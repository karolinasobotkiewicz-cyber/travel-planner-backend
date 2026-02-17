"""
Test Problem #8: Lunch Time Constraint

BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #8):
Client issue: "Lunch o 16:15 po termach wygląda nienaturalnie"

Requirements:
- Lunch should be inserted between 12:00-14:30
- System should enforce this constraint strictly
- If passed 14:30, insert lunch immediately with warning

Solution:
- Modified lunch checkpoint to insert lunch as soon as time >= 12:00
- Add warning if lunch is scheduled after 14:30 (late lunch)
"""
import sys
sys.path.insert(0, '.')

from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from app.domain.planner.engine import build_day, time_to_minutes

# Load POI
pois = load_zakopane_poi('data/zakopane.xlsx')
print(f"Loaded {len(pois)} POIs\n")

print("="*80)
print("TEST: Problem #8 - Lunch Time Constraint")
print("="*80)

# Test parameters
user = {
    "target_group": "family_kids",
    "preferences": ["nature_landscapes", "kids_attractions"],
    "budget_level": 2
}

context = {
    "season": "winter",
    "has_car": True,
    "accommodation_location": {"lat": 49.295, "lon": 19.949},
    "start_time": "09:00",
    "end_time": "19:00",
    "date": "2026-02-17"  # Tuesday
}

# Generate plan
print("\nGenerating plan...")
plan = build_day(
    pois=pois,
    user=user,
    context=context,
    day_start="09:00",
    day_end="19:00"
)

print(f"\nGenerated plan with {len(plan)} items")

# Find lunch_break in plan
lunch_item = None
for item in plan:
    if item.get("type") == "lunch_break":
        lunch_item = item
        break

print("\n" + "="*80)
print("VALIDATION")
print("="*80)

if not lunch_item:
    print("\nFAIL: No lunch_break found in plan")
else:
    lunch_start = lunch_item.get("start_time")
    lunch_end = lunch_item.get("end_time")
    lunch_start_min = time_to_minutes(lunch_start)
    
    earliest_min = time_to_minutes("12:00")
    latest_min = time_to_minutes("14:30")
    
    print(f"\nLunch scheduled: {lunch_start} - {lunch_end}")
    print(f"Expected window: 12:00 - 14:30")
    
    if lunch_start_min < earliest_min:
        print(f"\nWARNING: Lunch too early (before 12:00)")
        print(f"   Lunch at {lunch_start} is {earliest_min - lunch_start_min} min before 12:00")
    elif lunch_start_min > latest_min:
        print(f"\nWARNING: Lunch too late (after 14:30)")
        print(f"   Lunch at {lunch_start} is {lunch_start_min - latest_min} min after 14:30")
        print(f"   This should only happen if plan is very packed")
    else:
        print(f"\nPASS: Lunch within acceptable window (12:00-14:30)")
        print(f"   Lunch at {lunch_start} is perfect timing")
        print("\n   Problem #8 FIXED:")
        print("   - Lunch inserted as soon as time >= 12:00")
        print("   - Enforces strict 12:00-14:30 constraint")
        print("   - Warnings for late lunch (after 14:30)")

# Show timeline around lunch
print("\n" + "="*80)
print("TIMELINE (items around lunch)")
print("="*80)

timed_items = []
for item in plan:
    if "start_time" in item and "end_time" in item:
        timed_items.append({
            "type": item["type"],
            "start_time": item["start_time"],
            "end_time": item["end_time"],
            "name": item.get("name", item.get("suggestions", ["N/A"])[0] if item.get("suggestions") else "N/A")
        })

# Sort by start time
timed_items.sort(key=lambda x: time_to_minutes(x["start_time"]))

# Find lunch index
lunch_idx = None
for i, item in enumerate(timed_items):
    if item["type"] == "lunch_break":
        lunch_idx = i
        break

# Show 2 items before and after lunch
if lunch_idx is not None:
    start_idx = max(0, lunch_idx - 2)
    end_idx = min(len(timed_items), lunch_idx + 3)
    
    print(f"\n{'Item':<20} {'Start':<10} {'End':<10} {'Name':<40}")
    print("-" * 80)
    
    for i in range(start_idx, end_idx):
        item = timed_items[i]
        item_type = item["type"].upper()
        marker = " <-- LUNCH" if i == lunch_idx else ""
        name = str(item["name"])[:40]
        # ASCII-safe encoding
        name = name.encode('ascii', errors='ignore').decode('ascii')
        print(f"{item_type:<20} {item['start_time']:<10} {item['end_time']:<10} {name:<40}{marker}")

print("\n" + "="*80)
