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
from app.domain.planner.engine import poi_geo_region_key
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


def main():
    svc = PlanService(POIRepository(str(BACKEND_DIR / "data" / "zakopane.xlsx")))
    from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
    pois = load_zakopane_poi(str(BACKEND_DIR / "data" / "zakopane.xlsx"))
    poi_by_id = {p.get("id"): p for p in pois if p.get("id")}

    passed = 0
    failed = []

    print("=" * 70)
    print("NATURALNESS TEST — Testy_Klientki (FIX #186)")
    print("=" * 70)

    for n in TEST_NUMBERS:
        data, resp = run_plan(n, svc)
        issues = check_preferences(data, resp, n)
        if n == 7:
            issues.extend(check_test07_trails(resp))
        if n == 8:
            issues.extend(check_test08_regions(resp, poi_by_id))

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
