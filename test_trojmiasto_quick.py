"""Quick test for Trójmiasto cluster"""
import sys
from datetime import date
from app.domain.models.trip_input import (
    TripInput, LocationInput, GroupInput, BudgetInput,
    TripLengthInput, DailyTimeWindow
)
from app.application.services.plan_service import PlanService
from app.api.dependencies import get_poi_repository

print("Testing Trójmiasto cluster...")

poi_repository = get_poi_repository()
plan_service = PlanService(poi_repository)

trip_input = TripInput(
    location=LocationInput(
        city="Trójmiasto",
        country="Poland",
        region_type="urban",
        is_cluster=True
    ),
    trip_length=TripLengthInput(
        days=2,
        start_date=date(2026, 7, 1)
    ),
    daily_time_window=DailyTimeWindow(
        start="09:00",
        end="19:00"
    ),
    group=GroupInput(
        type="friends",
        size=4
    ),
    budget=BudgetInput(
        total_budget=1200.0,
        currency="PLN"
    ),
    preferences=["culture", "beach"],
    travel_style="balanced",
    transport_modes=["car"]
)

try:
    plan = plan_service.generate_plan(trip_input)
    print(f"Success: {len(plan.days)} days generated")
    for i, day in enumerate(plan.days, 1):
        print(f"  Day {i}: {len(day.items)} items")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
