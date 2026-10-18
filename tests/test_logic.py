"""Tests for the pure calendar logic (no Home Assistant needed).

Run: python3 tests/test_logic.py [months.json] [miqaat-dir]
months.json maps "y-m" to [[hijri, gregorian], ...] pairs from mumineen.org's
/calendar endpoint; miqaat-dir holds miq_01.json ... miq_12.json for 1448 AH.
"""

import datetime as dt
import glob
import importlib.util
import json
import os
import sys
import types

ROOT = os.path.join(os.path.dirname(__file__), "..", "custom_components", "mumineen")


def _load():
    pkg = types.ModuleType("mumineen_pure")
    pkg.__path__ = [ROOT]
    sys.modules["mumineen_pure"] = pkg
    mods = {}
    for name in ("hijri", "events"):
        spec = importlib.util.spec_from_file_location(f"mumineen_pure.{name}", os.path.join(ROOT, f"{name}.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        mods[name] = mod
    return mods["hijri"], mods["events"]


hijri, events = _load()
H = hijri.HijriDate


def test_anchor():
    assert H.from_gregorian(dt.date(2026, 10, 18)) == H(1448, 5, 8)
    assert H(1448, 5, 8).to_gregorian() == dt.date(2026, 10, 18)
    assert str(H(1448, 5, 8)) == "8 Jumada al-Ula 1448"


def test_round_trip():
    d = dt.date(1990, 1, 1)
    while d < dt.date(2060, 1, 1):
        assert H.from_gregorian(d).to_gregorian() == d, d
        d += dt.timedelta(days=1)


def test_against_api(path):
    data = json.load(open(path))
    n = 0
    for days in data.values():
        for h, g in days:
            y, m, d = map(int, h.split("-"))
            assert H(y, m, d).to_gregorian() == dt.date.fromisoformat(g), (h, g)
            assert H.from_gregorian(dt.date.fromisoformat(g)) == H(y, m, d), (h, g)
            n += 1
    return n


def test_miqaats_against_api(folder):
    items = []
    for f in sorted(glob.glob(os.path.join(folder, "miq_*.json"))):
        items += json.load(open(f))["data"]
    records = [events.record_from_api(i) for i in items]
    occs = events.occurrences(records, dt.date(2026, 6, 1), dt.date(2027, 6, 30))
    by_key = {(o.title, o.hijri.isoformat()): o.date for o in occs}
    for item, record in zip(items, records):
        got = by_key[(record.title, item["hijri_date"])]
        assert got == dt.date.fromisoformat(item["gregorian_date"]), (record.title, got, item["gregorian_date"])
    kinds = {r.kind for r in records}
    assert kinds == {events.KIND_MIQAAT, events.KIND_URUS}
    raat = sorted({r.title for r in records if r.is_raat})
    assert "Fadhil Raat: Pehli Raat Washeq" in raat
    assert "Laylatul Qadr: Laylat al-Qadr (23rd Raat)" in raat
    assert not any(r.is_raat for r in records if r.kind == events.KIND_URUS)
    assert "Milad: Eid Milad un Nabi" in events.miqaat_titles(records)
    return len(items), raat


def test_key_specs():
    recs = [events.Record(kind=events.KIND_MIQAAT, title="Milad: Eid Milad un Nabi", month=3, day=12)]
    assert events.resolve_key_miqaat("milad: eid milad un nabi", recs).month == 3
    r = events.resolve_key_miqaat("Ramadan @ 9/1", recs)
    assert (r.title, r.month, r.day) == ("Ramadan", 9, 1)
    assert events.resolve_key_miqaat("Nonsense", recs) is None
    assert events.resolve_key_miqaat("Bad @ 13/1", recs) is None


def test_next_occurrence_and_clamp():
    # 1 Ramadan 1448 = 6 Feb 2027 (per the API's Fadhil Raat dates: 9/16 = 21 Feb 2027).
    assert hijri.next_occurrence(9, 1, dt.date(2026, 10, 18)) == dt.date(2027, 2, 6)
    # a 30th in a 29-day month moves to the 29th
    assert hijri.month_length(1448, 2) == 29
    assert hijri.clamped(1448, 2, 30) == H(1448, 2, 29)
    # on the day itself, it's today
    assert hijri.next_occurrence(5, 8, dt.date(2026, 10, 18)) == dt.date(2026, 10, 18)


def test_personal_series():
    rec = events.Record(kind=events.KIND_PERSONAL, title="Dada's barsi", month=5, day=10, uid="personal-abc")
    occs = events.occurrences([rec], dt.date(2026, 1, 1), dt.date(2030, 1, 1))
    assert [o.date.year for o in occs] == [2026, 2027, 2028, 2029]
    assert all(o.hijri.month == 5 and o.hijri.day == 10 for o in occs)
    assert rec.series_uid == "personal-abc"
    assert not rec.is_raat


if __name__ == "__main__":
    test_anchor()
    test_round_trip()
    test_key_specs()
    test_personal_series()
    if len(sys.argv) > 1:
        print("API days matched:", test_against_api(sys.argv[1]))
    if len(sys.argv) > 2:
        n, raat = test_miqaats_against_api(sys.argv[2])
        print("API miqaats matched:", n, "| raat titles:", raat)
    test_next_occurrence_and_clamp()
    print("all tests passed")
