"""The Maghrib screen: a small self-contained page cast to Nest Hubs.

The page is served without a Home Assistant login, so each link only works
once and expires within a minute (the same approach as WebRTC Camera's
DashCast links). It only shows public information: namaaz times and miqaats.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import secrets
import time

from aiohttp import web
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SCREEN_TOKEN_TTL, SCREEN_URL
from .coordinator import MumineenCoordinator
from .events import KIND_MIQAAT, KIND_PERSONAL
from .hijri import HijriDate


def new_screen_token(hass: HomeAssistant) -> str:
    tokens: dict[str, float] = hass.data[DOMAIN]["tokens"]
    now = time.time()
    for token, expires in list(tokens.items()):
        if expires < now:
            del tokens[token]
    token = secrets.token_urlsafe(18)
    tokens[token] = now + SCREEN_TOKEN_TTL
    return token


class ScreenView(HomeAssistantView):
    url = SCREEN_URL + "/{token}"
    name = "api:mumineen:screen"
    requires_auth = False

    async def get(self, request: web.Request, token: str) -> web.Response:
        hass = request.app[KEY_HASS]
        expires = hass.data[DOMAIN]["tokens"].pop(token, None)
        if expires is None or expires < time.time():
            return web.Response(status=404, text="This link has expired.")
        entries = hass.config_entries.async_loaded_entries(DOMAIN)
        if not entries:
            return web.Response(status=503, text="Mumineen is not set up.")
        page = render_screen(entries[0].runtime_data, dt_util.now())
        return web.Response(text=page, content_type="text/html", headers={"Cache-Control": "no-store"})


def _tonight(coordinator: MumineenCoordinator, today: dt.date) -> list[str]:
    """Miqaats whose night starts this evening, then those on tomorrow's day."""
    tomorrow = today + dt.timedelta(days=1)
    kinds = (KIND_MIQAAT, KIND_PERSONAL)
    titles = [o.title for o in coordinator.occurrences(today, tomorrow, kinds) if o.record.is_raat]
    titles += [
        o.title
        for o in coordinator.occurrences(tomorrow, tomorrow + dt.timedelta(days=1), kinds)
        if not o.record.is_raat
    ]
    return titles


def render_screen(coordinator: MumineenCoordinator, now: dt.datetime) -> str:
    today = now.date()
    times = coordinator.times_for(today)
    raat = HijriDate.from_gregorian(today + dt.timedelta(days=1))
    if times:
        maghrib = times["maghrib"]
        maghrib_ms = int(maghrib.timestamp() * 1000)
        maghrib_text = maghrib.strftime("%H:%M")
    else:
        maghrib_ms = 0
        maghrib_text = "--:--"
    items = "".join(f"<li>{html.escape(t)}</li>" for t in _tonight(coordinator, today))
    tonight = f'<ul class="tonight">{items}</ul>' if items else ""
    return _PAGE.format(
        hijri=html.escape(f"Raat of {raat.format()}"),
        maghrib=maghrib_text,
        tonight=tonight,
        maghrib_ms=json.dumps(maghrib_ms),
    )


_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Maghrib</title>
<style>
  :root {{ --fg: #f4efe3; --muted: #b8b1a0; --accent: #d9b65f; }}
  html, body {{ margin: 0; height: 100%; overflow: hidden; color: var(--fg);
    background: radial-gradient(130% 110% at 50% 0%, #1f3a31 0%, #0e1915 62%);
    font-family: "Google Sans", Roboto, system-ui, sans-serif; }}
  .wrap {{ box-sizing: border-box; height: 100%; padding: 5vh 6vw; display: flex;
    flex-direction: column; align-items: center; justify-content: center; text-align: center; }}
  .hijri {{ font-size: 4.4vh; color: var(--muted); }}
  .label {{ margin-top: 3vh; font-size: 5.5vh; letter-spacing: .28em; text-transform: uppercase; color: var(--accent); }}
  .time {{ font-size: 27vh; font-weight: 300; line-height: 1; margin: 1vh 0 2vh; }}
  .count {{ font-size: 5.5vh; color: var(--muted); font-variant-numeric: tabular-nums; min-height: 7vh; }}
  .tonight {{ margin: 4vh 0 0; padding: 0; list-style: none; font-size: 3.8vh; line-height: 1.5; }}
  .tonight li::before {{ content: "\\2726  "; color: var(--accent); }}
</style>
</head>
<body>
<div class="wrap">
  <div class="hijri">{hijri}</div>
  <div class="label">Maghrib</div>
  <div class="time">{maghrib}</div>
  <div class="count" id="count"></div>
  {tonight}
</div>
<script>
  const maghrib = {maghrib_ms};
  const el = document.getElementById("count");
  function tick() {{
    if (!maghrib) {{ el.textContent = "Namaaz times unavailable"; return; }}
    const left = Math.round((maghrib - Date.now()) / 1000);
    if (left <= 0) {{ el.textContent = "It is time for Maghrib"; return; }}
    const m = Math.floor(left / 60), s = left % 60;
    el.textContent = "in " + m + ":" + String(s).padStart(2, "0");
  }}
  tick();
  setInterval(tick, 1000);
</script>
</body>
</html>
"""
