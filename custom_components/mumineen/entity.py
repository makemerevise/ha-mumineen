"""Shared entity base classes."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_LOCATION_NAME, DOMAIN
from .coordinator import MumineenCoordinator


class MumineenEntity(CoordinatorEntity[MumineenCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: MumineenCoordinator, key: str, translated: bool = True) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        if translated:
            self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Mumineen",
            manufacturer="mumineen.org",
            model=entry.data.get(CONF_LOCATION_NAME),
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://mumineen.org",
        )


class TickingEntity(MumineenEntity):
    """Re-evaluates its state on a clock, for time-based values.

    Every minute by default; entities whose value only changes with the date
    set `_tick_daily` and re-evaluate just after midnight instead.
    """

    _tick_daily = False

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        when = {"hour": 0, "minute": 0, "second": 5} if self._tick_daily else {"second": 0}
        self.async_on_remove(async_track_time_change(self.hass, self._tick, **when))

    @callback
    def _tick(self, _now) -> None:
        self.async_write_ha_state()
