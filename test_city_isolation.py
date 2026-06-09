"""
FIX #188 — city isolation + neutral copy for non-Zakopane trips.

Checks:
1. Warsaw/Kraków plans contain no Zakopane-specific suggestion text
2. Attraction city field matches requested city (when set in POI data)
"""
import sys
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from app.domain.models.trip_input import (
    TripInput, LocationInput, GroupInput, BudgetInput,
    TripLengthInput, DailyTimeWindow,
)
from app.application.services.plan_service import PlanService
from app.infrastructure.repositories.poi_repository import POIRepository
from app.domain.planner.city_copy import normalize_city_name, poi_city_norm, poi_hub_norm
from app.domain.models.plan import ItemType

ZAKOPANE_LEAKS = (
    "krupówk", "krupowk", "góralsk", "goralsk", "oscypk",
    "tatry", "zakopane centrum", "bacówka",
)


def _base_trip(city: str, days: int = 3) -> TripInput:
    return TripInput(
        location=LocationInput(
            city=city, country="Poland", region_type="urban", is_cluster=False,
        ),
        group=GroupInput(type="couples", size=2),
        preferences=["culture", "museums", "local_food_experience"],
        travel_style="balanced",
        budget=BudgetInput(total_budget=2000.0, currency="PLN"),
        trip_length=TripLengthInput(days=days, start_date=date(2026, 7, 1)),
        daily_time_window=DailyTimeWindow(start="09:00", end="20:00"),
        transport_modes=["car"],
    )


def check_no_zakopane_copy(resp, city: str) -> list[str]:
    errs = []
    for day in resp.days:
        for it in day.items:
            label = getattr(it, "label", "") or ""
            desc = getattr(it, "description", "") or ""
            sugg = " ".join(getattr(it, "suggestions", []) or [])
            blob = f"{label} {desc} {sugg}".lower()
            for leak in ZAKOPANE_LEAKS:
                if leak in blob:
                    errs.append(f"{city} day{day.day}: Zakopane copy '{leak}' in {label[:40]}")
    return errs


def check_attraction_cities(resp, city: str, poi_by_id: dict) -> list[str]:
    errs = []
    want = normalize_city_name(city)
    for day in resp.days:
        for it in day.items:
            if getattr(it, "type", None) != ItemType.ATTRACTION:
                continue
            p = poi_by_id.get(getattr(it, "poi_id", ""), {})
            ac = normalize_city_name(getattr(it, "city", "") or p.get("city", "") or "")
            hub = poi_hub_norm(p) if p else ""
            # FIX #191: Zone C day-trips keep satellite City (Ojców, Kiścinne) but Hub = trip city.
            if hub == want or ac == want:
                continue
            if ac:
                errs.append(
                    f"{city} day{day.day}: '{it.name}' city={getattr(it,'city','')} hub={hub} (expected {city})"
                )
    return errs


def main():
    svc = PlanService(POIRepository(str(BACKEND_DIR / "data" / "zakopane.xlsx")))
    from app.infrastructure.repositories.load_multi_city import load_multi_city_poi
    mc_pois = load_multi_city_poi(
        str(BACKEND_DIR / "data" / "multi_city_attractions.xlsx"),
        ["Warszawa", "Kraków", "Wrocław", "Gdańsk"],
    )
    poi_by_id = {p.get("id"): p for p in mc_pois if p.get("id")}
    cities = ["Warszawa", "Kraków", "Wrocław", "Gdańsk"]
    passed = 0
    failed = []

    print("=" * 70)
    print("CITY ISOLATION TEST — FIX #188")
    print("=" * 70)

    for city in cities:
        try:
            resp = svc.generate_plan(_base_trip(city, days=3))
            issues = check_no_zakopane_copy(resp, city)
            issues.extend(check_attraction_cities(resp, city, poi_by_id))
            if issues:
                failed.append((city, issues))
                print(f"  FAIL  {city}")
                for i in issues[:5]:
                    print(f"        - {i}")
            else:
                passed += 1
                print(f"  PASS  {city}")
        except Exception as e:
            failed.append((city, [str(e)]))
            print(f"  FAIL  {city}: {e}")

    print("=" * 70)
    print(f"SUMMARY: {passed}/{len(cities)} passed")
    if failed:
        sys.exit(1)
    print("ALL CITY ISOLATION TESTS PASSED")


if __name__ == "__main__":
    main()
