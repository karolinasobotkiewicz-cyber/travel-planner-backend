"""
Test FULL pipeline: build_day() + simulate PlanService transit timing
This should reproduce the EXACT production scenario with gap.
"""
import sys
sys.path.insert(0, ".")

from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from app.domain.planner.engine import build_day, fill_plan_gaps
from app.domain.planner.time_utils import time_to_minutes, minutes_to_time
from datetime import date

print("=" * 80)
print("SIMULATING FULL PIPELINE - WITH PARKING")
print("=" * 80)

# Load POI
all_pois = load_zakopane_poi("data/zakopane.xlsx")

# Find specific POI
dino_park = next((p for p in all_pois if 'DINO PARK' in p['name']), None)
zoo = next((p for p in all_pois if 'Zoo' in p['name']), None)

if not dino_park or not zoo:
    print("❌ POI not found!")
    sys.exit(1)

# Context
context = {
    "date": date(2026, 2, 16),
    "season": "winter",
    "weather": {"temp": 5, "condition": "cloudy"}
}

user = {
    "target_group": "family_kids",
    "interests": ["dinozaury", "zoo"],
    "budget_level": "medium",
    "has_car": True
}

# Force algorithm to select DINO + Zoo by manipulating scores
# Increase must_see for these POI
for poi in all_pois:
    if poi['id'] == dino_park['id']:
        poi['must_see'] = 10  # Force high priority
        poi['time_min'] = 122  # Production duration
    elif poi['id'] == zoo['id']:
        poi['must_see'] = 10
        poi['time_min'] = 30
    else:
        poi['must_see'] = 1  # Lower priority for others

print("\n1. CALLING build_day()...")
raw_plan = build_day(
    pois=all_pois,
    user=user,
    context=context,
    day_start="10:00",
    day_end="18:00"
)

print(f"✓ Raw plan generated with {len(raw_plan)} items")

# Display raw plan
print("\nRAW PLAN (from build_day):")
for i, item in enumerate(raw_plan):
    if item['type'] == 'attraction':
        print(f"  {i}. {item['name']}: {item['start_time']}-{item['end_time']}")
    elif item['type'] == 'transfer':
        print(f"  {i}. transfer: {item.get('from', '?')} → {item.get('to', '?')} ({item['duration_min']} min)")
        print(f"      NO start_time/end_time in raw plan!")
    else:
        print(f"  {i}. {item['type']}")

# Simulate PlanService transit timing calculation
print("\n" + "=" * 80)
print("2. SIMULATING PlanService TRANSIT TIMING:")
print("=" * 80)

# PlanService adds parking first
parking_duration = 15
walk_time = dino_park.get('parking_walk_time_min', 1)

print(f"\nParking: 10:00-10:15 (15 min)")
print(f"Walk time: {walk_time} min")
print(f"First attraction adjusted start: {minutes_to_time(600 + parking_duration + walk_time)}")

# Iterate through plan and calculate transit times like PlanService does
items_with_times = []
last_end_time = "10:00"

for item in raw_plan:
    if item['type'] == 'accommodation_start':
        items_with_times.append({
            'type': 'day_start',
            'time': item['time']
        })
        last_end_time = item['time']
        
    elif item['type'] == 'parking':
        # Simulated parking
        items_with_times.append({
            'type': 'parking',
            'start_time': last_end_time,
            'end_time': minutes_to_time(time_to_minutes(last_end_time) + parking_duration),
            'walk_time': walk_time
        })
        last_end_time = minutes_to_time(time_to_minutes(last_end_time) + parking_duration + walk_time)
        
    elif item['type'] == 'attraction':
        # Adjust first attraction start time
        if len(items_with_times) == 1:  # First attraction after day_start
            # Add simulated parking
            parking_end = minutes_to_time(time_to_minutes(last_end_time) + parking_duration)
            items_with_times.append({
                'type': 'parking',
                'start_time': last_end_time,
                'end_time': parking_end,
                'walk_time': walk_time
            })
            # First attraction starts after parking + walk
            start_time = minutes_to_time(time_to_minutes(parking_end) + walk_time)
            end_time = minutes_to_time(time_to_minutes(start_time) + item['duration_min'])
        else:
            start_time = item['start_time']
            end_time = item['end_time']
        
        items_with_times.append({
            'type': 'attraction',
            'name': item['name'],
            'start_time': start_time,
            'end_time': end_time,
            'duration_min': item['duration_min']
        })
        last_end_time = end_time
        
    elif item['type'] == 'transfer':
        # PlanService calculates transit times from last_end_time
        start_time = last_end_time
        duration = item['duration_min']
        end_time = minutes_to_time(time_to_minutes(start_time) + duration)
        
        items_with_times.append({
            'type': 'transit',
            'from': item.get('from'),
            'to': item.get('to'),
            'start_time': start_time,
            'end_time': end_time,
            'duration_min': duration
        })
        last_end_time = end_time

print("\nFINAL PLAN (with PlanService times):")
for i, item in enumerate(items_with_times):
    print(f"\n{i}. {item['type'].upper()}")
    
    if item['type'] in ['attraction', 'transit', 'parking']:
        print(f"   {item['start_time']} - {item['end_time']}")
        if 'name' in item:
            print(f"   {item['name']}")
        if 'from' in item:
            print(f"   {item['from']} → {item.get('to', '?')}")
    
    # Check for gaps
    if item['type'] == 'transit' and i < len(items_with_times) - 1:
        next_item = items_with_times[i + 1]
        if next_item['type'] == 'attraction':
            transit_end_min = time_to_minutes(item['end_time'])
            next_start_min = time_to_minutes(next_item['start_time'])
            gap = next_start_min - transit_end_min
            
            if gap > 20:
                print(f"\n   ❌❌❌ GAP DETECTED: {gap} min")
                print(f"   Transit ends: {item['end_time']} ({transit_end_min} min)")
                print(f"   {next_item['name']} starts: {next_item['start_time']} ({next_start_min} min)")
                print(f"   THIS SHOULD HAVE BEEN FILLED BY fill_plan_gaps()!")
            elif gap > 0:
                print(f"   ⚠️ Small gap: {gap} min")

print("\n" + "=" * 80)
print("CONCLUSION:")
print("=" * 80)
print("If you see '❌❌❌ GAP DETECTED' above, gap filling failed!")
print("The raw plan from build_day() has NO gaps (transfer times align with next attraction).")
print("But PlanService adds parking, which shifts times and creates gaps.")
print("\nSOLUTION: fill_plan_gaps() must run AFTER PlanService adds parking,")
print("OR build_day() must account for parking when calculating attraction start times!")

