"""
Quick overlap check - verify no attractions exceed day_end after buffer fix
"""
import sys
sys.path.append('c:\\Users\\matte\\Desktop\\Backend Developer (Python) - silnik planowania podróży\\travel-planner-backend')

from app.domain.planner.engine import build_day, time_to_minutes
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi


def quick_overlap_check():
    print("Quick Overlap Check - Post-fix verification")
    print("="*80)
    
    pois = load_zakopane_poi('data/zakopane.xlsx')
    print(f"Loaded {len(pois)} POIs\n")
    
    # Test 3 different user profiles
    test_cases = [
        {
            "name": "Family",
            "user": {"target_group": "family_kids", "group_size": 4, "daily_limit": 400},
            "context": {
                "season": "summer",
                "date": "2026-07-15",
                "weather": {"condition": "sunny", "temp": 25},
                "has_car": True,
                "daylight_start": "05:00",
                "daylight_end": "21:00"
            }
        },
        {
            "name": "Seniors",
            "user": {"target_group": "seniors", "group_size": 2, "daily_limit": 250},
            "context": {
                "season": "summer",
                "date": "2026-07-16",
                "weather": {"condition": "sunny", "temp": 23},
                "has_car": True,
                "daylight_start": "05:00",
                "daylight_end": "21:00"
            }
        },
        {
            "name": "Couple",
            "user": {"target_group": "couples", "group_size": 2, "daily_limit": 300},
            "context": {
                "season": "summer",
                "date": "2026-07-17",
                "weather": {"condition": "sunny", "temp": 24},
                "has_car": True,
                "daylight_start": "05:00",
                "daylight_end": "21:00"
            }
        }
    ]
    
    all_passed = True
    
    for test in test_cases:
        print(f"\nTest: {test['name']}")
        print("-" * 40)
        
        plan = build_day(pois, test['user'], test['context'])
        
        # Find day_end
        day_end_items = [item for item in plan if item.get('type') == 'accommodation_end']
        if day_end_items:
            day_end_str = day_end_items[0]['start_time']
            day_end_min = time_to_minutes(day_end_str)
            print(f"Day end: {day_end_str}")
        else:
            print("WARNING: No accommodation_end found")
            continue
        
        # Check all timed events
        events = [item for item in plan if 'start_time' in item and 'end_time' in item]
        print(f"Total events: {len(events)}")
        
        # Check for overlaps and day_end violations
        overlaps = []
        exceeds_day_end = []
        
        for i, event in enumerate(events):
            end_min = time_to_minutes(event['end_time'])
            
            # Check if exceeds day_end
            if end_min > day_end_min:
                exceeds_day_end.append({
                    'event': event,
                    'end_min': end_min,
                    'day_end_min': day_end_min,
                    'excess': end_min - day_end_min
                })
            
            # Check overlaps with other events
            start1 = time_to_minutes(event['start_time'])
            end1 = end_min
            
            for j in range(i+1, len(events)):
                event2 = events[j]
                start2 = time_to_minutes(event2['start_time'])
                end2 = time_to_minutes(event2['end_time'])
                
                if start1 < end2 and end1 > start2:
                    overlaps.append((event, event2))
        
        # Report results
        if not overlaps and not exceeds_day_end:
            print("[PASS] No overlaps, no day_end violations")
        else:
            all_passed = False
            
            if overlaps:
                print(f"[FAIL] Found {len(overlaps)} overlap(s)")
                for event1, event2 in overlaps[:3]:  # Show first 3
                    print(f"  - {event1['type']} ({event1['start_time']}-{event1['end_time']}) overlaps with {event2['type']} ({event2['start_time']}-{event2['end_time']})")
            
            if exceeds_day_end:
                print(f"[FAIL] Found {len(exceeds_day_end)} event(s) exceeding day_end")
                for item in exceeds_day_end[:3]:  # Show first 3
                    event = item['event']
                    print(f"  - {event['type']} ends at {event['end_time']} (day_end: {day_end_str}, excess: {item['excess']} min)")
    
    print("\n" + "="*80)
    if all_passed:
        print("[SUCCESS] All tests passed - no overlaps, no day_end violations")
    else:
        print("[FAILURE] Some tests failed - see details above")
    print("="*80)
    
    return all_passed


if __name__ == "__main__":
    success = quick_overlap_check()
    sys.exit(0 if success else 1)
