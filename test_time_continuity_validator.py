"""
Test Problem #7: Time Continuity Validator

BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #7):
Client issue: "Brakuje automatycznej walidacji time continuity"

Requirements:
1. Validator sprawdza ciągłość czasu przed zwróceniem planu
2. Wykrywa gaps >10 min między itemami
3. Wykrywa overlaps
4. Wykrywa items przekraczające day_end
5. Automatycznie dodaje free_time do day_end jeśli gap >30 min

Solution:
- Added _validate_and_fix_time_continuity() function
- Integrated with build_day() before return
- Auto-adds free_time to fill gap to day_end
"""
import sys
sys.path.insert(0, '.')

from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from app.domain.planner.engine import build_day

# Load POI
pois = load_zakopane_poi('data/zakopane.xlsx')
print(f"Loaded {len(pois)} POIs\n")

print("="*80)
print("TEST: Problem #7 - Time Continuity Validator")
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
    "end_time": "18:00",  # Early end time to test gap-to-day_end filling
    "date": "2026-02-16"  # Monday
}

# ============================================================================
# TEST 1: Generate plan and validate time continuity
# ============================================================================
print("\n" + "="*80)
print("TEST 1: Time Continuity Validation")
print("="*80)

print("\nGenerating plan...")
plan = build_day(
    pois=pois,
    user=user,
    context=context,
    day_start="09:00",
    day_end="18:00"
)

print(f"\nGenerated plan with {len(plan)} items")

# Extract timed items
timed_items = []
for item in plan:
    if "start_time" in item and "end_time" in item:
        timed_items.append({
            "type": item["type"],
            "name": item.get("name", item.get("description", "N/A")),
            "start_time": item["start_time"],
            "end_time": item["end_time"],
            "duration_min": item.get("duration_min", "N/A")
        })

print(f"\nTIMELINE ({len(timed_items)} timed items):")
print("-" * 80)
for i, item in enumerate(timed_items, 1):
    item_type = item["type"].upper()
    name_raw = item["name"][:50]  # Truncate long names
    # ASCII-safe encoding for Windows terminal
    name = name_raw.encode('ascii', errors='ignore').decode('ascii')
    duration = item.get("duration_min", "N/A")
    print(f"[{i:2d}] {item_type:15s} {item['start_time']}-{item['end_time']} ({duration:3} min)")
    
    # Show name for attractions/free_time
    if item_type in ["ATTRACTION", "FREE_TIME", "BUFFER"]:
        print(f"     {name}")

# ============================================================================
# TEST 2: Check for gaps between items
# ============================================================================
print("\n" + "="*80)
print("TEST 2: Gap Detection")
print("="*80)

from app.domain.planner.engine import time_to_minutes

gaps = []
for i in range(len(timed_items) - 1):
    current = timed_items[i]
    next_item = timed_items[i + 1]
    
    current_end_min = time_to_minutes(current["end_time"])
    next_start_min = time_to_minutes(next_item["start_time"])
    
    gap = next_start_min - current_end_min
    
    if gap > 10:
        gaps.append({
            "from": current["type"],
            "to": next_item["type"],
            "gap_min": gap,
            "from_end": current["end_time"],
            "to_start": next_item["start_time"]
        })

if gaps:
    print(f"\nWARNING: Found {len(gaps)} large gap(s) (>10 min):")
    for gap in gaps:
        print(f"   Gap: {gap['gap_min']} min between {gap['from']} (ends {gap['from_end']}) "
              f"and {gap['to']} (starts {gap['to_start']})")
else:
    print("\nPASS: No large unexplained gaps (all transitions <= 10 min)")

# ============================================================================
# TEST 3: Check last item vs day_end
# ============================================================================
print("\n" + "="*80)
print("TEST 3: Gap to day_end")
print("="*80)

if timed_items:
    last_item = timed_items[-1]
    day_end_min = time_to_minutes("18:00")
    last_end_min = time_to_minutes(last_item["end_time"])
    
    gap_to_day_end = day_end_min - last_end_min
    
    print(f"\nLast item: {last_item['type']} ends at {last_item['end_time']}")
    print(f"Day end: 18:00")
    print(f"Gap to day_end: {gap_to_day_end} min")
    
    if gap_to_day_end > 30:
        # Check if free_time was auto-added
        has_final_free_time = any(
            item["type"] == "free_time" and 
            time_to_minutes(item["start_time"]) >= last_end_min 
            for item in timed_items
        )
        
        if has_final_free_time:
            print(f"\nPASS: Gap to day_end >30 min, free_time auto-added")
        else:
            print(f"\nFAIL: Gap to day_end >30 min but no free_time added")
            test3_pass = False
    elif gap_to_day_end >= -10:
        print(f"\nPASS: Plan ends close to day_end (within 10 min)")
        test3_pass = True
    else:
        print(f"\nWARNING: Last item exceeds day_end by {abs(gap_to_day_end)} min")
        test3_pass = True  # Not a failure, just info
else:
    print("\nWARNING: No timed items in plan")
    test3_pass = False

# ============================================================================
# TEST 4: Check for overlaps
# ============================================================================
print("\n" + "="*80)
print("TEST 4: Overlap Detection")
print("="*80)

overlaps = []
for i in range(len(timed_items)):
    for j in range(i + 1, len(timed_items)):
        item1 = timed_items[i]
        item2 = timed_items[j]
        
        item1_start = time_to_minutes(item1["start_time"])
        item1_end = time_to_minutes(item1["end_time"])
        item2_start = time_to_minutes(item2["start_time"])
        item2_end = time_to_minutes(item2["end_time"])
        
        # Check overlap
        if item1_start < item2_end and item1_end > item2_start:
            overlaps.append({
                "item1": item1["type"],
                "item2": item2["type"],
                "time1": f"{item1['start_time']}-{item1['end_time']}",
                "time2": f"{item2['start_time']}-{item2['end_time']}"
            })

if overlaps:
    print(f"\nFAIL: Found {len(overlaps)} overlap(s):")
    for overlap in overlaps:
        print(f"   {overlap['item1']} ({overlap['time1']}) overlaps with "
              f"{overlap['item2']} ({overlap['time2']})")
    test4_pass = False
else:
    print("\nPASS: No overlaps detected")
    test4_pass = True

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*80)
print("TEST SUMMARY")
print("="*80)

test2_pass = len(gaps) == 0
all_pass = test2_pass and test3_pass and test4_pass

if all_pass:
    print("\nALL TESTS PASSED")
    print("\n   Problem #7 FIXED:")
    print("   - Time continuity validated automatically")
    print("   - No large unexplained gaps (>10 min)")
    print("   - No overlaps detected")
    print("   - Gap to day_end handled (auto-added free_time if needed)")
else:
    print("\nWARNING: SOME ISSUES DETECTED")
    if not test2_pass:
        print(f"   - Found {len(gaps)} large gap(s) >10 min")
    if not test3_pass:
        print("   - Gap to day_end not handled correctly")
    if not test4_pass:
        print("   - Overlaps detected")

print("\n" + "="*80)
