"""Fetches namaaz times and miqaats once in a while and keeps a cached copy."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import MumineenApi, MumineenApiError
from .const import (
    CONF_ALERT_MINUTES,
    CONF_KEY_MIQAATS,
    DEFAULT_ALERT_MINUTES,
    DOMAIN,
    MIQAAT_REFRESH,
    NAMAAZ,
    SALAAT_DAYS,
    UPDATE_INTERVAL,
)
from .events import (
    KIND_MIQAAT,
    KIND_PERSONAL,
    KIND_URUS,
    Occurrence,
    Record,
    occurrences,
    record_from_api,
    resolve_key_miqaat,
)
from .hijri import HijriDate

_LOGGER = logging.getLogger(__name__)

STORE_VERSION = 1
# Fetch again before the cached times run out, even if they were fetched today.
SALAAT_MIN_AHEAD = 30


@dataclass
class MumineenData:
    salaat: dict[str, dict[str, dt.datetime]] = field(default_factory=dict)
    salaat_fetched: dt.datetime | None = None
    miqaats: list[dict[str, Any]] = field(default_factory=list)  # raw API items
    miqaats_fetched: dt.datetime | None = None
    personal: list[dict[str, Any]] = field(default_factory=list)


MumineenConfigEntry = ConfigEntry["MumineenCoordinator"]


class MumineenCoordinator(DataUpdateCoordinator[MumineenData]):
    config_entry: MumineenConfigEntry

    def __init__(self, hass: HomeAssistant, entry: MumineenConfigEntry) -> None:
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=UPDATE_INTERVAL
        )
        self.api = MumineenApi(async_get_clientsession(hass))
        self._cache = Store(hass, STORE_VERSION, f"{DOMAIN}.{entry.entry_id}.cache")
        self._events_store = Store(hass, STORE_VERSION, f"{DOMAIN}.{entry.entry_id}.events")
        self._state = MumineenData()
        self._records: list[Record] = []
        # Derived values only change when the data does, or once a day, so they are
        # worked out once and reused by every entity rather than on each state write.
        self._keys: dict[str, Record | None] = {}
        self._memo: dict[tuple, list[Occurrence]] = {}
        self._memo_day: dt.date | None = None

    # ---- settings -------------------------------------------------------

    @property
    def latitude(self) -> float:
        return float(self.config_entry.data[CONF_LATITUDE])

    @property
    def longitude(self) -> float:
        return float(self.config_entry.data[CONF_LONGITUDE])

    @property
    def alert_minutes(self) -> int:
        return int(self.config_entry.options.get(CONF_ALERT_MINUTES, DEFAULT_ALERT_MINUTES))

    @property
    def key_miqaat_specs(self) -> list[str]:
        return list(self.config_entry.options.get(CONF_KEY_MIQAATS, []))

    # ---- loading and fetching ---------------------------------------------

    async def _async_setup(self) -> None:
        cached = await self._cache.async_load() or {}
        tz = dt_util.get_default_time_zone()
        self._state.salaat = {
            day: {k: dt.datetime.fromisoformat(v) for k, v in times.items()}
            for day, times in cached.get("salaat", {}).items()
        }
        if cached.get("salaat_fetched"):
            self._state.salaat_fetched = dt.datetime.fromisoformat(cached["salaat_fetched"]).astimezone(tz)
        self._state.miqaats = cached.get("miqaats", [])
        if cached.get("miqaats_fetched"):
            self._state.miqaats_fetched = dt.datetime.fromisoformat(cached["miqaats_fetched"]).astimezone(tz)
        events = await self._events_store.async_load() or {}
        self._state.personal = events.get("events", [])
        self._rebuild_records()

    async def _async_update_data(self) -> MumineenData:
        now = dt_util.now()
        today = now.date()
        state = self._state
        changed = False
        errors: list[str] = []

        ahead = (today + dt.timedelta(days=SALAAT_MIN_AHEAD)).isoformat()
        if state.salaat_fetched is None or state.salaat_fetched.date() < today or ahead not in state.salaat:
            try:
                state.salaat = await self._fetch_salaat(today)
                state.salaat_fetched = now
                changed = True
            except (MumineenApiError, KeyError, TypeError, ValueError) as err:
                errors.append(f"namaaz times: {err}")

        if state.miqaats_fetched is None or now - state.miqaats_fetched > MIQAAT_REFRESH:
            try:
                state.miqaats = await self._fetch_miqaats(today)
                state.miqaats_fetched = now
                changed = True
            except (MumineenApiError, KeyError, TypeError, ValueError) as err:
                errors.append(f"miqaats: {err}")

        if changed:
            self._rebuild_records()
            await self._save_cache()
        if errors:
            if today.isoformat() not in state.salaat or not state.miqaats:
                raise UpdateFailed("Could not reach mumineen.org: " + "; ".join(errors))
            _LOGGER.warning("Using cached data; mumineen.org failed for %s", "; ".join(errors))
        return state

    async def _fetch_salaat(self, today: dt.date) -> dict[str, dict[str, dt.datetime]]:
        tz_name = self.hass.config.time_zone
        tz = dt_util.get_time_zone(tz_name)
        raw = await self.api.salaat(
            today - dt.timedelta(days=1),
            today + dt.timedelta(days=SALAAT_DAYS - 2),
            self.latitude,
            self.longitude,
            tz_name,
        )
        return {
            day: {
                name: dt.datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz)
                for name, value in times.items()
            }
            for day, times in raw.items()
        }

    async def _fetch_miqaats(self, today: dt.date) -> list[dict[str, Any]]:
        """All miqaats for this Hijri year and the next (24 small requests, paced)."""
        year = HijriDate.from_gregorian(today).year
        items: list[dict[str, Any]] = []
        seen: set[tuple] = set()
        for y in (year, year + 1):
            for m in range(1, 13):
                for item in await self.api.month_miqaats(y, m):
                    key = (item.get("name"), item.get("month"), item.get("day"), item.get("year"))
                    if key not in seen:
                        seen.add(key)
                        items.append(item)
                await asyncio.sleep(0.5)
        return items

    async def _save_cache(self) -> None:
        state = self._state
        await self._cache.async_save(
            {
                "salaat": {
                    day: {k: v.isoformat() for k, v in times.items()} for day, times in state.salaat.items()
                },
                "salaat_fetched": state.salaat_fetched.isoformat() if state.salaat_fetched else None,
                "miqaats": state.miqaats,
                "miqaats_fetched": state.miqaats_fetched.isoformat() if state.miqaats_fetched else None,
            }
        )

    # ---- personal events -------------------------------------------------

    async def async_add_event(self, name: str, month: int, day: int, description: str = "") -> str:
        uid = f"personal-{uuid.uuid4().hex[:12]}"
        self._state.personal.append(
            {"uid": uid, "name": name.strip(), "month": month, "day": day, "description": description}
        )
        await self._save_events()
        return uid

    async def async_remove_event(self, uid_or_name: str) -> bool:
        wanted = uid_or_name.strip()
        before = len(self._state.personal)
        self._state.personal = [
            e for e in self._state.personal if e["uid"] != wanted and e["name"].lower() != wanted.lower()
        ]
        if len(self._state.personal) == before:
            return False
        await self._save_events()
        return True

    async def _save_events(self) -> None:
        await self._events_store.async_save({"events": self._state.personal})
        self._rebuild_records()
        self.async_update_listeners()

    # ---- derived values used by the entities -------------------------------

    def times_for(self, date: dt.date) -> dict[str, dt.datetime] | None:
        return self._state.salaat.get(date.isoformat())

    def _rebuild_records(self) -> None:
        recs: list[Record] = []
        for item in self._state.miqaats:
            try:
                recs.append(record_from_api(item))
            except (KeyError, TypeError, ValueError):
                _LOGGER.debug("Skipping unreadable miqaat %s", item)
        recs += [
            Record(
                kind=KIND_PERSONAL,
                title=e["name"],
                month=int(e["month"]),
                day=int(e["day"]),
                description=e.get("description", ""),
                uid=e["uid"],
            )
            for e in self._state.personal
        ]
        self._records = recs
        self._keys = {spec: resolve_key_miqaat(spec, recs) for spec in self.key_miqaat_specs}
        self._memo.clear()

    def records(self, kind: str | None = None) -> list[Record]:
        return list(self._records) if kind is None else [r for r in self._records if r.kind == kind]

    def occurrences(self, start: dt.date, end: dt.date, kinds: tuple[str, ...]) -> list[Occurrence]:
        today = dt_util.now().date()
        if self._memo_day != today or len(self._memo) > 64:
            self._memo.clear()
            self._memo_day = today
        key = (start, end, kinds)
        found = self._memo.get(key)
        if found is None:
            found = occurrences([r for r in self._records if r.kind in kinds], start, end)
            self._memo[key] = found
        return found

    def hijri_today(self, now: dt.datetime) -> HijriDate:
        return HijriDate.from_gregorian(now.date())

    def after_maghrib(self, now: dt.datetime) -> bool:
        times = self.times_for(now.date())
        return bool(times and now >= times["maghrib"])

    def next_namaaz(self, now: dt.datetime) -> tuple[str, dt.datetime] | None:
        for offset in (0, 1):
            times = self.times_for(now.date() + dt.timedelta(days=offset))
            if not times:
                continue
            for key, label in NAMAAZ.items():
                if times[key] > now:
                    return label, times[key]
        return None

    def key_miqaats(self) -> list[tuple[str, Record | None]]:
        return list(self._keys.items())

    def key_record(self, spec: str) -> Record | None:
        return self._keys.get(spec)

    def upcoming(self, now: dt.datetime, days: int, kinds: tuple[str, ...] = (KIND_MIQAAT, KIND_PERSONAL)) -> list[Occurrence]:
        start = now.date()
        return self.occurrences(start, start + dt.timedelta(days=days), kinds)


ALL_KINDS = (KIND_MIQAAT, KIND_URUS, KIND_PERSONAL)
