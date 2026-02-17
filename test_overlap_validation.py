"""
Test - Overlapping Events Validation (CLIENT FEEDBACK Problem #2)

Tests that engine prevents overlapping events in daily plan.
Client reported: Test 08 Day 6 had free_time + museum simultaneously.
"""
import sys
sys.path.append('c:\\Users\\matte\\Desktop\\Backend Developer (Python) - silnik planowania podróży\\travel-planner-backend')

from app.domain.planner.engine import build_day, _check_time_overlap

print("="*80)
print("OVERLAP VALIDATION TEST (CLIENT FEEDBACK Problem #2)")
print("="*80)

# Test 1: _check_time_overlap function
print("\n1. UNIT TEST: _check_time_overlap function")
print("-" * 80)

plan = [
    {"type": "accommodation_start", "time": "09:00"},
    {"type": "attraction", "start_time": "09:30", "end_time": "11:00"},
    {"type": "lunch_break", "start_time": "13:00", "end_time": "14:00"},
]

# Test case 1: No overlap (before first attraction)
overlaps, conflict = _check_time_overlap(plan, "09:00", "09:20")
print(f"Test 1a: 09:00-09:20 (before attraction)")
print(f"  Result: {'❌ OVERLAP' if overlaps else '✅ NO OVERLAP'}")
assert not overlaps, "Should not overlap"

# Test case 2: Overlap with attraction (exact match)
overlaps, conflict = _check_time_overlap(plan, "09:30", "11:00")
print(f"\nTest 1b: 09:30-11:00 (exact match with attraction)")
print(f"  Result: {'❌ OVERLAP' if overlaps else '✅ NO OVERLAP'}")
assert overlaps, "Should overlap"
print(f"  Conflicting item: {conflict.get('type')}")

# Test case 3: Overlap with attraction (partial)
overlaps, conflict = _check_time_overlap(plan, "10:30", "11:30")
print(f"\nTest 1c: 10:30-11:30 (partial overlap with attraction)")
print(f"  Result: {'❌ OVERLAP' if overlaps else '✅ NO OVERLAP'}")
assert overlaps, "Should overlap"

# Test case 4: No overlap (between attraction and lunch)
overlaps, conflict = _check_time_overlap(plan, "11:30", "12:30")
print(f"\nTest 1d: 11:30-12:30 (between attraction and lunch)")
print(f"  Result: {'❌ OVERLAP' if overlaps else '✅ NO OVERLAP'}")
assert not overlaps, "Should not overlap"

# Test case 5: Overlap with lunch
overlaps, conflict = _check_time_overlap(plan, "13:30", "14:30")
print(f"\nTest 1e: 13:30-14:30 (partial overlap with lunch)")
print(f"  Result: {'❌ OVERLAP' if overlaps else '✅ NO OVERLAP'}")
assert overlaps, "Should overlap"

print("\n✅ All unit tests PASSED")

# Test 2: Integration test with build_day
print("\n\n2. INTEGRATION TEST: build_day prevents overlaps")
print("-" * 80)

# Create mock POI data
mock_pois = [
    {
        "id": "poi_1",
        "name": "Muzeum Tatrzańskie",
        "Name": "Muzeum Tatrzańskie",
        "type": "museum",
        "priority_level": 12,  # Core POI
        "must_see": 9,
        "must_see_score": 9,
        "time_min": 60,
        "time_max": 120,
        "intensity": "low",
        "target_groups": ["couples", "families", "seniors"],
        "kids_only": False,
        "ticket_price": 15,
        "free_entry": False,
        "Lat": 49.2962,
        "Lng": 19.9496,
        "Opening hours": {
            "mon": "09:00-17:00",
            "tue": "09:00-17:00",
            "wed": "09:00-17:00",
            "thu": "09:00-17:00",
            "fri": "09:00-17:00",
            "sat": "09:00-17:00",
            "sun": "09:00-17:00",
        },
        "opening_hours_seasonal": None,
        "seasonality": "all_year",
    },
    {
        "id": "poi_2",
        "name": "Krupówki",
        "Name": "Krupówki",
        "type": "street",
        "priority_level": 10,
        "must_see": 8,
        "must_see_score": 8,
        "time_min": 30,
        "time_max": 90,
        "intensity": "low",
        "target_groups": ["couples", "families", "seniors"],
        "kids_only": False,
        "ticket_price": 0,
        "free_entry": True,
        "Lat": 49.2955,
        "Lng": 19.9500,
        "Opening hours": {
            "mon": "00:00-23:59",
            "tue": "00:00-23:59",
            "wed": "00:00-23:59",
            "thu": "00:00-23:59",
            "fri": "00:00-23:59",
            "sat": "00:00-23:59",
            "sun": "00:00-23:59",
        },
        "opening_hours_seasonal": None,
        "seasonality": "all_year",
    },
]

user = {
    "target_group": "couples",
    "group_size": 2,
    "daily_limit": 300,
}

context = {
    "season": "winter",
    "date": "2026-02-16",
    "has_car": True,
}

# Build day plan
plan = build_day(mock_pois, user, context, day_start="09:00", day_end="17:00")

print(f"\nGenerated plan with {len(plan)} items:")
print(f"{'Type':<20} {'Start':<10} {'End':<10} {'Name':<30}")
print("-" * 80)

# Check for overlaps in generated plan
has_overlap_error = False
for i, item in enumerate(plan):
    if "start_time" not in item or "end_time" not in item:
        print(f"{item.get('type', 'unknown'):<20} {item.get('time', 'N/A'):<10} {'N/A':<10} {'':<30}")
        continue
    
    start = item.get("start_time")
    end = item.get("end_time")
    name = item.get("name", item.get("description", ""))
    
    print(f"{item.get('type', 'unknown'):<20} {start:<10} {end:<10} {name:<30}")
    
    # Check if this item overlaps with any previous item
    for j in range(i):
        prev_item = plan[j]
        if "start_time" not in prev_item or "end_time" not in prev_item:
            continue
        
        overlaps, _ = _check_time_overlap([prev_item], start, end)
        if overlaps:
            print(f"  ❌ OVERLAP ERROR: Overlaps with item {j} ({prev_item.get('type')} {prev_item.get('start_time')}-{prev_item.get('end_time')})")
            has_overlap_error = True

if has_overlap_error:
    print("\n❌ FAIL: Plan contains overlapping events")
else:
    print("\n✅ PASS: No overlapping events detected")

print("\n\n" + "="*80)
print("SUMMARY")
print("="*80)
print("✅ _check_time_overlap function works correctly")
print(f"{'✅' if not has_overlap_error else '❌'} build_day generates plan without overlaps")
print("\n📝 This fixes CLIENT FEEDBACK issue #2 (16.02.2026)")
print("📝 BUGFIX: Overlap validation prevents simultaneous events")
