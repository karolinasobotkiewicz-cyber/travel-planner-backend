"""
Unit tests for tag preference scoring module.
"""

import sys
sys.path.append("app")

from domain.scoring.tag_preferences import calculate_tag_preference_score, USER_PREFERENCES_TO_TAGS

def test_kids_preference():
    """Test attractions_for_kids preference matching"""
    print("\n🧪 TEST 1: Kids Preference")
    print("=" * 80)
    
    poi = {
        "id": "poi_test",
        "name": "Iluzja Park",
        "type": "kids_attractions",
        "tags": ["illusion_kids", "interactive_exhibition_kids", "playground"]
    }
    
    preferences = ["attractions_for_kids"]
    score = calculate_tag_preference_score(poi, preferences)
    
    print(f"POI: {poi['name']}")
    print(f"Type: {poi['type']}")
    print(f"Tags: {poi['tags']}")
    print(f"User preferences: {preferences}")
    print(f"\n💡 Expected:")
    print(f"   Type match (kids_attractions): +20")
    print(f"   Tag matches (3 tags × 15): +45")
    print(f"   Total: +65")
    print(f"\n✅ Actual score: {score}")
    
    assert score == 65, f"Expected 65, got {score}"
    print("✅ PASS")


def test_water_preference():
    """Test water_attractions preference matching"""
    print("\n🧪 TEST 2: Water Attractions Preference")
    print("=" * 80)
    
    poi = {
        "id": "poi_test",
        "name": "Termy Chochołowskie",
        "type": "water_wellness",
        "tags": ["thermal_baths", "hot_springs", "geothermal_pools", "relaxation_pools", "year_round"]
    }
    
    preferences = ["water_attractions"]
    score = calculate_tag_preference_score(poi, preferences)
    
    print(f"POI: {poi['name']}")
    print(f"Type: {poi['type']}")
    print(f"Tags: {poi['tags']}")
    print(f"User preferences: {preferences}")
    print(f"\n💡 Expected:")
    print(f"   Type match (water_wellness): +20")
    print(f"   Tag matches (5 tags × 15): +75")
    print(f"   Total: +95")
    print(f"\n✅ Actual score: {score}")
    
    assert score == 95, f"Expected 95, got {score}"
    print("✅ PASS")


def test_no_preference():
    """Test backward compatibility - no preferences should return 0"""
    print("\n🧪 TEST 3: No Preferences (Backward Compat)")
    print("=" * 80)
    
    poi = {
        "id": "poi_test",
        "name": "Muzeum Tatrzańskie",
        "type": "museum",
        "tags": ["local_history", "mountain_culture"]
    }
    
    preferences = []
    score = calculate_tag_preference_score(poi, preferences)
    
    print(f"POI: {poi['name']}")
    print(f"User preferences: {preferences}")
    print(f"\n💡 Expected: 0 (no penalty for missing preferences)")
    print(f"✅ Actual score: {score}")
    
    assert score == 0, f"Expected 0, got {score}"
    print("✅ PASS")


def test_no_matching_tags():
    """Test POI with no matching tags - only type bonus"""
    print("\n🧪 TEST 4: No Matching Tags (Type Only)")
    print("=" * 80)
    
    poi = {
        "id": "poi_test",
        "name": "Random Museum",
        "type": "museum",
        "tags": ["some_random_tag", "another_tag"]
    }
    
    preferences = ["museums_heritage"]
    score = calculate_tag_preference_score(poi, preferences)
    
    print(f"POI: {poi['name']}")
    print(f"Type: {poi['type']}")
    print(f"Tags: {poi['tags']}")
    print(f"User preferences: {preferences}")
    print(f"\n💡 Expected:")
    print(f"   Type match (museum): +20")
    print(f"   Tag matches (0): +0")
    print(f"   Total: +20")
    print(f"\n✅ Actual score: {score}")
    
    assert score == 20, f"Expected 20, got {score}"
    print("✅ PASS")


def test_multiple_preferences():
    """Test POI matching multiple user preferences"""
    print("\n🧪 TEST 5: Multiple Preferences")
    print("=" * 80)
    
    poi = {
        "id": "poi_test",
        "name": "Termy with Kids Zone",
        "type": "water_wellness",
        "tags": ["thermal_baths", "aquatic_playground", "family_entertainment"]
    }
    
    preferences = ["water_attractions", "attractions_for_kids"]
    score = calculate_tag_preference_score(poi, preferences)
    
    print(f"POI: {poi['name']}")
    print(f"Type: {poi['type']}")
    print(f"Tags: {poi['tags']}")
    print(f"User preferences: {preferences}")
    print(f"\n💡 Expected:")
    print(f"   water_attractions:")
    print(f"     - Type match (water_wellness): +20")
    print(f"     - thermal_baths: +15")
    print(f"     - aquatic_playground: +15")
    print(f"   attractions_for_kids:")
    print(f"     - aquatic_playground: +15 (matches both!)")
    print(f"     - family_entertainment: +15")
    print(f"   Total: +80")
    print(f"\n✅ Actual score: {score}")
    
    assert score == 80, f"Expected 80, got {score}"
    print("✅ PASS")


def test_active_sport_preference():
    """Test active_sport preference with multiple matching tags"""
    print("\n🧪 TEST 6: Active Sport Preference")
    print("=" * 80)
    
    poi = {
        "id": "poi_test",
        "name": "Kasprowy Wierch",
        "type": "active_sport",
        "tags": ["skiing", "snowboarding", "mountain_trails", "alpine_activities"]
    }
    
    preferences = ["active_sport"]
    score = calculate_tag_preference_score(poi, preferences)
    
    print(f"POI: {poi['name']}")
    print(f"Type: {poi['type']}")
    print(f"Tags: {poi['tags']}")
    print(f"User preferences: {preferences}")
    print(f"\n💡 Expected:")
    print(f"   Type match (active_sport): +20")
    print(f"   Tag matches (4 tags × 15): +60")
    print(f"   Total: +80")
    print(f"\n✅ Actual score: {score}")
    
    assert score == 80, f"Expected 80, got {score}"
    print("✅ PASS")


if __name__ == "__main__":
    print("=" * 80)
    print("TAG PREFERENCE SCORING - UNIT TESTS")
    print("=" * 80)
    
    try:
        test_kids_preference()
        test_water_preference()
        test_no_preference()
        test_no_matching_tags()
        test_multiple_preferences()
        test_active_sport_preference()
        
        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED")
        print("=" * 80)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
