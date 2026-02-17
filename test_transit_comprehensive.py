"""
Test comprehensive: Sprawdź czy engine ZAWSZE dodaje transity między POI.

HYPOTHESIS: Problem #3 może dotyczyć sytuacji gdzie engine:
1. Pomija transit przez błąd w warunku if last_poi
2. Pomija transit dla POI z zerową odległością GPS
3. Pomija transit dla soft POI (gap filling)
"""
import sys
sys.path.append('c:\\Users\\matte\\Desktop\\Backend Developer (Python) - silnik planowania podróży\\travel-planner-backend')

from app.domain.planner.engine import build_day, haversine_distance
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi


def analyze_transits(plan, test_name):
    """Analyze transit coverage in a plan."""
    print(f"\n{'='*80}")
    print(f"ANALYZING: {test_name}")
    print(f"{'='*80}")
    
    attractions = []
    transits = []
    
    for item in plan:
        if item.get('type') == 'attraction':
            poi = item.get('poi', {})
            attractions.append({
                'name': poi.get('name', 'Unknown'),
                'id': poi.get('id'),
                'lat': poi.get('lat'),
                'lng': poi.get('lng'),
                'start_time': item.get('start_time'),
                'end_time': item.get('end_time')
            })
        elif item.get('type') == 'transfer':
            transits.append({
                'from': item.get('from'),
                'to': item.get('to'),
                'duration': item.get('duration_min')
            })
    
    print(f"Attractions: {len(attractions)}")
    print(f"Transits: {len(transits)}")
    print(f"Expected transits: {max(0, len(attractions) - 1)}")
    
    # Check for missing transits
    missing_transits = []
    
    for i in range(len(attractions) - 1):
        curr = attractions[i]
        next_attr = attractions[i + 1]
        
        # Check if there's a transit between them in plan
        # Look for transfer mentioning these POI names
        has_transit = any(
            (t['from'] == curr['name'] and t['to'] == next_attr['name']) or
            (curr['name'] in t['from'] and next_attr['name'] in t['to'])
            for t in transits
        )
        
        # Calculate actual distance
        if all([curr['lat'], curr['lng'], next_attr['lat'], next_attr['lng']]):
            distance = haversine_distance(
                curr['lat'], curr['lng'],
                next_attr['lat'], next_attr['lng']
            )
        else:
            distance = None
        
        if not has_transit:
            missing_transits.append({
                'from': curr['name'],
                'to': next_attr['name'],
                'distance_km': distance
            })
        
        # Print details
        status = "TRANSIT" if has_transit else "NO TRANSIT"
        dist_str = f"{distance:.2f} km" if distance else "N/A"
        
        # Safe print for Windows terminal (avoid ALL Unicode)
        curr_name_safe = curr['name'].encode('ascii', 'replace').decode('ascii')
        next_name_safe = next_attr['name'].encode('ascii', 'replace').decode('ascii')
        
        print(f"\n  [{i+1}] {curr_name_safe}")
        print(f"      -> {dist_str} - [{status}]")
        print(f"  [{i+2}] {next_name_safe}")
    
    # Summary
    if missing_transits:
        print(f"\n[FAILED] Found {len(missing_transits)} missing transit(s):")
        for mt in missing_transits:
            dist_str = f"{mt['distance_km']:.2f} km" if mt['distance_km'] else "Unknown distance"
            requirement = "[VIOLATES >2km rule]" if mt['distance_km'] and mt['distance_km'] > 2 else ""
            print(f"  - {mt['from']} -> {mt['to']} ({dist_str}) {requirement}")
        return False
    else:
        print(f"\n[PASSED] All adjacent POI have transits")
        return True


def test_multiple_scenarios():
    """Test multiple user scenarios to find missing transits."""
    print("="*80)
    print("COMPREHENSIVE TRANSIT VALIDATION - MULTIPLE SCENARIOS")
    print("="*80)
    
    pois = load_zakopane_poi('data/zakopane.xlsx')
    print(f"Loaded {len(pois)} POIs\n")
    
    scenarios = [
        {
            "name": "Scenario 1: Family Moderate",
            "user": {
                "target_group": "family_kids",
                "group_size": 4,
                "daily_limit": 400,
                "preferences": {"pace": "moderate"}
            }
        },
        {
            "name": "Scenario 2: Friends Active",
            "user": {
                "target_group": "friends",
                "group_size": 3,
                "daily_limit": 600,
                "preferences": {"pace": "active"}
            }
        },
        {
            "name": "Scenario 3: Couples Relaxed",
            "user": {
                "target_group": "couples",
                "group_size": 2,
                "daily_limit": 500,
                "preferences": {"pace": "relaxed"}
            }
        },
        {
            "name": "Scenario 4: Seniors Slow",
            "user": {
                "target_group": "seniors",
                "group_size": 2,
                "daily_limit": 300,
                "preferences": {"pace": "slow"}
            }
        },
        {
            "name": "Scenario 5: Solo Active (long day)",
            "user": {
                "target_group": "solo",
                "group_size": 1,
                "daily_limit": 700,
                "preferences": {"pace": "active"}
            }
        }
    ]
    
    context = {
        "season": "summer",
        "date": "2026-07-15",
        "weather": {"condition": "sunny", "temp": 25, "wind_speed": 10},
        "has_car": True,
        "daylight_start": "05:00",
        "daylight_end": "21:00"
    }
    
    all_passed = True
    
    for scenario in scenarios:
        plan = build_day(pois, scenario["user"], context)
        passed = analyze_transits(plan, scenario["name"])
        
        if not passed:
            all_passed = False
    
    # Final summary
    print(f"\n{'='*80}")
    print(f"FINAL SUMMARY")
    print(f"{'='*80}")
    
    if all_passed:
        print(f"[PASS] ALL SCENARIOS PASSED")
        print(f"   Problem #3 appears to be RESOLVED or NON-EXISTENT")
        print(f"   Engine correctly adds transits between all adjacent POI")
    else:
        print(f"[FAIL] SOME SCENARIOS FAILED")
        print(f"   Problem #3 CONFIRMED - missing transits detected")
        print(f"   Code fix required in engine.py")
    
    return all_passed


if __name__ == "__main__":
    success = test_multiple_scenarios()
    sys.exit(0 if success else 1)
