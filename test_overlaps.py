"""
Test for Problem #2: Overlapping Events Validation

CLIENT FEEDBACK (16.02.2026):
Test 08 Day 6 has free_time + museum simultaneously (overlapping events).

This test verifies that no events overlap in the daily plan.
"""
import sys
sys.path.append('c:\\Users\\matte\\Desktop\\Backend Developer (Python) - silnik planowania podróży\\travel-planner-backend')

from app.domain.planner.engine import build_day, time_to_minutes
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi


def check_overlaps(plan):
    """
    Check if any events in the plan overlap.
    
    Returns:
        list: List of overlapping pairs [(item1, item2), ...]
    """
    overlaps = []
    
    # Get events with time ranges
    events = [item for item in plan if 'start_time' in item and 'end_time' in item]
    
    for i, event1 in enumerate(events):
        start1 = time_to_minutes(event1['start_time'])
        end1 = time_to_minutes(event1['end_time'])
        
        for event2 in events[i+1:]:
            start2 = time_to_minutes(event2['start_time'])
            end2 = time_to_minutes(event2['end_time'])
            
            # Check overlap: event1 starts before event2 ends AND event1 ends after event2 starts
            if start1 < end2 and end1 > start2:
                overlaps.append((event1, event2))
    
    return overlaps


def test_no_overlaps():
    """Test that build_day produces no overlapping events."""
    print("="*80)
    print("OVERLAP TEST - Problem #2 (CLIENT FEEDBACK 16.02.2026)")
    print("="*80)
    
    # Load POIs
    pois = load_zakopane_poi('data/zakopane.xlsx')
    print(f"Loaded {len(pois)} POIs\n")
    
    # Test different user profiles (similar to client's TEST 01-10)
    test_users = [
        {
            "name": "TEST 01 - Family",
            "user": {
                "target_group": "family_kids",
                "group_size": 4,
                "children_age": 8,
                "daily_limit": 400,
                "preferences": {
                    "pace": "moderate",
                    "interests": ["nature", "culture", "family"]
                }
            }
        },
        {
            "name": "TEST 02 - Couple",
            "user": {
                "target_group": "couples",
                "group_size": 2,
                "daily_limit": 300,
                "preferences": {
                    "pace": "moderate",
                    "interests": ["nature", "culture", "romance"]
                }
            }
        },
        {
            "name": "TEST 08 - Friends",
            "user": {
                "target_group": "friends",
                "group_size": 3,
                "daily_limit": 250,
                "preferences": {
                    "pace": "active",
                    "interests": ["adventure", "culture"]
                }
            }
        }
    ]
    
    context = {
        "season": "summer",
        "date": "2026-07-15",
        "weather": {
            "condition": "sunny",
            "temp": 25,
            "wind_speed": 10
        },
        "has_car": True,
        "daylight_start": "05:00",
        "daylight_end": "21:00"
    }
    
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    
    for test_case in test_users:
        test_name = test_case["name"]
        user = test_case["user"]
        
        print(f"\n{'='*80}")
        print(f"{test_name}: {user['target_group']}, {user['group_size']} persons")
        print(f"{'='*80}")
        
        # Build day plan
        plan = build_day(pois, user, context)
        
        # Check for overlaps
        overlaps = check_overlaps(plan)
        
        total_tests += 1
        
        if overlaps:
            failed_tests += 1
            print(f"\n[FAIL] Found {len(overlaps)} overlapping event(s)\n")
            
            for i, (event1, event2) in enumerate(overlaps, 1):
                print(f"  Overlap #{i}:")
                print(f"    Event 1: {event1.get('type')} '{event1.get('name', event1.get('description', 'N/A'))}' ({event1['start_time']} - {event1['end_time']})")
                print(f"    Event 2: {event2.get('type')} '{event2.get('name', event2.get('description', 'N/A'))}' ({event2['start_time']} - {event2['end_time']})")
                print()
        else:
            passed_tests += 1
            print(f"\n[PASS] No overlapping events\n")
            
            # Show plan summary
            events = [item for item in plan if 'start_time' in item and 'end_time' in item]
            print(f"Plan has {len(events)} timed events - all time-valid (no overlaps)")
    
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"Total tests: {total_tests}")
    print(f"[PASS] Passed: {passed_tests}")
    print(f"[FAIL] Failed: {failed_tests}")
    print(f"\n{'[PASS] ALL TESTS PASSED' if failed_tests == 0 else '[FAIL] SOME TESTS FAILED'}")
    print(f"{'='*80}")
    
    return failed_tests == 0


if __name__ == "__main__":
    success = test_no_overlaps()
    sys.exit(0 if success else 1)
