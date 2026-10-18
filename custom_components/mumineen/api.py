"""Small client for mumineen.org's public API (no authentication)."""

from __future__ import annotations

import asyncio
import datetime as dt
from typing import Any

import aiohttp

from .const import API_BASE


class MumineenApiError(Exception):
    """The API could not be reached or returned something unexpected."""


class MumineenApi:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        # Without Accept: application/json the API answers errors with an HTML redirect.
        headers = {"Accept": "application/json", "User-Agent": "ha-mumineen"}
        try:
            async with asyncio.timeout(30):
                async with self._session.get(f"{API_BASE}{path}", params=params, headers=headers) as resp:
                    if resp.status != 200:
                        raise MumineenApiError(f"{path}: HTTP {resp.status}")
                    return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise MumineenApiError(f"{path}: {err}") from err

    async def nearest_location(self, latitude: float, longitude: float) -> dict[str, Any]:
        data = await self._get("/location/nearest", {"latitude": latitude, "longitude": longitude})
        return data["data"]

    async def salaat(
        self, start: dt.date, end: dt.date, latitude: float, longitude: float, timezone: str
    ) -> dict[str, dict[str, str]]:
        """Times per Gregorian date, as local "YYYY-MM-DD HH:MM:SS" strings."""
        data = await self._get(
            "/salaat",
            {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "latitude": latitude,
                "longitude": longitude,
                "timezone": timezone,
            },
        )
        return data["data"]

    async def month_miqaats(self, hijri_year: int, hijri_month: int) -> list[dict[str, Any]]:
        data = await self._get(f"/calendar/{hijri_year:04d}-{hijri_month:02d}-01/miqaat")
        return data["data"]
