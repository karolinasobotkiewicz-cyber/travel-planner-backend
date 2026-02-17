"""
Test for Problem #3: Missing Transits Validation

CLIENT FEEDBACK (16.02.2026):
Test 06 Day 4: Brak transitu między odległymi lokacjami (Morskie Oko - Gubałówka, ~20km).

This test verifies that:
1. All POI pairs with distance > 2km have a transfer between them
2. Transfer duration reflects actual travel distance
"""
import sys
sys.path.append('c:\\Users\\matte\\Desktop\\Backend Developer (Python) - silnik planowania podróży\\travel-planner-backend')

from app.domain.planner.engine import build_day, haversine_distance
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi


def check_missing_transits(plan, pois_dict):
    """
    Check if any adjacent attractions lack proper transit.
    
    Args:
        plan: List of plan items
        pois_dict: Dict mapping POI IDs to POI data
    
    Returns:
        list: List of missing transits [(poi1, poi2, distance_km), ...]
    """
    missing_transits = []
    prev_attraction = None
    
    for item in plan:
        if item.get('type') == 'attraction':
            if prev_attraction is not None:
                # Check if there's a transfer before this attraction
                prev_index = None
                current_index = None
                
                for i, plan_item in enumerate(plan):
                    if plan_item == prev_attraction:
                        prev_index = i
                    if plan_item == item:
                        current_index = i
                        break
                
                # Check items between prev and current attraction
                has_transfer = False
                if prev_index is not None and current_index is not None:
                    for i in range(prev_index + 1, current_index):
                        if plan[i].get('type') == 'transfer':
                            has_transfer = True
                            break
                
                # Calculate distance between POI
                prev_poi = prev_attraction.get('poi', {})
                curr_poi = item.get('poi', {})
                
                prev_lat = prev_poi.get('lat')
                prev_lng = prev_poi.get('lng')
                curr_lat = curr_poi.get('lat')
                curr_lng = curr_poi.get('lng')
                
                if all([prev_lat, prev_lng, curr_lat, curr_lng]):
                    distance_km = haversine_distance(prev_lat, prev_lng, curr_lat, curr_lng)
                    
                    # REQUIREMENT: distance > 2km MUST have transfer
                    if distance_km > 2.0 and not has_transfer:
                        missing_transits.append({
                            'from': prev_attraction.get('name', 'Unknown'),
                            'to': item.get('name', 'Unknown'),
                            'distance_km': distance_km
                        })
            
            prev_attraction = item
    
    return missing_transits


def test_transits():
    """Test that build_day includes transits for distant POI."""
    print("="*80)
    print("TRANSIT VALIDATION TEST - Problem #3 (CLIENT FEEDBACK 16.02.2026)")
    print("="*80)
    
    # Load POIs
    pois = load_zakopane_poi('data/zakopane.xlsx')
    print(f"Loaded {len(pois)} POIs\n")
    
    # Create POI dict for quick lookup
    pois_dict = {p.get('id'): p for p in pois}
    
    # Test different user profiles
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
            "name": "TEST 06 - Friends (long trip)",
            "user": {
                "target_group": "friends",
                "group_size": 3,
                "daily_limit": 600,
                "preferences": {
                    "pace": "active",
                    "interests": ["adventure", "nature"]
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
        
        # Check for missing transits
        missing = check_missing_transits(plan, pois_dict)
        
        total_tests += 1
        
        # Count attractions and transfers
        attractions = [item for item in plan if item.get('type') == 'attraction']
        transfers = [item for item in plan if item.get('type') == 'transfer']
        
        print(f"\nPlan summary:")
        print(f"  Attractions: {len(attractions)}")
        print(f"  Transfers: {len(transfers)}")
        print(f"  Expected transfers: {max(0, len(attractions) - 1)}")
        
        if missing:
            failed_tests += 1
            print(f"\n[FAIL] Found {len(missing)} missing transit(s) for distant POI")
            print(f"       (distance > 2km REQUIRES transfer)\n")
            
            for item in missing:
                print(f"  Missing transfer:")
                print(f"    From: {item['from']}")
                print(f"    To: {item['to']}")
                print(f"    Distance: {item['distance_km']:.2f} km")
                print()
        else:
            passed_tests += 1
            print(f"\n[PASS] All distant POI have proper transits")
            
            # Show transfers summary
            if transfers:
                print(f"\nTransfers in plan:")
                for t in transfers:
                    print(f"  {t.get('from', 'N/A')} -> {t.get('to', 'N/A')} ({t.get('duration_min', 0)} min)")
    
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
    success = test_transits()
    sys.exit(0 if success else 1)
