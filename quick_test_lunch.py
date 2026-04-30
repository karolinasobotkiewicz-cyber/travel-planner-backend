import sys
sys.path.insert(0, '.')
from pathlib import Path
import json
from app.domain.planner.engine import plan_multiple_days
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from app.api.routes.trip_mapper import trip_input_to_engine_params
from app.domain.models.plan import TripInput

# Load test file
test_file = Path('../Testy_Klientki/test-02.json')
print(f"Loading {test_file}...")
with open(test_file, 'r', encoding='utf-8') as f:
    test_data = json.load(f)

trip_input = TripInput(**test_data)
params = trip_input_to_engine_params(trip_input)
poi_list = load_zakopane_poi('data/zakopane.xlsx')
print(f"Loaded {len(poi_list)} POI")

contexts = [params['context']] * params['num_days']
print(f"Planning {params['num_days']} days for {params['user']['target_group']}...")

result = plan_multiple_days(
    pois=poi_list,
    user=params['user'],
    contexts=contexts,
    day_start=params['day_start'],
    day_end=params['day_end']
)

# Check lunch times
print(f"\n{'='*60}")
print("LUNCH TIMING VERIFICATION (FIX #14)")
print(f"{'='*60}")
lunch_found = False
for day_idx, day in enumerate(result, 1):
    for item in day.get('items', []):
        if item.get('type') == 'lunch_break':
            lunch_time = item.get('start_time', 'N/A')
            h, m = map(int, lunch_time.split(':'))
            lunch_min = h * 60 + m
            
            # Expected: 12:00-14:30 (720-870 min)
            if 720 <= lunch_min <= 870:
                print(f"✅ Day {day_idx}: Lunch at {lunch_time} (PASS - within 12:00-14:30)")
            else:
                print(f"❌ Day {day_idx}: Lunch at {lunch_time} (FAIL - should be 12:00-14:30)")
            lunch_found = True

if not lunch_found:
    print("⚠️ No lunches found in plan")
