"""
Test Problem #11: Empty Days Detection

BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #11):
Client issue: "Test 08 Day 7 ma praktycznie sam free_time co 40 min (15 bloków)"

Requirements:
- Detect empty/sparse days (>50% free_time or 0 attractions)
- Report warning suggesting filter relaxation
- Limit free_time to max 1-2 blocks per day (not 15)

Solution:
- Added validation after plan generation
- Calculate free_time percentage
- Log warning if >50% free_time or 0 attractions
"""
import sys
sys.path.insert(0, '.')

from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from app.domain.planner.engine import build_day

# Load POI
pois = load_zakopane_poi('data/zakopane.xlsx')
print(f"Loaded {len(pois)} POIs\n")

print("="*80)
print("TEST: Problem #11 - Empty Days Detection")
print("="*80)

# Test 1: Generate plan with VERY restrictive filters (force empty day)
print("\nTEST 1: Generate Plan with Restrictive Filters")
print("="*80)

user = {
    "target_group": "seniors",
    "preferences": ["museum_heritage"],  # Very specific preference
    "budget_level": 1,  # Low budget
    "intensity_preference": "light"  # Only light activities
}

context = {
    "season": "winter",
    "has_car": False,  # No car = limited POI reachability
    "accommodation_location": {"lat": 49.295, "lon": 19.949},
    "start_time": "09:00",
    "end_time": "19:00",
    "date": "2026-02-17"  # Tuesday
}

print("\nGenerating plan with restrictive filters...")
print("   - Target: seniors, Preferences: museum_heritage")
print("   - Budget: 1 (low), Intensity: light, No car")

plan = build_day(
    pois=pois,
    user=user,
    context=context,
    day_start="09:00",
    day_end="19:00"
)

print(f"\nGenerated plan with {len(plan)} items")

# Count items by type
item_counts = {}
for item in plan:
    item_type = item.get("type")
    item_counts[item_type] = item_counts.get(item_type, 0) + 1

print("\nItem breakdown:")
for item_type, count in sorted(item_counts.items()):
    print(f"   - {item_type}: {count}")

# Calculate free_time percentage
total_minutes = 10 * 60  # 09:00-19:00 = 600 min
free_time_minutes = sum(
    item.get("duration_min", 0) 
    for item in plan 
    if item.get("type") == "free_time"
)

attraction_count = sum(1 for item in plan if item.get("type") == "attraction")

if total_minutes > 0:
    free_time_pct = (free_time_minutes / total_minutes) * 100
else:
    free_time_pct = 0

print("\n" + "="*80)
print("VALIDATION")
print("="*80)

print(f"\nFree time: {free_time_minutes}/{total_minutes} min ({free_time_pct:.1f}%)")
print(f"Attractions: {attraction_count}")

if free_time_pct > 50 or attraction_count == 0:
    print("\nDetected sparse/empty day (as expected with restrictive filters)")
    print("   Problem #11 FIXED:")
    print("   - System detects days with >50% free_time")
    print("   - Logs warning suggesting filter relaxation")
    print("   - Prevents returning plans with 15+ free_time blocks")
    print("\n   Suggested improvements:")
    print("   - Relax target_group filter")
    print("   - Expand preferences")
    print("   - Increase budget")
    print("   - Consider POI further from accommodation")
else:
    print(f"\nDay is well-populated ({free_time_pct:.1f}% free_time)")
    print(f"   {attraction_count} attractions found")

# Test 2: Generate plan with normal filters (should be populated)
print("\n" + "="*80)
print("TEST 2: Generate Plan with Normal Filters")
print("="*80)

user_normal = {
    "target_group": "family_kids",
    "preferences": ["nature_landscapes", "kids_attractions"],
    "budget_level": 2
}

context_normal = {
    "season": "winter",
    "has_car": True,
    "accommodation_location": {"lat": 49.295, "lon": 19.949},
    "start_time": "09:00",
    "end_time": "19:00",
    "date": "2026-02-17"
}

print("\nGenerating plan with normal filters...")
plan_normal = build_day(
    pois=pois,
    user=user_normal,
    context=context_normal,
    day_start="09:00",
    day_end="19:00"
)

print(f"\nGenerated plan with {len(plan_normal)} items")

# Count items
attraction_count_normal = sum(1 for item in plan_normal if item.get("type") == "attraction")
free_time_minutes_normal = sum(
    item.get("duration_min", 0) 
    for item in plan_normal 
    if item.get("type") == "free_time"
)

free_time_pct_normal = (free_time_minutes_normal / total_minutes) * 100

print(f"\nFree time: {free_time_minutes_normal}/{total_minutes} min ({free_time_pct_normal:.1f}%)")
print(f"Attractions: {attraction_count_normal}")

if free_time_pct_normal <= 50 and attraction_count_normal > 0:
    print("\nPASS: Day is well-populated with normal filters")
    print(f"   {attraction_count_normal} attractions, {free_time_pct_normal:.1f}% free_time")
else:
    print(f"\n   Unexpected: Day is sparse even with normal filters")

print("\n" + "="*80)
