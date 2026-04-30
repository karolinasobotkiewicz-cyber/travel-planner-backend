"""Debug trail limit for test-01.json (family_kids, 3 days)"""

import json
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.domain.models.trip import TripRequest
from app.infrastructure.repositories import POIRepository
from app.application.services.plan_service import PlanService

# Load test-01.json
with open('Testy_Klientki/test-01.json', 'r', encoding='utf-8') as f:
    test_data = json.load(f)

print("="*80)
print("TRAIL LIMIT DEBUG - TEST-01 (family_kids, 3 days)")
print("="*80)
print(f"Input: {test_data['group']['type']}, {test_data['trip_length']['days']} days")
print(f"Expected: max 1 trail (FIX #12: family_kids gets max(1, num_days//4) = max(1, 0) = 1 trail)")
print("="*80)

# Initialize service
poi_repo = POIRepository("data/zakopane.xlsx")
plan_service = PlanService(poi_repo)

# Generate plan
try:
    trip_request = TripRequest(**test_data)
    result = plan_service.generate_plan(trip_request)
    
    print("\nPLAN GENERATED SUCCESSFULLY")
    print("="*80)
    
    # Count trails per day
    for day_idx, day in enumerate(result["days"], 1):
        trails_in_day = [item for item in day["items"] if item.get("type") == "trail"]
        print(f"\nDAY {day_idx}:")
        print(f"  Total items: {len(day['items'])}")
        print(f"  Trails: {len(trails_in_day)}")
        for trail in trails_in_day:
            print(f"    - {trail.get('name')} ({trail.get('difficulty_level')}, {trail.get('duration')}min)")
    
    # Total trail count
    total_trails = sum(1 for day in result["days"] for item in day["items"] if item.get("type") == "trail")
    print(f"\n{'='*80}")
    print(f"TOTAL TRAILS: {total_trails}")
    print(f"EXPECTED: 1 (family_kids, 3 days)")
    print(f"STATUS: {'✅ PASS' if total_trails == 1 else '❌ FAIL'}")
    print("="*80)
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
