"""Actions: add or remove your own yearly Hijri events, and cast the Maghrib screen."""

from __future__ import annotations

import asyncio
import logging

import voluptuous as vol
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import (
    CHIME_FILE,
    DOMAIN,
    SCREEN_URL,
    SERVICE_ADD_EVENT,
    SERVICE_CAST_SCREEN,
    SERVICE_REMOVE_EVENT,
    STATIC_URL,
)
from .coordinator import MumineenCoordinator
from .screen import new_screen_token

_LOGGER = logging.getLogger(__name__)

CHIME_SECONDS = 7

ADD_EVENT_SCHEMA = vol.Schema(
    {
        vol.Required("name"): vol.All(cv.string, vol.Length(min=1)),
        vol.Required("month"): vol.All(vol.Coerce(int), vol.Range(min=1, max=12)),
        vol.Required("day"): vol.All(vol.Coerce(int), vol.Range(min=1, max=30)),
        vol.Optional("description", default=""): cv.string,
    }
)
REMOVE_EVENT_SCHEMA = vol.Schema({vol.Required("event"): cv.string})
CAST_SCREEN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional("chime", default=True): cv.boolean,
    }
)


def _coordinator(hass: HomeAssistant) -> MumineenCoordinator:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError("Mumineen is not set up")
    return entries[0].runtime_data


def _dash_cast(hass: HomeAssistant, entity_id: str, url: str) -> None:
    """Open a web page on a Google Cast display (runs in an executor thread)."""
    from pychromecast.controllers.dashcast import DashCastController  # noqa: PLC0415

    component = hass.data.get("entity_components", {}).get("media_player")
    entity = component.get_entity(entity_id) if component else None
    chromecast = getattr(entity, "_chromecast", None)
    if chromecast is None:
        raise HomeAssistantError(f"{entity_id} is not a Google Cast device")
    controller = getattr(entity, "_mumineen_dashcast", None)
    if controller is None:
        controller = DashCastController()
        chromecast.register_handler(controller)
        entity._mumineen_dashcast = controller  # noqa: SLF001
    controller.load_url(url, force=True)


def async_register_services(hass: HomeAssistant) -> None:
    async def add_event(call: ServiceCall) -> ServiceResponse:
        uid = await _coordinator(hass).async_add_event(
            call.data["name"], call.data["month"], call.data["day"], call.data["description"]
        )
        return {"uid": uid}

    async def remove_event(call: ServiceCall) -> None:
        if not await _coordinator(hass).async_remove_event(call.data["event"]):
            raise ServiceValidationError(f"No event called {call.data['event']}")

    async def cast_screen(call: ServiceCall) -> None:
        _coordinator(hass)
        try:
            base = get_url(hass, prefer_external=False, allow_cloud=False)
        except NoURLAvailableError as err:
            raise HomeAssistantError("Home Assistant has no local URL set") from err
        entity_ids: list[str] = call.data[ATTR_ENTITY_ID]
        if call.data["chime"]:
            await hass.services.async_call(
                "media_player",
                "play_media",
                {
                    ATTR_ENTITY_ID: entity_ids,
                    "media_content_id": f"{base}{STATIC_URL}/{CHIME_FILE}",
                    "media_content_type": "music",
                },
                blocking=True,
            )
            await asyncio.sleep(CHIME_SECONDS)
        for entity_id in entity_ids:
            url = f"{base}{SCREEN_URL}/{new_screen_token(hass)}"
            await hass.async_add_executor_job(_dash_cast, hass, entity_id, url)

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_EVENT, add_event, ADD_EVENT_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(DOMAIN, SERVICE_REMOVE_EVENT, remove_event, REMOVE_EVENT_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_CAST_SCREEN, cast_screen, CAST_SCREEN_SCHEMA)
