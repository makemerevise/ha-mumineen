"""Namaaz time, Hijri date and miqaat countdown sensors."""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import ROLL_GRACE, SALAAT_TIMES, UPCOMING_DAYS
from .coordinator import MumineenConfigEntry, MumineenCoordinator
from .entity import TickingEntity
from .events import KIND_MIQAAT, KIND_PERSONAL, KIND_URUS, Occurrence, Record
from .hijri import HijriDate, next_occurrence


async def async_setup_entry(
    hass: HomeAssistant, entry: MumineenConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [SalaatTimeSensor(coordinator, key) for key in SALAAT_TIMES]
    entities += [
        NextNamaazSensor(coordinator),
        NextNamaazTimeSensor(coordinator),
        HijriDateSensor(coordinator),
        UpcomingSensor(coordinator),
    ]
    entities += [KeyMiqaatSensor(coordinator, spec) for spec in coordinator.key_miqaat_specs]
    async_add_entities(entities)


def _describe(occ: Occurrence, today: dt.date) -> dict[str, Any]:
    return {
        "date": occ.date.isoformat(),
        "weekday": occ.date.strftime("%a"),
        "days": (occ.date - today).days,
        "hijri": occ.hijri.format(with_year=False),
        "title": occ.title,
        "kind": occ.kind,
        "raat": occ.record.is_raat,
    }


class SalaatTimeSensor(TickingEntity, SensorEntity):
    """The next time of one namaaz boundary (Sihori, Fajr, Maghrib, ...).

    Shows today's time until a minute after it has passed, then moves on to
    tomorrow's, so it always points at the coming one. The minute's grace lets
    automations that fire exactly on the time still see it.
    """

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: MumineenCoordinator, key: str) -> None:
        super().__init__(coordinator, key)
        self._key = key

    @property
    def native_value(self) -> dt.datetime | None:
        now = dt_util.now()
        cutoff = now - ROLL_GRACE
        for offset in (-1, 0, 1, 2):
            times = self.coordinator.times_for(now.date() + dt.timedelta(days=offset))
            value = times.get(self._key) if times else None
            if value and value > cutoff:
                return value
        return None


class NextNamaazSensor(TickingEntity, SensorEntity):
    _attr_icon = "mdi:mosque"

    def __init__(self, coordinator: MumineenCoordinator) -> None:
        super().__init__(coordinator, "next_namaaz")

    @property
    def native_value(self) -> str | None:
        found = self.coordinator.next_namaaz(dt_util.now())
        return found[0] if found else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        found = self.coordinator.next_namaaz(dt_util.now())
        return {"time": found[1].isoformat()} if found else {}


class NextNamaazTimeSensor(TickingEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: MumineenCoordinator) -> None:
        super().__init__(coordinator, "next_namaaz_time")

    @property
    def native_value(self) -> dt.datetime | None:
        found = self.coordinator.next_namaaz(dt_util.now())
        return found[1] if found else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        found = self.coordinator.next_namaaz(dt_util.now())
        return {"namaaz": found[0]} if found else {}


class HijriDateSensor(TickingEntity, SensorEntity):
    """Today's Hijri date. After Maghrib, `raat` names the night that has begun."""

    _attr_icon = "mdi:moon-waxing-crescent"

    def __init__(self, coordinator: MumineenCoordinator) -> None:
        super().__init__(coordinator, "hijri_date")

    @property
    def native_value(self) -> str:
        return self.coordinator.hijri_today(dt_util.now()).format()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        now = dt_util.now()
        today = self.coordinator.hijri_today(now)
        after = self.coordinator.after_maghrib(now)
        tonight = HijriDate.from_gregorian(now.date() + dt.timedelta(days=1))
        return {
            "year": today.year,
            "month": today.month,
            "day": today.day,
            "month_name": today.month_name,
            "iso": today.isoformat(),
            "after_maghrib": after,
            "raat": f"Raat of {tonight.format()}" if after else None,
        }


class UpcomingSensor(TickingEntity, SensorEntity):
    """Number of miqaats (and your own events) in the next 7 days, listed in attributes."""

    _attr_icon = "mdi:calendar-star"
    _attr_native_unit_of_measurement = "miqaats"
    _unrecorded_attributes = frozenset({"events", "urus"})
    _tick_daily = True

    def __init__(self, coordinator: MumineenCoordinator) -> None:
        super().__init__(coordinator, "upcoming")

    def _occurrences(self) -> list[Occurrence]:
        return self.coordinator.upcoming(dt_util.now(), UPCOMING_DAYS, (KIND_MIQAAT, KIND_PERSONAL, KIND_URUS))

    @property
    def native_value(self) -> int:
        return sum(1 for o in self._occurrences() if o.kind != KIND_URUS)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        today = dt_util.now().date()
        occs = self._occurrences()
        return {
            "events": [_describe(o, today) for o in occs if o.kind != KIND_URUS],
            "urus": [_describe(o, today) for o in occs if o.kind == KIND_URUS],
        }


class KeyMiqaatSensor(TickingEntity, SensorEntity):
    """Days until one of the key miqaats chosen in the integration's options."""

    _attr_icon = "mdi:timer-sand"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.DAYS
    _attr_suggested_display_precision = 0
    _tick_daily = True

    def __init__(self, coordinator: MumineenCoordinator, spec: str) -> None:
        slug = re.sub(r"[^a-z0-9]+", "_", spec.lower()).strip("_")
        super().__init__(coordinator, f"key_{slug}", translated=False)
        self._spec = spec
        self._attr_name = f"Days until {self._label}"

    @property
    def _record(self) -> Record | None:
        return self.coordinator.key_record(self._spec)

    @property
    def _label(self) -> str:
        return self._spec.split("@")[0].strip()

    @property
    def available(self) -> bool:
        return super().available and self._record is not None

    def _next_date(self) -> dt.date | None:
        record = self._record
        if record is None:
            return None
        today = dt_util.now().date()
        cached = getattr(self, "_cached", None)
        if cached is None or cached[0] != today or cached[1] is not record:
            self._cached = (today, record, next_occurrence(record.month, record.day, today))
        return self._cached[2]

    @property
    def native_value(self) -> int | None:
        date = self._next_date()
        return (date - dt_util.now().date()).days if date else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        date = self._next_date()
        if date is None:
            return {"spec": self._spec}
        return {
            "title": self._record.title if self._record else self._label,
            "date": date.isoformat(),
            "weekday": date.strftime("%A"),
            "hijri": HijriDate.from_gregorian(date).format(),
            "spec": self._spec,
        }
