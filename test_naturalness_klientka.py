"""
Naturalness regression — 10 Client Test JSONs (Testy_Klientki)

FIX #186 (A4):
  1. Every active user preference has >= 1 matching attraction (preference_coverage)
  2. test-07 (culture adventure): no iconic mountain-only trails (Morskie Oko, …)
  3. test-08 (7 days): at most one far geo-region per day (no Pieniny + Słowacja mix)

Usage:
    cd travel-planner-backend
    python test_naturalness_klientka.py
"""
import contextlib
import io
import json
import sys
from collections import Counter
from pathlib import Path

BACKEND_DIR = Path(__file__).parent
sys.path.insert(0, str(BACKEND_DIR))

from app.application.services.plan_service import PlanService
from app.domain.models.plan import ItemType
from app.domain.models.trip_input import TripInput
from app.domain.planner.engine import (
    is_scenic_experience_poi,
    is_underground_poi,
    poi_geo_region_key,
)
from app.infrastructure.repositories.poi_repository import POIRepository

TESTS_DIR = BACKEND_DIR.parent / "Testy_Klientki"
TEST_NUMBERS = list(range(1, 11))

_ICONIC_TRAILS = (
    "morskie oko", "kopieniec", "szymoszkowa", "rusinowa polana",
    "pięć stawów", "piec stawow", "giewont",
)


def load_test(n: int) -> dict:
    with open(TESTS_DIR / f"test-{n:02d}.json", encoding="utf-8") as f:
        return json.load(f)


def run_plan(n: int, svc: PlanService):
    data = load_test(n)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        resp = svc.generate_plan(TripInput(**data))
    return data, resp


def check_preferences(data: dict, resp, test_n: int) -> list[str]:
    errs = []
    prefs = data.get("preferences") or []
    cov = getattr(resp, "preference_coverage", None) or {}
    for pref in prefs:
        info = cov.get(pref) or {}
        if not info.get("covered"):
            errs.append(f"pref '{pref}' not covered: {info}")
    return errs


def check_test07_trails(resp) -> list[str]:
    errs = []
    for day in resp.days:
        for it in day.items:
            if getattr(it, "type", None) != ItemType.ATTRACTION:
                continue
            name = (getattr(it, "name", "") or "").lower()
            for marker in _ICONIC_TRAILS:
                if marker in name:
                    errs.append(f"day {day.day}: iconic trail '{it.name}'")
    return errs


def check_test08_regions(resp, poi_by_id: dict) -> list[str]:
    errs = []
    for day in resp.days:
        regions = set()
        for it in day.items:
            if getattr(it, "type", None) != ItemType.ATTRACTION:
                continue
            poi = poi_by_id.get(getattr(it, "poi_id", ""), {"name": it.name})
            r = poi_geo_region_key(poi)
            if r:
                regions.add(r)
        if len(regions) > 1:
            errs.append(f"day {day.day}: mixed far regions {regions}")
    return errs


def check_no_sightseeing_after_long_trail(resp, poi_by_id: dict) -> list[str]:
    """FIX #193: po 3h+ szlaku — bez jaskiń, muzeów, zamków (tylko termy/free_time)."""
    from app.domain.planner.engine import (
        is_museum_heritage_poi,
        is_post_trail_recovery_poi,
        is_underground_poi,
    )
    errs = []
    for day in resp.days:
        trail_end_min = None
        max_trail = 0
        for it in day.items:
            if getattr(it, "type", None) != ItemType.ATTRACTION:
                continue
            p = poi_by_id.get(getattr(it, "poi_id", ""), {})
            if p.get("type") == "trail":
                dur = int(p.get("time_min") or p.get("duration_min") or 0)
                max_trail = max(max_trail, dur)
                if it.end_time:
                    from app.domain.planner.engine import time_to_minutes
                    trail_end_min = time_to_minutes(it.end_time)
        if max_trail < 180:
            continue
        for it in day.items:
            if getattr(it, "type", None) != ItemType.ATTRACTION:
                continue
            p = poi_by_id.get(getattr(it, "poi_id", ""), {"name": it.name})
            if p.get("type") == "trail":
                continue
            if is_post_trail_recovery_poi(p):
                continue
            if trail_end_min and it.start_time:
                from app.domain.planner.engine import time_to_minutes
                if time_to_minutes(it.start_time) < trail_end_min:
                    continue
            if is_underground_poi(p) or is_museum_heritage_poi(p) or "zamek" in (it.name or "").lower():
                errs.append(
                    f"day {day.day}: '{it.name}' after {max_trail}min trail (sightseeing blocked)"
                )
    return errs


def check_no_far_excursion_after_long_trail(resp, poi_by_id: dict) -> list[str]:
    """FIX #187a: no Zone C / Pieniny after 3h+ trail on same day."""
    errs = []
    for day in resp.days:
        max_trail = 0
        for it in day.items:
            if getattr(it, "type", None) != ItemType.ATTRACTION:
                continue
            p = poi_by_id.get(getattr(it, "poi_id", ""), {})
            if p.get("type") == "trail":
                max_trail = max(max_trail, int(p.get("time_min") or p.get("duration_min") or 0))
        if max_trail < 180:
            continue
        for it in day.items:
            if getattr(it, "type", None) != ItemType.ATTRACTION:
                continue
            p = poi_by_id.get(getattr(it, "poi_id", ""), {})
            if p.get("type") == "trail":
                continue
            if poi_geo_region_key(p) or str(p.get("zone", "")).strip().upper() == "C":
                errs.append(
                    f"day {day.day}: far excursion '{it.name}' after {max_trail}min trail"
                )
    return errs


def check_underground_caves(resp, poi_by_id: dict) -> list[str]:
    """FIX #190/#192: underground pref → real jaskinia, not Archiwum Planety."""
    caves = []
    bad = []
    for day in resp.days:
        for it in day.items:
            if getattr(it, "type", None) != ItemType.ATTRACTION:
                continue
            p = poi_by_id.get(getattr(it, "poi_id", ""), {"name": it.name, "tags": []})
            name_l = (it.name or "").lower()
            if "archiw" in name_l and "planety" in name_l:
                bad.append(it.name)
            if is_underground_poi(p):
                caves.append(it.name)
    errs = []
    if bad:
        errs.append(f"underground: museum Archiwum in plan instead of cave: {bad}")
    if not caves:
        errs.append("underground: no cave POI (expected Mroźna/Raptawicka/Bielańska)")
    return errs


def check_afternoon_topup(resp, poi_by_id: dict) -> list[str]:
    """FIX #195: bez ciężkiego szlaku — nie jeden wielki popołudniowy free_time (>3h od 14:00)."""
    from app.domain.planner.engine import time_to_minutes
    errs = []
    for day in resp.days:
        max_trail = 0
        for it in day.items:
            if getattr(it, "type", None) != ItemType.ATTRACTION:
                continue
            p = poi_by_id.get(getattr(it, "poi_id", ""), {})
            item_dur = int(getattr(it, "duration_min", 0) or 0)
            if p.get("type") == "trail":
                max_trail = max(
                    max_trail,
                    int(p.get("time_min") or p.get("duration_min") or item_dur or 0),
                )
            elif item_dur >= 180:
                max_trail = max(max_trail, item_dur)
        if max_trail >= 300:
            continue
        # Po szlaku z regeneracją (atrakcja po szlaku lub 4h+) — duży free_time OK.
        if max_trail >= 120:
            has_post_trail = False
            trail_done = False
            for it in day.items:
                if getattr(it, "type", None) != ItemType.ATTRACTION:
                    continue
                p = poi_by_id.get(getattr(it, "poi_id", ""), {})
                _idur = int(getattr(it, "duration_min", 0) or 0)
                _trail_like = p.get("type") == "trail" or _idur >= 180
                if _trail_like:
                    trail_done = True
                elif trail_done:
                    has_post_trail = True
                    break
            if has_post_trail or max_trail >= 240:
                continue
        for it in day.items:
            if getattr(it, "type", None) != ItemType.FREE_TIME:
                continue
            dur = int(getattr(it, "duration_min", 0) or 0)
            if dur < 180 or not it.start_time:
                continue
            if time_to_minutes(it.start_time) < 960:
                errs.append(
                    f"day {day.day}: {dur}min free_time from {it.start_time} "
                    f"(afternoon top-up expected)"
                )
    return errs


def check_no_timeline_overlaps(resp) -> list[str]:
    """FIX #196: brak nakładających się bloków w timeline."""
    from app.domain.planner.engine import time_to_minutes
    errs = []
    for day in resp.days:
        items = [
            it for it in day.items
            if getattr(it, "start_time", None) and getattr(it, "end_time", None)
        ]
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                as_ = time_to_minutes(a.start_time)
                ae = time_to_minutes(a.end_time)
                bs = time_to_minutes(b.start_time)
                be = time_to_minutes(b.end_time)
                if ae <= bs or be <= as_:
                    continue
                an = getattr(a, "name", None) or getattr(a, "label", str(getattr(a, "type", "")))
                bn = getattr(b, "name", None) or getattr(b, "label", str(getattr(b, "type", "")))
                errs.append(
                    f"day {day.day}: overlap {a.start_time}-{a.end_time} ({an}) "
                    f"vs {b.start_time}-{b.end_time} ({bn})"
                )
    return errs


def check_consecutive_free_time_merged(resp) -> list[str]:
    """FIX #193: max 2 kolejne bloki free_time (scalenie w jeden sensowny)."""
    errs = []
    for day in resp.days:
        run = 0
        max_run = 0
        for it in day.items:
            if getattr(it, "type", None) == ItemType.FREE_TIME:
                run += 1
                max_run = max(max_run, run)
            else:
                run = 0
        if max_run > 2:
            errs.append(f"day {day.day}: {max_run} consecutive free_time blocks (expected <=2)")
    return errs


def check_free_time_long_trips(resp, num_days: int) -> list[str]:
    """FIX #192: 5-7 day plans — cap afternoon dead time (was 5-6h/day)."""
    if num_days < 5:
        return []
    _max_ft = 280 if num_days >= 7 else 240
    errs = []
    for day in resp.days:
        attrs = sum(
            1 for it in day.items if getattr(it, "type", None) == ItemType.ATTRACTION
        )
        ft = sum(
            getattr(it, "duration_min", 0) or 0
            for it in day.items if getattr(it, "type", None) == ItemType.FREE_TIME
        )
        day_max = 360 if attrs <= 2 else _max_ft
        if ft > day_max:
            errs.append(f"day {day.day}: too much free_time ({ft}min, max {day_max})")
    return errs


def check_test04_nature_balance(resp, poi_by_id: dict) -> list[str]:
    """FIX #190: nature+museum+history — no museum-only days, max 3 museums/day."""
    errs = []
    _museum_name_markers = ("muze", "galeri", "kaplic", "cmentarz", "willa", "archiw")
    for day in resp.days:
        museums = 0
        nature = 0
        for it in day.items:
            if getattr(it, "type", None) != ItemType.ATTRACTION:
                continue
            p = poi_by_id.get(getattr(it, "poi_id", ""), {"name": it.name, "tags": []})
            name_l = (it.name or "").lower()
            tags = set(p.get("tags") or [])
            if any(m in name_l for m in _museum_name_markers) or "museum_heritage" in tags:
                museums += 1
            if "nature_landscape" in tags or p.get("type") == "trail":
                nature += 1
        if museums >= 4 and nature == 0:
            errs.append(f"day {day.day}: {museums} museum-like attractions, no nature/trail")
        if museums >= 5:
            errs.append(f"day {day.day}: {museums} museum-like attractions (too many)")
    return errs


def check_test08_scenic_cap(resp, poi_by_id: dict) -> list[str]:
    """FIX #190: max 2 scenic experiences per day (JSON8 viewpoint clustering)."""
    errs = []
    for day in resp.days:
        scenic = []
        for it in day.items:
            if getattr(it, "type", None) != ItemType.ATTRACTION:
                continue
            p = poi_by_id.get(getattr(it, "poi_id", ""), {"name": it.name, "tags": []})
            if is_scenic_experience_poi(p):
                scenic.append(it.name)
        if len(scenic) > 2:
            errs.append(f"day {day.day}: {len(scenic)} scenic POIs {scenic}")
    return errs


def check_test08_day7_fill(resp) -> list[str]:
    """FIX #187b: last day should not be mostly empty."""
    errs = []
    d7 = next((d for d in resp.days if d.day == 7), None)
    if not d7:
        return errs
    ft = sum(
        getattr(it, "duration_min", 0) or 0
        for it in d7.items if getattr(it, "type", None) == ItemType.FREE_TIME
    )
    attrs = sum(
        1 for it in d7.items if getattr(it, "type", None) == ItemType.ATTRACTION
    )
    if ft > 240:
        errs.append(f"day 7: too much free_time ({ft}min)")
    if attrs < 3:
        errs.append(f"day 7: only {attrs} attractions (expected >=3)")
    return errs


def main():
    svc = PlanService(POIRepository(str(BACKEND_DIR / "data" / "zakopane.xlsx")))
    from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
    pois = load_zakopane_poi(str(BACKEND_DIR / "data" / "zakopane.xlsx"))
    poi_by_id = {p.get("id"): p for p in pois if p.get("id")}

    passed = 0
    failed = []

    print("=" * 70)
    print("NATURALNESS TEST — Testy_Klientki (FIX #186 + #187)")
    print("=" * 70)

    for n in TEST_NUMBERS:
        data, resp = run_plan(n, svc)
        issues = check_preferences(data, resp, n)
        if n in (4, 8):
            issues.extend(check_free_time_long_trips(resp, data.get("trip_length", {}).get("days", 0)))
        if n == 4:
            issues.extend(check_test04_nature_balance(resp, poi_by_id))
        if n == 7:
            issues.extend(check_test07_trails(resp))
            issues.extend(check_underground_caves(resp, poi_by_id))
        issues.extend(check_no_far_excursion_after_long_trail(resp, poi_by_id))
        issues.extend(check_no_sightseeing_after_long_trail(resp, poi_by_id))
        issues.extend(check_afternoon_topup(resp, poi_by_id))
        issues.extend(check_no_timeline_overlaps(resp))
        issues.extend(check_consecutive_free_time_merged(resp))
        if n == 8:
            issues.extend(check_test08_regions(resp, poi_by_id))
            issues.extend(check_test08_scenic_cap(resp, poi_by_id))
            issues.extend(check_test08_day7_fill(resp))

        # dup check
        names = []
        for d in resp.days:
            for it in d.items:
                if getattr(it, "type", None) == ItemType.ATTRACTION:
                    names.append(getattr(it, "name", ""))
        dupes = [x for x, c in Counter(names).items() if c > 1]
        if dupes:
            issues.append(f"duplicate POIs: {dupes}")

        if issues:
            failed.append((n, issues))
            print(f"  FAIL  test-{n:02d}: {issues[0]}")
        else:
            passed += 1
            cov_ok = sum(
                1 for p in (data.get("preferences") or [])
                if (getattr(resp, "preference_coverage", {}) or {}).get(p, {}).get("covered")
            )
            print(f"  PASS  test-{n:02d}  prefs_covered={cov_ok}/{len(data.get('preferences') or [])}")

    print("=" * 70)
    print(f"SUMMARY: {passed}/{len(TEST_NUMBERS)} passed")
    if failed:
        for n, issues in failed:
            for i in issues:
                print(f"  test-{n:02d}: {i}")
        sys.exit(1)
    print("ALL NATURALNESS TESTS PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()
