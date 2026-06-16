"""
FIX #203 (16.06.2026) regression guard.

Locks in the client-reported fixes:
  1. preference_coverage classification (false positives + false negatives).
  2. region_type="cluster" activates multi-city cluster mode (no single-city stick).
  3. No transit endpoints referencing POIs absent from the timeline.
  4. No item scheduled past the daily day_end window.

Run: python test_fix203.py   (exits non-zero on any failure)
Zakopane + multi-city density regressions are validated separately.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date
from app.application.services.plan_service import PlanService
from app.domain.models.plan import ItemType
from app.domain.models.trip_input import (
    TripInput, LocationInput, GroupInput, BudgetInput,
    TripLengthInput, DailyTimeWindow,
)
from app.infrastructure.repositories.poi_repository import POIRepository
from app.infrastructure.repositories.load_multi_city import load_multi_city_poi
from app.domain.scoring.preference_coverage import poi_covers_preference_report
from app.domain.planner.engine import time_to_minutes

MC = os.path.join("data", "multi_city_attractions.xlsx")

# (city, name fragment, preference, expected covered)
COVERAGE_CASES = [
    ("Kraków", "Smoka Wawelskiego", "nature_landscape", False),
    ("Kraków", "Smoka Wawelskiego", "history_mystery", False),
    ("Kraków", "Bernatka", "nature_landscape", False),
    ("Kraków", "Podziemia Rynku", "kids_attractions", False),
    ("Kraków", "Rynek Główny", "history_mystery", False),
    ("Warszawa", "Łazienki", "relaxation", True),
    ("Warszawa", "Polskiej Wódki", "local_food_experience", True),
    ("Warszawa", "Multimedialny Park Fontann", "water_attractions", True),
    ("Warszawa", "Norblina", "nature_landscape", False),
    ("Warszawa", "Plac Europejski", "nature_landscape", False),
    ("Wrocław", "Sky Tower", "nature_landscape", False),
    ("Wrocław", "Hydropolis", "nature_landscape", False),
    ("Wrocław", "Most Grunwaldzki", "nature_landscape", False),
    ("Wrocław", "Fontanna Multimedialna", "nature_landscape", False),
    ("Wrocław", "Pana Tadeusza", "museum_heritage", True),
    ("Wrocław", "Centrum Historii Zajezdnia", "museum_heritage", True),
    ("Wrocław", "Ostrów Tumski", "history_mystery", True),
    ("Gdańsk", "Ulica Długa", "nature_landscape", False),
    ("Gdańsk", "Długi Targ", "nature_landscape", False),
    ("Gdańsk", "Marina Gdańsk", "nature_landscape", False),
    ("Gdynia", "ORP Błyskawica", "museum_heritage", True),
    ("Gdynia", "Dar Pomorza", "museum_heritage", True),
    ("Katowice", "Ogród Zoologiczny", "active_sport", False),
    ("Kłodzko", "Stare Miasto", "nature_landscape", False),
    ("Kłodzko", "Twierdza Kłodzko", "history_mystery", True),
    ("Kudowa-Zdrój", "Błędne Skały", "history_mystery", False),
    ("Kudowa-Zdrój", "Szczeliniec", "nature_landscape", True),
]

_pool_cache = {}


def _pois(city):
    if city not in _pool_cache:
        _pool_cache[city] = load_multi_city_poi(MC, [city])
    return _pool_cache[city]


def check_coverage():
    fails = []
    for city, frag, pref, expected in COVERAGE_CASES:
        match = next(
            (p for p in _pois(city) if frag.lower() in str(p.get("name", "")).lower()),
            None,
        )
        if match is None:
            fails.append(f"{city}/{frag}: POI not found")
            continue
        got = poi_covers_preference_report(match, pref)
        if got != expected:
            fails.append(f"{city}/{frag} [{pref}]: got {got}, expected {expected}")
    return fails


def _cluster_trip(city, days=3, style="balanced", group="couples", prefs=None):
    return TripInput(
        location=LocationInput(city=city, country="Poland", region_type="cluster"),
        group=GroupInput(type=group, size=2),
        preferences=prefs or ["museum_heritage", "history_mystery"],
        travel_style=style,
        budget=BudgetInput(level=2, daily_limit=500),
        trip_length=TripLengthInput(days=days, start_date=date(2026, 7, 1)),
        daily_time_window=DailyTimeWindow(start="09:00", end="19:00"),
        transport_modes=["car"],
    )


def _timeline_issues(resp, day_end_min):
    issues = []
    for day in resp.days:
        attr_names = {
            getattr(it, "name", "")
            for it in day.items
            if getattr(it, "type", None) == ItemType.ATTRACTION
        }
        for it in day.items:
            et = getattr(it, "end_time", None)
            if et and time_to_minutes(et) > day_end_min:
                issues.append(f"day {day.day}: item past day_end ({et})")
            if getattr(it, "type", None) == ItemType.TRANSIT:
                frm = getattr(it, "from_location", "") or ""
                to = getattr(it, "to_location", "") or ""
                if to and to not in attr_names:
                    issues.append(f"day {day.day}: transit to absent POI '{to}'")
    return issues


def check_cluster_and_timeline(svc):
    fails = []
    checks = [
        ("Gdańsk", 3), ("Sopot", 3), ("Szklarska Poręba", 3), ("Kłodzko", 2),
    ]
    for city, days in checks:
        trip = _cluster_trip(city, days=days)
        resp = svc.generate_plan(trip)
        cities = {
            (getattr(it, "city", "") or "").strip()
            for d in resp.days for it in d.items
            if getattr(it, "type", None) == ItemType.ATTRACTION
        }
        cities.discard("")
        if len(cities) < 2:
            fails.append(f"{city}: cluster stuck in single city ({cities})")
        fails.extend(f"{city}: {x}" for x in _timeline_issues(resp, time_to_minutes("19:00")))
    return fails


def test_fix203_regression_guard():
    """Pytest entry point: fails the suite if any FIX #203 check regresses."""
    svc = PlanService(POIRepository(os.path.join("data", "zakopane.xlsx")))
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cov_fails = check_coverage()
        tl_fails = check_cluster_and_timeline(svc)
    assert not cov_fails, "coverage regressions:\n" + "\n".join(cov_fails)
    assert not tl_fails, "cluster/timeline regressions:\n" + "\n".join(tl_fails)


def main():
    print("=" * 70)
    print("FIX #203 regression guard")
    print("=" * 70)
    svc = PlanService(POIRepository(os.path.join("data", "zakopane.xlsx")))

    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cov_fails = check_coverage()
        tl_fails = check_cluster_and_timeline(svc)

    ok = True
    if cov_fails:
        ok = False
        print(f"  FAIL coverage ({len(cov_fails)}):")
        for f in cov_fails:
            print(f"    - {f}")
    else:
        print(f"  PASS coverage ({len(COVERAGE_CASES)} cases)")
    if tl_fails:
        ok = False
        print(f"  FAIL cluster/timeline ({len(tl_fails)}):")
        for f in tl_fails:
            print(f"    - {f}")
    else:
        print("  PASS cluster activation + no transit orphans + no day_end overflow")

    print("=" * 70)
    if ok:
        print("ALL FIX #203 CHECKS PASSED")
    else:
        print("FIX #203 CHECKS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
