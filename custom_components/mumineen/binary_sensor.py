"""The "Maghrib soon" sensor, on for the last few minutes before Maghrib."""

from __future__ import annotations

import datetime as dt
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import MumineenConfigEntry, MumineenCoordinator
from .entity import TickingEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: MumineenConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([MaghribSoonSensor(entry.runtime_data)])


class MaghribSoonSensor(TickingEntity, BinarySensorEntity):
    _attr_icon = "mdi:weather-sunset-down"

    def __init__(self, coordinator: MumineenCoordinator) -> None:
        super().__init__(coordinator, "maghrib_soon")

    def _maghrib(self) -> dt.datetime | None:
        times = self.coordinator.times_for(dt_util.now().date())
        return times["maghrib"] if times else None

    @property
    def is_on(self) -> bool | None:
        maghrib = self._maghrib()
        if maghrib is None:
            return None
        now = dt_util.now()
        return maghrib - dt.timedelta(minutes=self.coordinator.alert_minutes) <= now < maghrib

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        maghrib = self._maghrib()
        return {
            "maghrib": maghrib.isoformat() if maghrib else None,
            "minutes_before": self.coordinator.alert_minutes,
        }
