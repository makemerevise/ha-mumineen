"""Turn yearly Hijri records (miqaats, urus, personal events) into dated occurrences.

Pure Python with no Home Assistant imports, so it can be tested on its own.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Iterable

from .hijri import HijriDate, clamped

KIND_MIQAAT = "miqaat"
KIND_URUS = "urus"
KIND_PERSONAL = "personal"

_RAAT = re.compile(r"\b(raat|laylat)", re.IGNORECASE)
_KEY_SPEC = re.compile(r"^\s*(?P<name>.+?)\s*@\s*(?P<month>\d{1,2})\s*/\s*(?P<day>\d{1,2})\s*$")


@dataclass(frozen=True)
class Record:
    """Something that falls on the same Hijri day every year."""

    kind: str
    title: str
    month: int
    day: int
    year: int | None = None  # set when it only happens in one Hijri year
    description: str = ""
    link: str = ""
    uid: str = ""

    @property
    def is_raat(self) -> bool:
        """Night miqaats start at Maghrib on the Gregorian day they're listed on."""
        return self.kind == KIND_MIQAAT and bool(_RAAT.search(self.title))

    @property
    def series_uid(self) -> str:
        if self.uid:
            return self.uid
        slug = re.sub(r"[^a-z0-9]+", "-", self.title.lower()).strip("-")
        return f"{self.kind}-{self.month:02d}{self.day:02d}-{slug}"


@dataclass(frozen=True)
class Occurrence:
    record: Record
    date: dt.date
    hijri: HijriDate

    @property
    def title(self) -> str:
        return self.record.title

    @property
    def kind(self) -> str:
        return self.record.kind


def record_from_api(item: dict) -> Record:
    """Build a Record from one item of mumineen.org's /calendar/{date}/miqaat response."""
    kind_name = ((item.get("type") or {}).get("name") or "").strip()
    name = (item.get("name") or "").strip()
    kind = KIND_URUS if kind_name.lower() == "urus" else KIND_MIQAAT
    if kind == KIND_MIQAAT and kind_name and kind_name.lower() != name.lower():
        title = f"{kind_name}: {name}"
    else:
        title = name or kind_name
    link = item.get("external_link") or ""
    if not link and item.get("local_link"):
        link = "https://mumineen.org" + str(item["local_link"])
    year = item.get("year")
    return Record(
        kind=kind,
        title=title,
        month=int(item["month"]),
        day=int(item["day"]),
        year=int(year) if year else None,
        link=link,
    )


def occurrences(records: Iterable[Record], start: dt.date, end: dt.date) -> list[Occurrence]:
    """Occurrences with start <= date < end, sorted by date."""
    records = list(records)
    if end <= start or not records:
        return []
    first = HijriDate.from_gregorian(start).year
    last = HijriDate.from_gregorian(end).year
    found: list[Occurrence] = []
    for year in range(first, last + 1):
        for record in records:
            if record.year is not None and record.year != year:
                continue
            hijri = clamped(year, record.month, record.day)
            date = hijri.to_gregorian()
            if start <= date < end:
                found.append(Occurrence(record, date, hijri))
    found.sort(key=lambda o: (o.date, o.kind != KIND_MIQAAT, o.title))
    return found


def miqaat_titles(records: Iterable[Record]) -> list[str]:
    """Distinct miqaat (non-urus) titles in Hijri calendar order."""
    seen: dict[str, tuple[int, int]] = {}
    for r in records:
        if r.kind == KIND_MIQAAT and r.title not in seen:
            seen[r.title] = (r.month, r.day)
    return sorted(seen, key=lambda t: seen[t])


def resolve_key_miqaat(spec: str, records: Iterable[Record]) -> Record | None:
    """Find the record a key-miqaat option refers to.

    Accepts a miqaat or personal-event title (case-insensitive), or a custom
    "Name @ month/day" Hijri date such as "Ramadan @ 9/1".
    """
    wanted = spec.strip().lower()
    for r in records:
        if r.kind != KIND_URUS and r.title.lower() == wanted:
            return r
    match = _KEY_SPEC.match(spec)
    if match:
        month, day = int(match["month"]), int(match["day"])
        if 1 <= month <= 12 and 1 <= day <= 30:
            return Record(kind=KIND_MIQAAT, title=match["name"], month=month, day=day)
    return None
