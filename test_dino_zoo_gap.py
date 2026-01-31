"""
Reproduce EXACT production gap issue - force DINO PARK + Zoo selection
"""
import sys
sys.path.insert(0, ".")

from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from datetime import date

print("=" * 80)
print("LOADING POI...")
print("=" * 80)

all_pois = load_zakopane_poi("data/zakopane.xlsx")

# Find DINO PARK and Zoo
dino_park = next((p for p in all_pois if 'DINO PARK' in p['name']), None)
zoo = next((p for p in all_pois if 'Zoo' in p['name']), None)

if not dino_park:
    print("❌ DINO PARK not found!")
    sys.exit(1)
if not zoo:
    print("❌ Zoo not found!")
    sys.exit(1)

print(f"✓ Found DINO PARK: opening_hours={dino_park['opening_hours']}")
print(f"✓ Found Zoo: opening_hours={zoo['opening_hours']}\n")

# Build a minimal plan with just these 2 POI
from app.domain.planner.time_utils import time_to_minutes, minutes_to_time
from app.domain.planner.engine import travel_time_minutes

# Simulate production context
context = {
    "date": date(2026, 2, 16),  # Monday from production test
    "season": "winter",
    "weather": {"temp": 5, "condition": "cloudy"}
}

user = {
    "target_group": "family_kids",
    "interests": ["dinozaury", "zoo"],
    "budget_level": "medium",
    "has_car": True
}

# Manual plan building
print("=" * 80)
print("SIMULATING PRODUCTION PLAN WITH DINO PARK + ZOO:")
print("=" * 80)

day_start = "10:00"
start_min = time_to_minutes(day_start)

# 1. DINO PARK first (opens at 10:00)
dino_start_min = start_min
# Use longer duration like production (2h+ for family with kids)
dino_duration = 122  # From production: 600 to 722 = 122 min
dino_end_min = dino_start_min + dino_duration

print(f"\n1. DINO PARK")
print(f"   Opens: {dino_park['opening_hours']['mon']}")
print(f"   Start: {minutes_to_time(dino_start_min)}")
print(f"   Duration: {dino_duration} min")
print(f"   End: {minutes_to_time(dino_end_min)}")

# 2. TRANSFER DINO -> Zoo
travel_duration = travel_time_minutes(dino_park, zoo, user)
transfer_start_min = dino_end_min
transfer_end_min = transfer_start_min + travel_duration

print(f"\n2. TRANSFER (DINO -> Zoo)")
print(f"   Start: {minutes_to_time(transfer_start_min)}")
print(f"   Duration: {travel_duration} min")
print(f"   End: {minutes_to_time(transfer_end_min)}")

# 3. ZOO
# Check opening hours for Monday
zoo_opens = zoo['opening_hours']['mon'].split('-')[0]  # e.g., "08:00"
zoo_opens_min = time_to_minutes(zoo_opens)

# If transfer ends before zoo opens, there's a GAP!
if transfer_end_min < zoo_opens_min:
    gap_min = zoo_opens_min - transfer_end_min
    print(f"\n❌ GAP DETECTED: {gap_min} min")
    print(f"   Transfer ends: {minutes_to_time(transfer_end_min)}")
    print(f"   Zoo opens: {zoo_opens}")
    print(f"   ⚠️ This gap should be filled by fill_plan_gaps()!")
    zoo_start_min = zoo_opens_min
else:
    print(f"\n✓ No gap - Zoo can start immediately")
    zoo_start_min = transfer_end_min

zoo_duration = zoo['time_min']  # 30 min minimum
zoo_end_min = zoo_start_min + zoo_duration

print(f"\n3. ZOO")
print(f"   Opens: {zoo['opening_hours']['mon']}")
print(f"   Start: {minutes_to_time(zoo_start_min)}")
print(f"   Duration: {zoo_duration} min")
print(f"   End: {minutes_to_time(zoo_end_min)}")

# Now test with fill_plan_gaps()
print("\n" + "=" * 80)
print("TESTING fill_plan_gaps() WITH THIS SCENARIO:")
print("=" * 80)

# Build raw plan structure
raw_plan = [
    {"type": "accommodation_start", "time": day_start},
    {
        "type": "attraction",
        "poi": dino_park,
        "name": dino_park['name'],
        "start_time": minutes_to_time(dino_start_min),
        "end_time": minutes_to_time(dino_end_min),
        "duration_min": dino_duration
    },
    {
        "type": "transfer",
        "from": dino_park['name'],
        "to": zoo['name'],
        "duration_min": travel_duration,
        "mode": "car"
    },
    {
        "type": "attraction",
        "poi": zoo,
        "name": zoo['name'],
        "start_time": minutes_to_time(zoo_start_min),
        "end_time": minutes_to_time(zoo_end_min),
        "duration_min": zoo_duration
    },
    {"type": "accommodation_end", "time": "18:00"}
]

print(f"\nRAW PLAN ({len(raw_plan)} items):")
for i, item in enumerate(raw_plan):
    if item['type'] == 'attraction':
        print(f"  {i}. {item['type']}: {item['name']} ({item['start_time']}-{item['end_time']})")
    elif item['type'] == 'transfer':
        print(f"  {i}. {item['type']}: {item['from']} -> {item['to']} ({item['duration_min']} min)")
    else:
        print(f"  {i}. {item['type']}")

# Call fill_plan_gaps()
from app.domain.planner.engine import fill_plan_gaps

filled_plan = fill_plan_gaps(raw_plan, all_pois, set([dino_park['id'], zoo['id']]), context)

print(f"\nFILLED PLAN ({len(filled_plan)} items):")
gap_filled = False
for i, item in enumerate(filled_plan):
    if item['type'] == 'attraction':
        print(f"  {i}. {item['type']}: {item['name']} ({item['start_time']}-{item['end_time']})")
    elif item['type'] == 'transfer':
        print(f"  {i}. {item['type']}: {item.get('from', '?')} -> {item.get('to', '?')} ({item['duration_min']} min)")
    elif item['type'] == 'free_time':
        print(f"  {i}. ✓ FREE_TIME: {item['start_time']}-{item['end_time']} (FILLED GAP!)")
        gap_filled = True
    else:
        print(f"  {i}. {item['type']}")

print("\n" + "=" * 80)
if gap_filled:
    print("✓ GAP FILLING WORKING - free_time added!")
elif len(filled_plan) > len(raw_plan):
    print("✓ GAP FILLING WORKING - soft POI added!")
else:
    print("❌ GAP FILLING NOT WORKING - plan unchanged!")
print("=" * 80)
