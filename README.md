# Mumineen for Home Assistant

Namaaz times, the Hijri date and miqaats from [mumineen.org](https://mumineen.org), as Home Assistant sensors and calendars.

## What you get

**Sensors**
- **Namaaz times:** Sihori, Fajr, Sunrise, Zawaal, Zohr end, Asr end, Maghrib, Maghrib end, Nisful layl and Nisful layl end. Each shows the coming one: today's until a minute after it passes, then tomorrow's.
- **Next namaaz:** the next of Fajr, Zohr and Maghrib, with its time.
- **Hijri date:** the Misri calendar. After Maghrib, the `raat` attribute names the night that has begun.
- **Miqaats this week:** a count of the miqaats in the next 7 days, plus your own events. The attributes list each one, with urus listed separately.
- **Days until …:** one countdown for each key miqaat you choose in the options.
- **Maghrib soon:** a binary sensor that turns on a few minutes before Maghrib (5 by default).

**Calendars**
- **Miqaats** and **Urus**, kept separate so urus don't crowd out the rest. Night miqaats (Fadhil Raat, Laylat al-Qadr, …) start at that evening's Maghrib.
- **My events:** your own dates, repeating every year on the same Hijri day. You can add them in two ways:
  - from Home Assistant's calendar, by picking a date (it's converted to its Hijri day), or
  - with the **Add my event** action, by giving a Hijri day and month.
  - Deleting one removes every year.

**Actions**
- `mumineen.add_event` / `mumineen.remove_event`: manage My events.
- `mumineen.cast_screen`: plays a soft chime, then shows a Maghrib countdown screen on Google Cast displays such as a Nest Hub. It works on your local network, without Home Assistant Cloud or HTTPS.

## How it works

- **Namaaz times:** fetched once a day, a year at a time, for the location you set up (the nearest mumineen.org location is suggested).
- **Miqaats:** fetched once a week.
- **Caching:** everything is kept locally, so it carries on through restarts and short API outages.
- **Hijri dates:** worked out locally with the tabular Misri calendar. This was checked against mumineen.org for every day from 1430 to 1473 AH.

The Maghrib screen is served without a Home Assistant login. Each link works only once and expires within a minute, and the page shows only public information (namaaz times and miqaats).

## Install

1. In HACS, open ⋮ → **Custom repositories** and add `https://github.com/makemerevise/ha-mumineen` as an **Integration**.
2. Download **Mumineen**, then restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration → Mumineen**.

Key miqaats and the "Maghrib soon" lead time are under the integration's **Configure** button. For a key date that isn't a listed miqaat, type it as `Name @ month/day`, for example `Ramadan @ 9/1`.

Not affiliated with mumineen.org.
