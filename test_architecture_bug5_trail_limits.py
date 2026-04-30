"""
Test for ARCHITECTURE BUG #5: Trail limits per trip (27.04.2026 - CLIENT FEEDBACK)

Problem: No limits on trails per trip (could have 5 trails in 3 days)
Expected: Trail limits based on trip duration
Solution: Global trail counter with limits

Trail limit rules:
- 2-3 days → max 1 trail
- 4-5 days → max 2 trails
- 6-7 days → max 3 trails

Test cases:
1. 3-day trip -> max 1 trail (even if 4 trails available)
2. 5-day trip -> max 2 trails (even if 4 trails available)
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from app.domain.planner.engine import plan_multiple_days


def test_trail_limits():
    """Test that trails are limited based on trip duration"""
    print("="*80)
    print("TEST: Trail Limits Per Trip (Bug #5)")
    print("="*80)
    
    # Mock POIs: 4 trails + 5 regular POI
    pois = [
        {
            "id": "rysy",
            "type": "trail",
            "name": "Rysy",
            "difficulty_level": "difficult",
            "duration_min": 660,  # 11h
            "duration_max": 780,
            "priorytet": 20,
            "tags": ["mountain", "hiking", "difficult"],
            "target_groups": ["friends", "adventure_seekers"],
            "lat": 49.1794,
            "lng": 20.0880
        },
        {
            "id": "giewont",
            "type": "trail",
            "name": "Giewont",
            "difficulty_level": "moderate",
            "duration_min": 210,  # 3.5h
            "duration_max": 250,
            "priorytet": 18,
            "tags": ["mountain", "hiking"],
            "target_groups": ["friends", "couples"],
            "lat": 49.1794,
            "lng": 20.0880
        },
        {
            "id": "koscieliska",
            "type": "trail",
            "name": "Dolina Koscieliska",
            "difficulty_level": "easy",
            "duration_min": 180,  # 3h
            "duration_max": 210,
            "priorytet": 16,
            "tags": ["mountain", "hiking"],
            "target_groups": ["friends", "couples", "family_kids"],
            "lat": 49.2192,
            "lng": 19.9914
        },
        {
            "id": "morskie_oko",
            "type": "trail",
            "name": "Morskie Oko Trail",
            "difficulty_level": "easy",
            "duration_min": 120,  # 2h
            "duration_max": 150,
            "priorytet": 14,
            "tags": ["nature", "lake"],
            "target_groups": ["family_kids", "friends", "couples"],
            "lat": 49.2016,
            "lng": 20.0707
        },
        {
            "id": "poi1",
            "type": "poi",
            "Name": "Termy Zakopiańskie",
            "priorytet": 12,
            "typ": "spa",
            "czas_zwiedzania_min": 120,
            "tags": ["spa", "relaxation"],
            "target_groups": ["couples", "seniors"],
            "lat": 49.2964,
            "lng": 19.8486
        },
        {
            "id": "poi2",
            "type": "poi",
            "Name": "Gubałówka",
            "priorytet": 10,
            "typ": "viewpoint",
            "czas_zwiedzania_min": 45,
            "tags": ["viewpoint", "scenic"],
            "target_groups": ["family_kids", "friends", "couples", "seniors"],
            "lat": 49.2864,
            "lng": 19.9486
        },
        {
            "id": "poi3",
            "type": "poi",
            "Name": "Krupówki",
            "priorytet": 10,
            "typ": "shopping",
            "czas_zwiedzania_min": 90,
            "tags": ["shopping", "culture"],
            "target_groups": ["family_kids", "friends", "couples", "seniors"],
            "lat": 49.2964,
            "lng": 19.9486
        },
        {
            "id": "poi4",
            "type": "poi",
            "Name": "Muzeum Tatrzańskie",
            "priorytet": 8,
            "typ": "museum",
            "czas_zwiedzania_min": 60,
            "tags": ["museum", "culture"],
            "target_groups": ["friends", "couples", "seniors"],
            "lat": 49.2900,
            "lng": 19.9500
        },
        {
            "id": "poi5",
            "type": "poi",
            "Name": "Wielka Krokiew",
            "priorytet": 7,
            "typ": "attraction",
            "czas_zwiedzania_min": 30,
            "tags": ["sports", "sightseeing"],
            "target_groups": ["family_kids", "friends", "couples"],
            "lat": 49.2800,
            "lng": 19.9600
        }
    ]
    
    # User with hiking preferences (allows trails)
    user_hiking = {
        "target_group": "friends",
        "budget_level": 2,
        "preferences": ["mountain_trails", "nature", "outdoor"],
        "special_needs": []
    }
    
    # =========================================================================
    # Test Case 1: 3-day trip -> max 1 trail
    # =========================================================================
    print("\n[Test Case 1] 3-day trip")
    print("-"*80)
    print("Expected: max 1 trail (even though 4 trails available)")
    
    contexts_3day = [
        {"city_name": "Zakopane", "destination_type": "city", "season": "summer", "days_count": 3},
        {"city_name": "Zakopane", "destination_type": "city", "season": "summer", "days_count": 3},
        {"city_name": "Zakopane", "destination_type": "city", "season": "summer", "days_count": 3}
    ]
    
    plan_3day = plan_multiple_days(pois, user_hiking, contexts_3day, "08:00", "20:00")
    
    # Count trails across all 3 days
    trail_count_3day = 0
    trail_ids_3day = []
    for day_num, day_plan in enumerate(plan_3day):
        day_trails = 0
        for item in day_plan:
            if item.get("type") == "attraction":
                poi = item.get("poi", {})
                if poi.get("type") == "trail":
                    trail_count_3day += 1
                    day_trails += 1
                    trail_ids_3day.append(poi.get("id"))
        print(f"Day {day_num + 1}: {day_trails} trails")
    
    print(f"\nTotal trails in 3-day plan: {trail_count_3day}")
    print(f"Trail IDs: {trail_ids_3day}")
    
    if trail_count_3day <= 1:
        print(f"CORRECT: {trail_count_3day}/1 trail limit respected for 3-day trip")
        test1_pass = True
    else:
        print(f"BUG: {trail_count_3day} trails (should be max 1 for 3-day trip)")
        test1_pass = False
    
    # =========================================================================
    # Test Case 2: 5-day trip -> max 2 trails
    # =========================================================================
    print("\n[Test Case 2] 5-day trip")
    print("-"*80)
    print("Expected: max 2 trails (even though 4 trails available)")
    
    contexts_5day = [
        {"city_name": "Zakopane", "destination_type": "city", "season": "summer", "days_count": 5},
        {"city_name": "Zakopane", "destination_type": "city", "season": "summer", "days_count": 5},
        {"city_name": "Zakopane", "destination_type": "city", "season": "summer", "days_count": 5},
        {"city_name": "Zakopane", "destination_type": "city", "season": "summer", "days_count": 5},
        {"city_name": "Zakopane", "destination_type": "city", "season": "summer", "days_count": 5}
    ]
    
    plan_5day = plan_multiple_days(pois, user_hiking, contexts_5day, "08:00", "20:00")
    
    # Count trails across all 5 days
    trail_count_5day = 0
    trail_ids_5day = []
    for day_num, day_plan in enumerate(plan_5day):
        day_trails = 0
        for item in day_plan:
            if item.get("type") == "attraction":
                poi = item.get("poi", {})
                if poi.get("type") == "trail":
                    trail_count_5day += 1
                    day_trails += 1
                    trail_ids_5day.append(poi.get("id"))
        print(f"Day {day_num + 1}: {day_trails} trails")
    
    print(f"\nTotal trails in 5-day plan: {trail_count_5day}")
    print(f"Trail IDs: {trail_ids_5day}")
    
    if trail_count_5day <= 2:
        print(f"CORRECT: {trail_count_5day}/2 trail limit respected for 5-day trip")
        test2_pass = True
    else:
        print(f"BUG: {trail_count_5day} trails (should be max 2 for 5-day trip)")
        test2_pass = False
    
    # =========================================================================
    # Final result
    # =========================================================================
    print("\n" + "="*80)
    print("TEST RESULT:")
    print("="*80)
    
    success = test1_pass and test2_pass
    
    if success:
        print("SUCCESS: Trail limits working correctly")
        print("   - 3-day trip -> max 1 trail")
        print("   - 5-day trip -> max 2 trails")
        return True
    else:
        print("FAILURE: Trail limits not working")
        if not test1_pass:
            print("   - 3-day trip should have max 1 trail")
        if not test2_pass:
            print("   - 5-day trip should have max 2 trails")
        return False


if __name__ == "__main__":
    success = test_trail_limits()
    sys.exit(0 if success else 1)
