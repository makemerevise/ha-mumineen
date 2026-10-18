"""Miqaats, Urus and My events calendars."""

from __future__ import annotations

import datetime as dt
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEntityFeature, CalendarEvent
from homeassistant.components.calendar.const import EVENT_DESCRIPTION, EVENT_START, EVENT_SUMMARY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import MumineenConfigEntry, MumineenCoordinator
from .entity import MumineenEntity
from .events import KIND_MIQAAT, KIND_PERSONAL, KIND_URUS, Occurrence
from .hijri import HijriDate

CALENDARS = {"miqaats": KIND_MIQAAT, "urus": KIND_URUS, "my_events": KIND_PERSONAL}


async def async_setup_entry(
    hass: HomeAssistant, entry: MumineenConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities(MumineenCalendar(entry.runtime_data, key, kind) for key, kind in CALENDARS.items())


class MumineenCalendar(MumineenEntity, CalendarEntity):
    def __init__(self, coordinator: MumineenCoordinator, key: str, kind: str) -> None:
        super().__init__(coordinator, key)
        self._kind = kind
        if kind == KIND_PERSONAL:
            self._attr_supported_features = CalendarEntityFeature.CREATE_EVENT | CalendarEntityFeature.DELETE_EVENT

    def _to_event(self, occ: Occurrence) -> CalendarEvent:
        record = occ.record
        lines = [occ.hijri.format()]
        start: dt.date | dt.datetime = occ.date
        end: dt.date | dt.datetime = occ.date + dt.timedelta(days=1)
        if record.is_raat:
            # The night begins at Maghrib on the day it's listed on and runs to Fajr.
            times = self.coordinator.times_for(occ.date)
            if times:
                start = times["maghrib"]
                following = self.coordinator.times_for(occ.date + dt.timedelta(days=1))
                end = following["fajr"] if following else start + dt.timedelta(hours=12)
                lines.append("Raat begins at Maghrib.")
        if record.kind == KIND_PERSONAL:
            lines.append(f"Repeats every year on {occ.hijri.format(with_year=False)}.")
        if record.description:
            lines.append(record.description)
        if record.link:
            lines.append(record.link)
        return CalendarEvent(
            start=start,
            end=end,
            summary=record.title,
            description="\n".join(lines),
            uid=record.series_uid,
            recurrence_id=occ.date.isoformat(),
        )

    def _events_between(self, start: dt.date, end: dt.date) -> list[CalendarEvent]:
        return [self._to_event(o) for o in self.coordinator.occurrences(start, end, (self._kind,))]

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        today = now.date()
        for event in self._events_between(today - dt.timedelta(days=1), today + dt.timedelta(days=400)):
            if event.end_datetime_local > now:
                return event
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: dt.datetime, end_date: dt.datetime
    ) -> list[CalendarEvent]:
        events = self._events_between(
            dt_util.as_local(start_date).date() - dt.timedelta(days=1),
            dt_util.as_local(end_date).date() + dt.timedelta(days=1),
        )
        return [e for e in events if e.end_datetime_local > start_date and e.start_datetime_local < end_date]

    async def async_create_event(self, **kwargs: Any) -> None:
        """Adding an event here makes it repeat every year on the same Hijri day."""
        start = kwargs[EVENT_START]
        date = dt_util.as_local(start).date() if isinstance(start, dt.datetime) else start
        hijri = HijriDate.from_gregorian(date)
        await self.coordinator.async_add_event(
            kwargs[EVENT_SUMMARY], hijri.month, hijri.day, kwargs.get(EVENT_DESCRIPTION) or ""
        )

    async def async_delete_event(
        self, uid: str, recurrence_id: str | None = None, recurrence_range: str | None = None
    ) -> None:
        # Personal events are always a yearly series, so this removes every year.
        if not await self.coordinator.async_remove_event(uid):
            raise HomeAssistantError(f"No event with id {uid}")
