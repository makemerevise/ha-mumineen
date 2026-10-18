"""Set-up and options screens."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
from homeassistant.util import dt as dt_util

from .api import MumineenApi, MumineenApiError
from .const import (
    CONF_ALERT_MINUTES,
    CONF_KEY_MIQAATS,
    CONF_LOCATION_NAME,
    DEFAULT_ALERT_MINUTES,
    DOMAIN,
)
from .events import KIND_PERSONAL, miqaat_titles

_COORD = NumberSelector(NumberSelectorConfig(min=-180, max=180, step="any", mode=NumberSelectorMode.BOX))


class MumineenConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        api = MumineenApi(async_get_clientsession(self.hass))
        errors: dict[str, str] = {}
        if user_input is not None:
            today = dt_util.now().date()
            try:
                await api.salaat(
                    today, today, user_input[CONF_LATITUDE], user_input[CONF_LONGITUDE], self.hass.config.time_zone
                )
            except (MumineenApiError, KeyError, TypeError):
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=user_input[CONF_LOCATION_NAME], data=user_input)

        # Suggest the nearest location mumineen.org knows (usually the local masjid).
        defaults = {
            CONF_LOCATION_NAME: self.hass.config.location_name,
            CONF_LATITUDE: self.hass.config.latitude,
            CONF_LONGITUDE: self.hass.config.longitude,
        }
        try:
            nearest = await api.nearest_location(self.hass.config.latitude, self.hass.config.longitude)
            defaults = {
                CONF_LOCATION_NAME: nearest["name"],
                CONF_LATITUDE: float(nearest["latitude"]),
                CONF_LONGITUDE: float(nearest["longitude"]),
            }
        except (MumineenApiError, KeyError, TypeError, ValueError):
            pass
        if user_input is not None:
            defaults = user_input

        schema = vol.Schema(
            {
                vol.Required(CONF_LOCATION_NAME, default=defaults[CONF_LOCATION_NAME]): TextSelector(),
                vol.Required(CONF_LATITUDE, default=defaults[CONF_LATITUDE]): _COORD,
                vol.Required(CONF_LONGITUDE, default=defaults[CONF_LONGITUDE]): _COORD,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return MumineenOptionsFlow()


class MumineenOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        current: list[str] = list(options.get(CONF_KEY_MIQAATS, []))
        choices: list[str] = []
        coordinator = getattr(self.config_entry, "runtime_data", None)
        if coordinator is not None:
            records = coordinator.records()
            choices = miqaat_titles(records) + [r.title for r in records if r.kind == KIND_PERSONAL]
        choices += [c for c in current if c not in choices]

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_ALERT_MINUTES, default=options.get(CONF_ALERT_MINUTES, DEFAULT_ALERT_MINUTES)
                ): NumberSelector(NumberSelectorConfig(min=1, max=60, step=1, mode=NumberSelectorMode.BOX)),
                vol.Optional(CONF_KEY_MIQAATS, default=current): SelectSelector(
                    SelectSelectorConfig(
                        options=choices, multiple=True, custom_value=True, mode=SelectSelectorMode.DROPDOWN
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
