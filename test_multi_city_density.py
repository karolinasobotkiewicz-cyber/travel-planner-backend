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
from app.domain.planner.engine import time_to_minutes


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
    svc = PlanService(POIRepository(str(BACKEND_DIR / "data" / "zakopane.xlsx")))
    cities = ["Kraków", "Warszawa", "Wrocław", "Gdańsk", "Poznań"]
    passed = 0
    failed = []

    print("=" * 70)
    print("MULTI-CITY DENSITY TEST — FIX #194")
    print("=" * 70)

    for city in cities:
        try:
            resp = svc.generate_plan(_trip(city, days=3))
            issues = check_day_density(resp)
            prefs_ok = all(
                (resp.preference_coverage or {}).get(p, {}).get("covered")
                for p in ("museum_heritage", "local_food_experience", "history_mystery")
            )
            if not prefs_ok:
                issues.append("preference coverage incomplete")
            if issues:
                failed.append((city, issues))
                print(f"  FAIL  {city}: {issues[0]}")
            else:
                passed += 1
                print(f"  PASS  {city}")
        except Exception as e:
            failed.append((city, [str(e)]))
            print(f"  FAIL  {city}: {e}")

    print("=" * 70)
    print(f"SUMMARY: {passed}/{len(cities)} passed")
    if failed:
        for city, issues in failed:
            print(f"  {city}: {issues}")
        sys.exit(1)
    print("ALL MULTI-CITY DENSITY TESTS PASSED")


if __name__ == "__main__":
    main()
