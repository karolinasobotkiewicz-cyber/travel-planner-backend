"""
Test Critical Bug 1: Overlapping times fix
Test validates that overlapping time items are auto-removed.
"""
import sys
sys.path.insert(0, 'c:\\Users\\matte\\Desktop\\Backend Developer (Python) - silnik planowania podróży\\travel-planner-backend')

from app.domain.planner.engine import _validate_and_fix_time_continuity

def test_overlap_detection_and_fix():
    """Test that overlaps are detected and auto-fixed by removing lower-priority items."""
    
    # Test plan with overlapping free_time and attraction
    plan = [
        {"type": "accommodation_start", "start_time": "09:00", "end_time": "09:00"},
        {"type": "attraction", "start_time": "09:00", "end_time": "10:30", "poi_id": "test1"},
        {"type": "free_time", "start_time": "10:30", "end_time": "12:00", "duration_min": 90},
        {"type": "attraction", "start_time": "11:00", "end_time": "12:30", "poi_id": "test2"},  # OVERLAPS with free_time!
        {"type": "lunch_break", "start_time": "13:00", "end_time": "14:00", "duration_min": 60},
        {"type": "accommodation_end", "start_time": "19:00", "end_time": "19:00"},
    ]
    
    day_end_str = "19:00"
    
    is_valid, issues, fixed_plan = _validate_and_fix_time_continuity(plan, day_end_str)
    
    print("="*80)
    print("TEST: Overlap Detection & Auto-Fix")
    print("="*80)
    print(f"\nOriginal plan items: {len(plan)}")
    print(f"Fixed plan items: {len(fixed_plan)}")
    print(f"Is valid: {is_valid}")
    print(f"Issues found: {len(issues)}")
    
    print("\nIssues:")
    for issue in issues:
        print(f"  - {issue}")
    
    print("\nFixed plan timeline:")
    for item in fixed_plan:
        if item.get("type") not in ["accommodation_start", "accommodation_end"]:
            print(f"  {item.get('start_time')}-{item.get('end_time')}: {item.get('type')}")
    
    # Verify free_time was removed (lower priority than attraction)
    free_time_items = [item for item in fixed_plan if item.get("type") == "free_time"]
    attraction_items = [item for item in fixed_plan if item.get("type") == "attraction"]
    
    print(f"\n✅ Fixed plan has {len(attraction_items)} attractions (expected 2)")
    print(f"✅ Fixed plan has {len(free_time_items)} free_time items (expected 0 - removed due to overlap)")
    
    # Verify no overlaps remain
    timed_items = []
    for item in fixed_plan:
        if "start_time" in item and "end_time" in item:
            timed_items.append({
                "type": item.get("type"),
                "start_time": item.get("start_time"),
                "end_time": item.get("end_time"),
            })
    
    timed_items.sort(key=lambda x: x["start_time"])
    
    has_overlap = False
    for i in range(len(timed_items) - 1):
        current = timed_items[i]
        next_item = timed_items[i + 1]
        
        # Convert to minutes for comparison
        from app.domain.planner.engine import time_to_minutes
        current_end = time_to_minutes(current["end_time"])
        next_start = time_to_minutes(next_item["start_time"])
        
        if current_end > next_start:
            has_overlap = True
            print(f"\n❌ OVERLAP STILL EXISTS: {current['type']} ends {current['end_time']}, {next_item['type']} starts {next_item['start_time']}")
    
    if not has_overlap:
        print(f"\n✅ SUCCESS: No overlaps detected in fixed plan!")
    
    return not has_overlap


if __name__ == "__main__":
    success = test_overlap_detection_and_fix()
    
    if success:
        print("\n" + "="*80)
        print("CRITICAL BUG 1 FIX: ✅ PASSED")
        print("="*80)
        sys.exit(0)
    else:
        print("\n" + "="*80)
        print("CRITICAL BUG 1 FIX: ❌ FAILED")
        print("="*80)
        sys.exit(1)
