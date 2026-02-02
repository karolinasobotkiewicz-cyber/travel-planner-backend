"""
Test ETAP 2 fixes (02.02.2026):
- FIX #6: priority_level scoring bonus
- FIX #8: target_group matching dla wszystkich grup
"""
import sys
import os
sys.path.insert(0, os.path.abspath("."))

from app.domain.scoring.preferences import calculate_priority_bonus
from app.domain.scoring.family_fit import calculate_family_score


def test_priority_bonus():
    """Test FIX #6: priority_level bonus scoring"""
    print("\n=== TEST FIX #6: Priority_level scoring ===")
    
    # Test 1: core = +30
    poi_core = {"priority_level": "core"}
    bonus = calculate_priority_bonus(poi_core, {})
    print(f"✓ Core POI: {bonus} (expected 30.0)")
    assert bonus == 30.0, f"Core bonus should be 30.0, got {bonus}"
    
    # Test 2: secondary = +10
    poi_secondary = {"priority_level": "secondary"}
    bonus = calculate_priority_bonus(poi_secondary, {})
    print(f"✓ Secondary POI: {bonus} (expected 10.0)")
    assert bonus == 10.0, f"Secondary bonus should be 10.0, got {bonus}"
    
    # Test 3: optional = 0
    poi_optional = {"priority_level": "optional"}
    bonus = calculate_priority_bonus(poi_optional, {})
    print(f"✓ Optional POI: {bonus} (expected 0.0)")
    assert bonus == 0.0, f"Optional bonus should be 0.0, got {bonus}"
    
    # Test 4: brak = 0
    poi_none = {}
    bonus = calculate_priority_bonus(poi_none, {})
    print(f"✓ No priority_level: {bonus} (expected 0.0)")
    assert bonus == 0.0, f"No priority bonus should be 0.0, got {bonus}"
    
    print("✅ FIX #6 PASSED - Priority_level scoring works correctly\n")


def test_target_group_matching():
    """Test FIX #8: target_group matching dla wszystkich grup"""
    print("=== TEST FIX #8: Target Group Matching (All Groups) ===")
    
    # Test 1: seniors perfect match = +20
    user_seniors = {"target_group": "seniors"}
    poi_seniors = {"target_groups": ["seniors", "couples"]}
    score = calculate_family_score(poi_seniors, user_seniors)
    print(f"✓ Seniors match: {score} (expected 20.0)")
    assert score == 20.0, f"Seniors match should be 20.0, got {score}"
    
    # Test 2: solo perfect match = +20
    user_solo = {"target_group": "solo"}
    poi_solo = {"target_groups": ["solo", "friends"]}
    score = calculate_family_score(poi_solo, user_solo)
    print(f"✓ Solo match: {score} (expected 20.0)")
    assert score == 20.0, f"Solo match should be 20.0, got {score}"
    
    # Test 3: couples perfect match = +20
    user_couples = {"target_group": "couples"}
    poi_couples = {"target_groups": ["couples", "seniors"]}
    score = calculate_family_score(poi_couples, user_couples)
    print(f"✓ Couples match: {score} (expected 20.0)")
    assert score == 20.0, f"Couples match should be 20.0, got {score}"
    
    # Test 4: friends perfect match = +20
    user_friends = {"target_group": "friends"}
    poi_friends = {"target_groups": ["friends", "solo"]}
    score = calculate_family_score(poi_friends, user_friends)
    print(f"✓ Friends match: {score} (expected 20.0)")
    assert score == 20.0, f"Friends match should be 20.0, got {score}"
    
    # Test 5: mismatch = -10
    user_solo_mismatch = {"target_group": "solo"}
    poi_family_only = {"target_groups": ["family_kids"]}
    score = calculate_family_score(poi_family_only, user_solo_mismatch)
    print(f"✓ Solo vs family_kids POI (mismatch): {score} (expected -10.0)")
    assert score == -10.0, f"Mismatch should be -10.0, got {score}"
    
    # Test 6: brak target_groups = 0 (neutral)
    user_seniors_neutral = {"target_group": "seniors"}
    poi_no_target = {}
    score = calculate_family_score(poi_no_target, user_seniors_neutral)
    print(f"✓ Seniors vs POI with no target_groups: {score} (expected 0.0)")
    assert score == 0.0, f"No target_groups should be neutral (0.0), got {score}"
    
    # Test 7: family_kids legacy logic still works
    user_family = {"target_group": "family_kids", "children_age": 8}
    poi_kids = {"kids_only": True}
    score = calculate_family_score(poi_kids, user_family)
    print(f"✓ Family_kids with kids_only POI: {score} (expected 8.0)")
    assert score == 8.0, f"Kids only bonus should be 8.0, got {score}"
    
    print("✅ FIX #8 PASSED - Target group matching works for all groups\n")


def test_scoring_in_context():
    """Test integration - priority + target_group working together"""
    print("=== TEST INTEGRATION: Priority + Target Group ===")
    
    # Symulacja POI: core + seniors match
    poi = {
        "priority_level": "core",
        "target_groups": ["seniors", "couples"]
    }
    user = {"target_group": "seniors"}
    
    priority_bonus = calculate_priority_bonus(poi, user)
    target_bonus = calculate_family_score(poi, user)
    total_bonus = priority_bonus + target_bonus
    
    print(f"POI: core priority + seniors target_group")
    print(f"  Priority bonus: +{priority_bonus}")
    print(f"  Target group bonus: +{target_bonus}")
    print(f"  Total bonus: +{total_bonus} (expected 50.0)")
    assert total_bonus == 50.0, f"Total bonus should be 50.0, got {total_bonus}"
    
    print("✅ INTEGRATION TEST PASSED\n")


if __name__ == "__main__":
    try:
        test_priority_bonus()
        test_target_group_matching()
        test_scoring_in_context()
        print("\n" + "="*60)
        print("🎉 ALL ETAP 2 TESTS PASSED!")
        print("="*60)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
