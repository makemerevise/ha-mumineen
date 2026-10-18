"""Constants for the Mumineen integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "mumineen"
API_BASE = "https://mumineen.org/api/v1"

CONF_LOCATION_NAME = "location_name"
CONF_ALERT_MINUTES = "alert_minutes"
CONF_KEY_MIQAATS = "key_miqaats"
DEFAULT_ALERT_MINUTES = 5

# Times returned by the salaat endpoint, in the order they happen.
SALAAT_TIMES = (
    "sihori",
    "fajr",
    "sunrise",
    "zawaal",
    "zohr_end",
    "asr_end",
    "maghrib",
    "maghrib_end",
    "nisful_layl",
    "nisful_layl_end",
)
# How long a namaaz time sensor keeps showing a time that has just passed.
ROLL_GRACE = timedelta(minutes=1)
# The namaaz that "next namaaz" steps through, keyed by the time they start.
NAMAAZ = {"fajr": "Fajr", "zawaal": "Zohr", "maghrib": "Maghrib"}

UPDATE_INTERVAL = timedelta(hours=6)
SALAAT_DAYS = 365  # the API allows at most a year per request
MIQAAT_REFRESH = timedelta(days=7)
UPCOMING_DAYS = 7

STATIC_URL = "/mumineen_static"
SCREEN_URL = "/api/mumineen/screen"
CHIME_FILE = "maghrib-chime.m4a"
SCREEN_TOKEN_TTL = 60  # seconds a cast screen link stays usable

SERVICE_ADD_EVENT = "add_event"
SERVICE_REMOVE_EVENT = "remove_event"
SERVICE_CAST_SCREEN = "cast_screen"
