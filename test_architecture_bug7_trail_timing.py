"""
Test for ARCHITECTURE BUG #7: Trail timing (27.04.2026 - CLIENT FEEDBACK)

Problem: Trails scheduled at wrong times (trail start 14:00, 16:00)
Expected: Trails only in morning (08:00-10:00)
Solution: HARD FILTER trails if now >= 10:00 AM

Test cases:
1. Day starts at 14:00 (afternoon) -> NO trails allowed
2. Day starts at 09:00 (morning) -> trails allowed
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from app.domain.planner.engine import build_day


def test_trail_timing():
    """Test that trails are only selected in morning (before 10:00 AM)"""
    print("="*80)
    print("TEST: Trail Timing Restriction (Bug #7)")
    print("="*80)
    
    # Mock POIs: 2 trails + 2 regular POI
    pois = [
        {
            "id": "trail1",
            "type": "trail",
            "name": "Giewont",
            "difficulty_level": "moderate",
            "duration_min": 210,  # 3.5 hours
            "duration_max": 250,
            "priorytet": 12,
            "tags": ["mountain", "hiking"],
            "target_groups": ["friends", "couples"],
            "lat": 49.1794,
            "lng": 20.0880
        },
        {
            "id": "poi1",
            "type": "poi",
            "Name": "Morskie Oko",
            "priorytet": 15,
            "typ": "nature",
            "czas_zwiedzania_min": 60,
            "tags": ["lake", "nature"],
            "target_groups": ["family_kids", "friends", "couples"],
            "lat": 49.2016,
            "lng": 20.0707
        },
        {
            "id": "trail2",
            "type": "trail",
            "name": "Dolina Koscieliska",
            "difficulty_level": "easy",
            "duration_min": 180,  # 3 hours
            "duration_max": 210,
            "priorytet": 11,
            "tags": ["mountain", "hiking"],
            "target_groups": ["friends", "couples"],
            "lat": 49.2192,
            "lng": 19.9914
        },
        {
            "id": "poi2",
            "type": "poi",
            "Name": "Krupowki",
            "priorytet": 10,
            "typ": "shopping",
            "czas_zwiedzania_min": 90,
            "tags": ["shopping", "culture"],
            "target_groups": ["family_kids", "friends", "couples", "seniors"],
            "lat": 49.2964,
            "lng": 19.9486
        }
    ]
    
    # User with hiking preferences (trails allowed by preference filter)
    user_hiking = {
        "target_group": "friends",
        "budget_level": 2,
        "preferences": ["mountain_trails", "nature", "outdoor"],
        "special_needs": []
    }
    
    context = {
        "city_name": "Zakopane",
        "destination_type": "city",
        "days_count": 1
    }
    
    # =========================================================================
    # Test Case 1: Day starts at 14:00 (afternoon) -> NO trails allowed
    # =========================================================================
    print("\n[Test Case 1] Day starts at 14:00 (afternoon)")
    print("-"*80)
    print("Day start: 14:00 (after 10:00 cutoff)")
    print("Expected: NO trails (too late in day)")
    
    plan_afternoon = build_day(pois, user_hiking, context, day_start="14:00", day_end="19:00")
    
    # build_day returns list of items
    plan_items_afternoon = plan_afternoon if isinstance(plan_afternoon, list) else plan_afternoon.get("items", [])
    
    print(f"\n[DEBUG] Plan items for afternoon start:")
    trail_ids = []
    for item in plan_items_afternoon:
        if item.get("type") == "attraction":
            poi = item.get("poi", {})
            name_safe = str(poi.get('name', 'unknown')).encode('ascii', errors='ignore').decode('ascii')
            print(f"  - {item.get('type')}: id={poi.get('id')}, type={poi.get('type')}, name={name_safe}")
            if poi.get("type") == "trail":
                trail_ids.append(poi.get("id"))
    
    # Count trails in plan
    trail_count_afternoon = sum(
        1 for item in plan_items_afternoon
        if item.get("type") == "attraction" and 
           item.get("poi", {}).get("type") == "trail"
    )
    
    poi_count_afternoon = sum(
        1 for item in plan_items_afternoon
        if item.get("type") == "attraction"
    )
    
    print(f"\nPlan generated: {poi_count_afternoon} attractions total")
    print(f"Trails in plan: {trail_count_afternoon}")
    
    if trail_count_afternoon == 0:
        print("CORRECT: NO trails in plan (day starts too late - 14:00 > 10:00 cutoff)")
        test1_pass = True
    else:
        print(f"BUG: {trail_count_afternoon} trails in plan (should be 0 for afternoon start)")
        for trail_id in trail_ids:
            print(f"   - Trail {trail_id} - SHOULD NOT BE HERE (too late)")
        test1_pass = False
    
    # =========================================================================
    # Test Case 2: Day starts at 09:00 (morning) -> trails allowed
    # =========================================================================
    print("\n[Test Case 2] Day starts at 09:00 (morning)")
    print("-"*80)
    print("Day start: 09:00 (before 10:00 cutoff)")
    print("Expected: Trails allowed (within morning window)")
    
    plan_morning = build_day(pois, user_hiking, context, day_start="09:00", day_end="19:00")
    
    # build_day returns list of items
    plan_items_morning = plan_morning if isinstance(plan_morning, list) else plan_morning.get("items", [])
    
    print(f"\n[DEBUG] Plan items for morning start:")
    for item in plan_items_morning:
        if item.get("type") == "attraction":
            poi = item.get("poi", {})
            name_safe = str(poi.get('name', 'unknown')).encode('ascii', errors='ignore').decode('ascii')
            print(f"  - {item.get('type')}: id={poi.get('id')}, type={poi.get('type')}, name={name_safe}")
    
    # Count trails in plan
    trail_count_morning = sum(
        1 for item in plan_items_morning
        if item.get("type") == "attraction" and 
           item.get("poi", {}).get("type") == "trail"
    )
    
    poi_count_morning = sum(
        1 for item in plan_items_morning
        if item.get("type") == "attraction"
    )
    
    print(f"\nPlan generated: {poi_count_morning} attractions total")
    print(f"Trails in plan: {trail_count_morning}")
    
    if trail_count_morning > 0:
        print(f"CORRECT: {trail_count_morning} trails in plan (morning start allows trails)")
        test2_pass = True
    else:
        print(f"UNEXPECTED: NO trails in plan (morning start should allow trails)")
        test2_pass = False
    
    # =========================================================================
    # Final result
    # =========================================================================
    print("\n" + "="*80)
    print("TEST RESULT:")
    print("="*80)
    
    success = test1_pass and test2_pass
    
    if success:
        print("SUCCESS: Trail timing restriction working correctly")
        print("   - Afternoon start (14:00) -> NO trails")
        print("   - Morning start (09:00) -> trails allowed")
        return True
    else:
        print("FAILURE: Trail timing restriction not working")
        if not test1_pass:
            print("   - Afternoon start should NOT get trails")
        if not test2_pass:
            print("   - Morning start should get trails")
        return False


if __name__ == "__main__":
    success = test_trail_timing()
    sys.exit(0 if success else 1)
