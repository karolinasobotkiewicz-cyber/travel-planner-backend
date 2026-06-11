"""
FIX #194 — multi-city day density (non-Zakopane).

Ensures modest POI pools fill days with >=2 attractions and <60% free_time on 3-day trips.
Zakopane regression: run test_naturalness_klientka.py separately.
"""
import sys
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from app.application.services.plan_service import PlanService
from app.domain.models.plan import ItemType
from app.domain.models.trip_input import (
    TripInput, LocationInput, GroupInput, BudgetInput,
    TripLengthInput, DailyTimeWindow,
)
from app.infrastructure.repositories.poi_repository import POIRepository
from collections import Counter

from app.domain.planner.engine import (
    calculate_poi_cost_for_group,
    is_park_or_green_space_poi,
    time_to_minutes,
)


def _trip(city: str, days: int = 3) -> TripInput:
    return TripInput(
        location=LocationInput(
            city=city, country="Poland", region_type="urban", is_cluster=False,
        ),
        group=GroupInput(type="couples", size=2),
        preferences=["museum_heritage", "local_food_experience", "history_mystery"],
        travel_style="balanced",
        budget=BudgetInput(total_budget=2000.0, currency="PLN"),
        trip_length=TripLengthInput(days=days, start_date=date(2026, 7, 1)),
        daily_time_window=DailyTimeWindow(start="09:00", end="20:00"),
        transport_modes=["car"],
    )


def check_no_overlaps(resp) -> list[str]:
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
                if not (ae <= bs or be <= as_):
                    errs.append(f"day {day.day}: timeline overlap")
    return errs


def check_city_limits(resp, poi_by_id: dict, max_attrs: int = 6, max_parks: int = 2) -> list[str]:
    errs = []
    for day in resp.days:
        attrs = 0
        parks = 0
        for it in day.items:
            if getattr(it, "type", None) != ItemType.ATTRACTION:
                continue
            attrs += 1
            p = poi_by_id.get(getattr(it, "poi_id", ""), {})
            if is_park_or_green_space_poi(p):
                parks += 1
        if attrs > max_attrs:
            errs.append(f"day {day.day}: {attrs} attractions (max {max_attrs})")
        if parks > max_parks:
            errs.append(f"day {day.day}: {parks} parks (max {max_parks})")
    return errs


def check_no_duplicate_pois(resp) -> list[str]:
    ids = []
    for d in resp.days:
        for it in d.items:
            if getattr(it, "type", None) == ItemType.ATTRACTION and getattr(it, "poi_id", ""):
                ids.append(it.poi_id)
    dupes = [x for x, c in Counter(ids).items() if c > 1]
    return [f"duplicate poi_ids: {dupes}"] if dupes else []


def check_budget(resp, user: dict, daily_limit: float) -> list[str]:
    errs = []
    for day in resp.days:
        cost = 0.0
        for it in day.items:
            if getattr(it, "type", None) != ItemType.ATTRACTION:
                continue
            cost += calculate_poi_cost_for_group(
                {"ticket_normal": getattr(it, "ticket_price", None), "free_entry": False},
                user,
            )
        if cost > daily_limit * 1.05:
            errs.append(f"day {day.day}: cost {cost:.0f} > limit {daily_limit}")
    return errs


def check_day_density(resp, day_start: str = "09:00", day_end: str = "20:00") -> list[str]:
    errs = []
    window = max(time_to_minutes(day_end) - time_to_minutes(day_start), 1)
    for day in resp.days:
        attrs = sum(
            1 for it in day.items
            if getattr(it, "type", None) == ItemType.ATTRACTION
        )
        ft = sum(
            (getattr(it, "duration_min", 0) or 0)
            for it in day.items
            if getattr(it, "type", None) == ItemType.FREE_TIME
        )
        ratio = ft / window
        if attrs < 2:
            errs.append(f"day {day.day}: only {attrs} attractions")
        if ratio > 0.60:
            errs.append(f"day {day.day}: {int(ratio * 100)}% free_time")
    return errs


def main():
    from app.infrastructure.repositories.load_multi_city import load_multi_city_poi

    svc = PlanService(POIRepository(str(BACKEND_DIR / "data" / "zakopane.xlsx")))
    mc_path = str(BACKEND_DIR / "data" / "multi_city_attractions.xlsx")
    poi_by_id = {}
    for c in ("Kraków", "Warszawa", "Wrocław", "Katowice"):
        for p in load_multi_city_poi(mc_path, [c]):
            if p.get("id"):
                poi_by_id[p["id"]] = p

    cities = ["Kraków", "Warszawa", "Wrocław", "Gdańsk", "Poznań", "Katowice"]
    passed = 0
    failed = []

    print("=" * 70)
    print("MULTI-CITY DENSITY TEST — FIX #194 + #197 + #198")
    print("=" * 70)

    from app.domain.scoring.preference_coverage import poi_covers_preference_report

    # FIX #198: GPS/address must survive normalize merge
    _wawa = load_multi_city_poi(mc_path, ["Warszawa"])
    _bad_gps = [
        p for p in _wawa
        if not p.get("lat") or not p.get("lng") or not p.get("city")
    ]
    if _bad_gps:
        failed.append(("Warszawa-GPS", [f"{len(_bad_gps)} POI bez lat/lng/city"]))
        print(f"  FAIL  Warszawa-GPS: {len(_bad_gps)} POI bez współrzędnych")
    else:
        passed += 1
        print("  PASS  Warszawa-GPS (coords preserved)")

    # FIX #198: urban landmarks ≠ nature_landscape in coverage report
    _deny_names = ("Pałac Kultury", "Pomnik Syreny")
    _cov_bad = []
    for p in _wawa:
        nm = p.get("name", "")
        if any(d in nm for d in _deny_names):
            if poi_covers_preference_report(p, "nature_landscape"):
                _cov_bad.append(nm)
    if _cov_bad:
        failed.append(("coverage-deny", _cov_bad))
        print(f"  FAIL  coverage-deny: {_cov_bad}")
    else:
        passed += 1
        print("  PASS  coverage-deny (PKiN/Syrenka)")

    for city in cities:
        try:
            trip = _trip(city, days=3)
            resp = svc.generate_plan(trip)
            city_pois = load_multi_city_poi(mc_path, [city])
            city_poi_by_id = {p.get("id"): p for p in city_pois if p.get("id")}
            issues = check_day_density(resp)
            issues.extend(check_no_overlaps(resp))
            issues.extend(check_city_limits(resp, {**poi_by_id, **city_poi_by_id}))
            issues.extend(check_no_duplicate_pois(resp))
            prefs = ("museum_heritage", "local_food_experience", "history_mystery")
            for pref in prefs:
                pool_has = any(
                    poi_covers_preference_report(p, pref) for p in city_pois
                )
                if pool_has and not (resp.preference_coverage or {}).get(pref, {}).get("covered"):
                    issues.append(f"preference '{pref}' not covered")
            if issues:
                failed.append((city, issues))
                print(f"  FAIL  {city}: {issues[0]}")
            else:
                passed += 1
                print(f"  PASS  {city}")
        except Exception as e:
            failed.append((city, [str(e)]))
            print(f"  FAIL  {city}: {e}")

    # FIX #197: 5-day Kraków — no repeat POIs across trip
    try:
        trip5 = _trip("Kraków", days=5)
        trip5.preferences = ["museum_heritage", "nature_landscape", "history_mystery"]
        resp5 = svc.generate_plan(trip5)
        issues5 = check_no_duplicate_pois(resp5)
        issues5.extend(check_city_limits(resp5, poi_by_id))
        if issues5:
            failed.append(("Kraków-5d", issues5))
            print(f"  FAIL  Kraków-5d: {issues5[0]}")
        else:
            passed += 1
            print("  PASS  Kraków-5d (no dupes)")
    except Exception as e:
        failed.append(("Kraków-5d", [str(e)]))
        print(f"  FAIL  Kraków-5d: {e}")

    print("=" * 70)
    total = len(cities) + 3
    print(f"SUMMARY: {passed}/{total} passed")
    if failed:
        for city, issues in failed:
            print(f"  {city}: {issues}")
        sys.exit(1)
    print("ALL MULTI-CITY DENSITY TESTS PASSED")


if __name__ == "__main__":
    main()
