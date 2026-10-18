"""Misri (Fatimid tabular) Hijri calendar, as used by the Dawoodi Bohra community.

Pure Python with no Home Assistant imports, so it can be tested on its own.
Checked against mumineen.org's calendar API for every day of 1430-1473 AH.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

# Years of the 30-year cycle that have 355 days (Zilhaj gets a 30th day).
LEAP_YEARS = frozenset({2, 5, 8, 10, 13, 16, 19, 21, 24, 27, 29})
DAYS_PER_CYCLE = 10631
# Proleptic Gregorian ordinal of 1 Muharram 1 AH (18 July 622).
EPOCH = 227014

MONTHS = (
    "Muharram al-Haraam",
    "Safar al-Muzaffar",
    "Rabi al-Awwal",
    "Rabi al-Aakhar",
    "Jumada al-Ula",
    "Jumada al-Ukhra",
    "Rajab al-Asab",
    "Shaban al-Karim",
    "Ramadan al-Moazzam",
    "Shawwal al-Mukarram",
    "Zilqad al-Haraam",
    "Zilhaj al-Haraam",
)
MONTHS_SHORT = (
    "Muharram",
    "Safar",
    "Rabi I",
    "Rabi II",
    "Jumada I",
    "Jumada II",
    "Rajab",
    "Shaban",
    "Ramadan",
    "Shawwal",
    "Zilqad",
    "Zilhaj",
)


def is_leap(year: int) -> bool:
    return (year % 30) in LEAP_YEARS


def year_length(year: int) -> int:
    return 355 if is_leap(year) else 354


def month_length(year: int, month: int) -> int:
    if month % 2 == 1 or (month == 12 and is_leap(year)):
        return 30
    return 29


def _days_before_year(year: int) -> int:
    cycles, rem = divmod(year - 1, 30)
    return cycles * DAYS_PER_CYCLE + sum(year_length(y) for y in range(1, rem + 1))


def _days_before_month(year: int, month: int) -> int:
    return sum(month_length(year, m) for m in range(1, month))


@dataclass(frozen=True, order=True)
class HijriDate:
    year: int
    month: int
    day: int

    def __post_init__(self) -> None:
        if not 1 <= self.month <= 12:
            raise ValueError(f"Hijri month must be 1-12, got {self.month}")
        if not 1 <= self.day <= month_length(self.year, self.month):
            raise ValueError(f"Hijri day out of range: {self.year}-{self.month}-{self.day}")

    @classmethod
    def from_gregorian(cls, date: dt.date) -> HijriDate:
        days = date.toordinal() - EPOCH
        cycles, rem = divmod(days, DAYS_PER_CYCLE)
        year = cycles * 30 + 1
        while rem >= year_length(year):
            rem -= year_length(year)
            year += 1
        month = 1
        while rem >= month_length(year, month):
            rem -= month_length(year, month)
            month += 1
        return cls(year, month, rem + 1)

    def to_gregorian(self) -> dt.date:
        ordinal = EPOCH + _days_before_year(self.year) + _days_before_month(self.year, self.month) + self.day - 1
        return dt.date.fromordinal(ordinal)

    @property
    def month_name(self) -> str:
        return MONTHS[self.month - 1]

    @property
    def month_name_short(self) -> str:
        return MONTHS_SHORT[self.month - 1]

    def isoformat(self) -> str:
        return f"{self.year:04d}-{self.month:02d}-{self.day:02d}"

    def format(self, with_year: bool = True) -> str:
        text = f"{self.day} {self.month_name}"
        return f"{text} {self.year}" if with_year else text

    def __str__(self) -> str:
        return self.format()


def clamped(year: int, month: int, day: int) -> HijriDate:
    """Hijri date, moving a 30th to the 29th in months that only have 29 days."""
    return HijriDate(year, month, min(day, month_length(year, month)))


def next_occurrence(month: int, day: int, on_or_after: dt.date) -> dt.date:
    """Next Gregorian date (on or after the given date) of a yearly Hijri day."""
    year = HijriDate.from_gregorian(on_or_after).year
    for y in (year, year + 1):
        date = clamped(y, month, day).to_gregorian()
        if date >= on_or_after:
            return date
    raise AssertionError("unreachable")
