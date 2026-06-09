"""
FIX #191 — multi-city day count + strict preference coverage.

1. Warszawa 3-day request must NOT collapse to 1 day (FIX #112 zone-min bug).
2. Warsaw POIs must not falsely cover wrong preferences in coverage report.
"""
import contextlib
import io
import sys
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).parent
sys.path.insert(0, str(BACKEND_DIR))

from app.application.services.plan_service import PlanService
from app.domain.models.trip_input import (
    TripInput, LocationInput, GroupInput, BudgetInput,
    TripLengthInput, DailyTimeWindow,
)
from app.domain.scoring.preference_coverage import poi_covers_preference_report
from app.infrastructure.repositories.poi_repository import POIRepository
from app.infrastructure.repositories.load_multi_city import load_multi_city_poi

WARSAW_CASES = [
    ("Most Świętokrzyski", {"nature_landscape", "local_food_experience", "kids_attractions"}),
    ("Muzeum Świat Iluzji", {"nature_landscape", "kids_attractions"}),
    ("Ogród Botaniczny Uniwersytetu Warszawskiego", {"kids_attractions"}),
    ("Bulwary Wiślane", {"local_food_experience"}),
]


def test_warsaw_poi_strict_coverage():
    pois = load_multi_city_poi(str(BACKEND_DIR / "data" / "multi_city_attractions.xlsx"), ["Warszawa"])
    errs = []
    for name_part, forbidden_prefs in WARSAW_CASES:
        p = next((x for x in pois if name_part in x.get("name", "")), None)
        if not p:
            errs.append(f"missing POI: {name_part}")
            continue
        for pref in forbidden_prefs:
            if poi_covers_preference_report(p, pref):
                errs.append(f"{p['name']} wrongly covers {pref} (tags_excel={p.get('tags_excel')})")
        if not poi_covers_preference_report(p, "nature_landscape") and "Botaniczny" in name_part:
            errs.append(f"{p['name']} should cover nature_landscape")
    if errs:
        for e in errs:
            print(f"  FAIL  {e}")
        sys.exit(1)
    print("  PASS  Warsaw strict coverage cases")


def test_warsaw_multi_day_not_collapsed():
    svc = PlanService(POIRepository(str(BACKEND_DIR / "data" / "zakopane.xlsx")))
    trip = TripInput(
        location=LocationInput(city="Warszawa", country="Poland", region_type="urban", is_cluster=False),
        group=GroupInput(type="couples", size=2),
        preferences=["culture", "museums", "local_food_experience"],
        travel_style="balanced",
        budget=BudgetInput(total_budget=2000.0, currency="PLN"),
        trip_length=TripLengthInput(days=3, start_date=date(2026, 7, 1)),
        daily_time_window=DailyTimeWindow(start="09:00", end="20:00"),
        transport_modes=["car"],
    )
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        resp = svc.generate_plan(trip)
    if len(resp.days) < 3:
        print(f"  FAIL  Warszawa 3-day plan collapsed to {len(resp.days)} day(s)")
        sys.exit(1)
    shortage = [w for w in (resp.warnings or []) if w.get("type") == "poi_shortage"]
    if shortage:
        print(f"  FAIL  unexpected poi_shortage: {shortage[0].get('message', '')[:80]}")
        sys.exit(1)
    print(f"  PASS  Warszawa plan kept {len(resp.days)} days")


def main():
    print("=" * 70)
    print("PREFERENCE COVERAGE + MULTI-DAY — FIX #191")
    print("=" * 70)
    test_warsaw_poi_strict_coverage()
    test_warsaw_multi_day_not_collapsed()
    print("=" * 70)
    print("ALL FIX #191 TESTS PASSED")


if __name__ == "__main__":
    main()
