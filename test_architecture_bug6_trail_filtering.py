"""
Test Architecture Bug 6: Trail preference filtering
Verify trails are EXCLUDED when user has no hiking/mountain preferences
"""
import sys
sys.path.insert(0, 'c:\\Users\\matte\\Desktop\\Backend Developer (Python) - silnik planowania podróży\\travel-planner-backend')

from app.domain.planner.engine import build_day


def test_trail_preference_filtering():
    """Test that trails are filtered out when user has no hiking preferences."""
    
    print("="*80)
    print("TEST: Trail Preference Filtering (Bug #6)")
    print("="*80)
    
    # Mock POIs: 2 trails + 2 regular POI
    pois = [
        {
            "id": "trail1",
            "type": "trail",
            "name": "Giewont",  # Shorter trail that fits in 1 day
            "difficulty_level": "moderate",
            "duration_min": 210,  # 3.5 hours (fits in 10h day)
            "duration_max": 250,
            "priorytet": 12,
            "tags": ["mountain", "hiking"],
            "target_groups": ["friends", "couples"],  # friends is valid group
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
            "name": "Dolina Kościeliska",  # Shorter trail
            "difficulty_level": "easy",
            "duration_min": 180,  # 3 hours
            "duration_max": 210,
            "priorytet": 11,
            "tags": ["mountain", "hiking"],
            "target_groups": ["friends", "couples"],  # friends is valid group
            "lat": 49.2192,
            "lng": 19.9914
        },
        {
            "id": "poi2",
            "type": "poi",
            "Name": "Krupówki",
            "priorytet": 10,
            "typ": "shopping",
            "czas_zwiedzania_min": 90,
            "tags": ["shopping", "culture"],
            "target_groups": ["family_kids", "friends", "couples", "seniors"],
            "lat": 49.2964,
            "lng": 19.9486
        }
    ]
    
    # Test Case 1: User WITHOUT hiking preferences (culture + food)
    user_no_hiking = {
        "target_group": "couples",
        "budget_level": 2,
        "preferences": ["culture", "food", "shopping"],  # NO mountain_trails/hiking
        "special_needs": []
    }
    
    context = {
        "season": "summer",
        "date": "2026-07-15"
    }
    
    print("\n[Test Case 1] User WITHOUT hiking preferences")
    print("-" * 80)
    print(f"Preferences: {user_no_hiking['preferences']}")
    print(f"Group: {user_no_hiking['target_group']}")
    print(f"POIs available: 2 trails + 2 regular POI")
    print()
    
    plan_no_hiking = build_day(pois, user_no_hiking, context)
    
    # build_day returns list of items, not dict
    plan_items = plan_no_hiking if isinstance(plan_no_hiking, list) else plan_no_hiking.get("items", [])
    
    print(f"\n[DEBUG] Plan items for Test Case 1:")
    for item in plan_items:
        if item.get("type") == "attraction":
            poi = item.get("poi", {})  # Full POI dict is stored in "poi" field
            print(f"  - {item.get('type')}: id={poi.get('id')}, type={poi.get('type')}")
    
    # Count trails in plan
    trail_count = sum(
        1 for item in plan_items
        if item.get("type") == "attraction" and 
           item.get("poi", {}).get("type") == "trail"  # Check POI type directly
    )
    
    poi_count = sum(
        1 for item in plan_items
        if item.get("type") == "attraction"
    )
    
    print(f"Plan generated: {poi_count} attractions total")
    print(f"Trails in plan: {trail_count}")
    print()
    
    if trail_count == 0:
        print("CORRECT: NO trails in plan (user has no hiking preferences)")
        test1_pass = True
    else:
        print(f"BUG: {trail_count} trails in plan (should be 0 for culture/food user)")
        for item in plan_items:
            if item.get("type") == "attraction":
                poi = item.get("poi", {})
                if poi.get("type") == "trail":
                    print(f"   - {poi.get('name')} (trail) - SHOULD NOT BE HERE")
        test1_pass = False
    
    # Test Case 2: User WITH hiking preferences (mountain_trails)
    user_with_hiking = {
        "target_group": "friends",  # Valid group (not "adventure_seekers")
        "budget_level": 2,
        "preferences": ["mountain_trails", "nature", "outdoor"],  # HAS mountain_trails
        "special_needs": []
    }
    
    print("\n[Test Case 2] User WITH hiking preferences")
    print("-" * 80)
    print(f"Preferences: {user_with_hiking['preferences']}")
    print(f"Group: {user_with_hiking['target_group']}")
    print(f"POIs available: 2 trails + 2 regular POI")
    print()
    
    plan_with_hiking = build_day(pois, user_with_hiking, context)
    
    # build_day returns list of items, not dict
    plan_items_hiking = plan_with_hiking if isinstance(plan_with_hiking, list) else plan_with_hiking.get("items", [])
    
    print(f"\n[DEBUG] Plan items for Test Case 2:")
    for item in plan_items_hiking:
        if item.get("type") == "attraction":
            poi = item.get("poi", {})  # Full POI dict is stored in "poi" field
            name_safe = str(poi.get('name', 'unknown')).encode('ascii', errors='ignore').decode('ascii')
            print(f"  - {item.get('type')}: id={poi.get('id')}, type={poi.get('type')}, name={name_safe}")
    
    # Count trails in plan
    trail_count_hiking = sum(
        1 for item in plan_items_hiking
        if item.get("type") == "attraction" and 
           item.get("poi", {}).get("type") == "trail"  # Check POI type directly
    )
    
    poi_count_hiking = sum(
        1 for item in plan_items_hiking
        if item.get("type") == "attraction"
    )
    
    print(f"Plan generated: {poi_count_hiking} attractions total")
    print(f"Trails in plan: {trail_count_hiking}")
    print()
    
    if trail_count_hiking > 0:
        print(f"CORRECT: {trail_count_hiking} trails in plan (user has mountain_trails preference)")
        test2_pass = True
    else:
        print(f"UNEXPECTED: NO trails in plan (user has mountain_trails, should get trails)")
        test2_pass = False
    
    # Final result
    print("\n" + "="*80)
    print("TEST RESULT:")
    print("="*80)
    
    success = test1_pass and test2_pass
    
    if success:
        print("SUCCESS: Trail preference filtering working correctly")
        print("   - Culture/food user -> NO trails")
        print("   - Mountain_trails user -> trails allowed")
        return True
    else:
        print("FAILURE: Trail preference filtering not working")
        if not test1_pass:
            print("   - Culture/food user should NOT get trails")
        if not test2_pass:
            print("   - Mountain_trails user should get trails")
        return False


if __name__ == "__main__":
    success = test_trail_preference_filtering()
    sys.exit(0 if success else 1)
