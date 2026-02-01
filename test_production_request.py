"""
Test the same request that causes 500 error in production
"""
import sys
sys.path.insert(0, '.')

from app.domain.models.trip_input import TripInput, LocationInput, GroupInput, TripLengthInput, DailyTimeWindow, BudgetInput
from app.application.services.plan_service import PlanService
from app.infrastructure.repositories import POIRepository
from app.domain.planner.engine import Engine
from datetime import date

# Recreate exact request from production
trip_data = {
    "location": {
        "city": "Zakopane",
        "country": "Poland",
        "region_type": "mountain"
    },
    "group": {
        "type": "family_kids",
        "size": 4,
        "children_age": 8,
        "crowd_tolerance": 2
    },
    "trip_length": {
        "days": 1,
        "start_date": date(2026, 2, 10)
    },
    "daily_time_window": {
        "start": "09:00",
        "end": "18:00"
    },
    "budget": {
        "level": 2,
        "daily_limit": None
    },
    "transport_modes": ["car"],
    "preferences": [],
    "travel_style": "balanced"
}

try:
    print("Creating TripInput...")
    trip_input = TripInput(**trip_data)
    
    print("Loading POIs...")
    poi_repo = POIRepository()
    all_pois = poi_repo.get_all()
    print(f"Loaded {len(all_pois)} POIs")
    
    print("Creating Engine...")
    engine = Engine(all_pois)
    
    print("Creating PlanService...")
    plan_service = PlanService(engine, poi_repo)
    
    print("Generating plan...")
    plan = plan_service.generate_plan(trip_input)
    
    print(f"\n✅ SUCCESS! Generated plan with {len(plan.days[0].items)} items")
    print(f"First item: {plan.days[0].items[0].type}")
    
except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()
