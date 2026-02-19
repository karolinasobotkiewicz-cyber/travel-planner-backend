"""
Unit tests for Issue #4 fix - why_selected refinement 2.0 (UAT Round 2)

BUGFIX (19.02.2026 - UAT Round 2, Issue #4)

Problem: 7/10 tests show issues with why_selected explanations
Frequency: 70% of scenarios

Examples from UAT:
- Test 05: preferences=kids_attractions but why_selected missing "Matches your kids_attractions"
- Test 07: friends+adventure+crowd_tolerance=2 → "Quiet, peaceful destination" (wrong!)
- Test 08: Morskie Oko → "Quiet, peaceful destination" (most popular place!)
- Multiple tests: why_selected = [] (empty)

Root Cause:
1. "Quiet, peaceful destination" hardcoded without profile awareness
2. No profile-based reasons (friends+adventure should get "Great for group adventures")
3. No fallback for empty reasons
4. Preference matching may miss some cases

Fix:
1. Remove "Quiet, peaceful destination" hardcode
2. Add smarter crowd tolerance reasoning with profile awareness
3. Add profile-based reasons (_explain_profile_match function)
4. Add fallback: "Fits your travel plan timing and location"
5. Ensure every POI has ≥1 reason

Test Scenarios:
1. Friends + adventure → should NOT get "Quiet"
2. Seniors + relax → CAN get "Peaceful atmosphere"
3. Family + kids pref → "Perfect for families with kids"
4. Empty reasons → fallback added
5. UAT Example Test 07 validation
"""

from app.domain.planner.explainability import (
    explain_poi_selection,
    _explain_crowd_fit,
    _explain_profile_match
)


def test_scenario1_friends_adventure_no_quiet():
    """
    Scenario 1: Friends + adventure should NOT get "Quiet, peaceful destination"
    
    Profile:
    - target_group: friends
    - travel_style: adventure
    - crowd_tolerance: 2
    
    POI:
    - popularity_score: 2.5 (low)
    
    Expected:
    - Should NOT include "Quiet, peaceful destination"
    - BEFORE FIX: Would return "Quiet, peaceful destination"
    - AFTER FIX: Returns None (skip crowd reason for social/active profiles)
    """
    print("\\n" + "="*80)
    print("SCENARIO 1: Friends + Adventure → NO 'Quiet'")
    print("="*80)
    
    user = {
        "target_group": "friends",
        "travel_style": "adventure", 
        "crowd_tolerance": 2
    }
    
    poi = {
        "name": "Test Trail",
        "popularity_score": 2.5,  # Low popularity
        "priority_level": 10
    }
    
    # Test crowd fit function directly
    crowd_reason = _explain_crowd_fit(poi, user)
    
    print(f"Profile: friends + adventure + crowd_tolerance={user['crowd_tolerance']}")
    print(f"POI popularity: {poi['popularity_score']} (low)")
    print(f"Crowd reason: {crowd_reason}")
    
    # Validation
    assert crowd_reason is None or "quiet" not in crowd_reason.lower(), \
        f"Friends+adventure should NOT get 'Quiet', got: {crowd_reason}"
    
    print(f"[PASS] No 'Quiet' for friends+adventure profile ✓")
    print()


def test_scenario2_seniors_relax_peaceful_ok():
    """
    Scenario 2: Seniors + relax CAN get "Peaceful atmosphere"
    
    Profile:
    - target_group: seniors
    - travel_style: relax
    - crowd_tolerance: 2
    
    POI:
    - popularity_score: 2.5 (low)
    
    Expected:
    - CAN include "Peaceful atmosphere" (appropriate for seniors+relax)
    - This is a GOOD fix - context-aware reasoning
    """
    print("\\n" + "="*80)
    print("SCENARIO 2: Seniors + Relax → 'Peaceful' OK")
    print("="*80)
    
    user = {
        "target_group": "seniors",
        "travel_style": "relax",
        "crowd_tolerance": 2
    }
    
    poi = {
        "name": "Museum",
        "popularity_score": 2.5,  # Low popularity
        "priority_level": 10
    }
    
    crowd_reason = _explain_crowd_fit(poi, user)
    
    print(f"Profile: seniors + relax + crowd_tolerance={user['crowd_tolerance']}")
    print(f"POI popularity: {poi['popularity_score']} (low)")
    print(f"Crowd reason: {crowd_reason}")
    
    # Validation - should get peaceful atmosphere
    assert crowd_reason is not None, "Seniors+relax should get crowd reason"
    assert "peaceful" in crowd_reason.lower(), \
        f"Seniors+relax should get 'Peaceful', got: {crowd_reason}"
    
    print(f"[PASS] Seniors+relax gets 'Peaceful atmosphere' ✓")
    print()


def test_scenario3_profile_match_friends_adventure():
    """
    Scenario 3: Friends + adventure profile matching
    
    Profile:
    - target_group: friends
    - travel_style: adventure
    
    POI with adventure tags:
    - tags: ["trail", "hiking", "outdoor"]
    
    Expected:
    - "Great for group adventures"
    """
    print("\\n" + "="*80)
    print("SCENARIO 3: Profile Match - Friends + Adventure")
    print("="*80)
    
    user = {
        "target_group": "friends",
        "travel_style": "adventure"
    }
    
    poi = {
        "name": "Mountain Trail",
        "tags": ["trail", "hiking", "outdoor"],
        "type": "natura",
        "priority_level": 10
    }
    
    profile_reason = _explain_profile_match(poi, user)
    
    print(f"Profile: friends + adventure")
    print(f"POI tags: {poi['tags']}")
    print(f"Profile reason: {profile_reason}")
    
    # Validation
    assert profile_reason is not None, "Should get profile reason for friends+adventure+trail"
    assert "group" in profile_reason.lower() or "adventure" in profile_reason.lower(), \
        f"Should mention group/adventure, got: {profile_reason}"
    
    print(f"[PASS] Profile reason: {profile_reason} ✓")
    print()


def test_scenario4_empty_reasons_fallback():
    """
    Scenario 4: Empty reasons → fallback added
    
    POI with no special features:
    - Low priority
    - No preference match
    - No crowd fit
    - No budget fit
    - No style match
    - No profile match
    
    Expected:
    - BEFORE FIX: reasons = [] (empty!)
    - AFTER FIX: reasons = ["Fits your travel plan timing and location"]
    """
    print("\\n" + "="*80)
    print("SCENARIO 4: Empty Reasons → Fallback")
    print("="*80)
    
    user = {
        "target_group": "solo",
        "travel_style": "sightseeing",
        "crowd_tolerance": 2,
        "budget_level": 2,
        "preferences": []
    }
    
    poi = {
        "name": "Small Museum",
        "priority_level": 5,  # Low priority
        "popularity_score": 5.0,  # Medium popularity (no crowd match)
        "cena_bilet_normalny": 35,  # Price doesn't fit budget thresholds (no budget match)
        "tags": [],
        "type": "museum"
    }
    
    reasons = explain_poi_selection(poi, {}, user)
    
    print(f"POI: {poi['name']}")
    print(f"Profile: solo + sightseeing + no preferences")
    print(f"Reasons generated: {reasons}")
    print(f"Number of reasons: {len(reasons)}")
    
    # Validation
    assert len(reasons) > 0, "Reasons should NEVER be empty (fallback must trigger)"
    
    # For this weak POI, fallback should be present
    # (No must-see, no preference match, no crowd fit, no budget fit, no strong style match)
    assert any("timing" in r.lower() or "location" in r.lower() or "fits" in r.lower() for r in reasons), \
        f"POI with no strong signals should get fallback, got: {reasons}"
    
    print(f"[PASS] Always has ≥1 reason (fallback works) ✓")
    print()


def test_scenario5_uat_example_test07():
    """
    Scenario 5: UAT Example - Test 07 validation
    
    Client feedback Test 07:
    "Wielka Krokiew: why_selected=['Quiet, peaceful destination']
    Ale grupa = friends + adventure + crowd_tolerance=2!"
    
    Profile:
    - target_group: friends
    - travel_style: adventure
    - crowd_tolerance: 2
    
    POI:
    - Wielka Krokiew (popular ski jump)
    - popularity_score: ~6-7 (popular attraction)
    
    Expected:
    - Should NOT get "Quiet, peaceful destination"
    - Should get reasons appropriate for friends+adventure
    - May get: "Must-see", preference match, or profile match
    """
    print("\\n" + "="*80)
    print("SCENARIO 5: UAT Example - Test 07 (Wielka Krokiew)")
    print("="*80)
    
    user = {
        "target_group": "friends",
        "travel_style": "adventure",
        "crowd_tolerance": 2,
        "budget_level": 2,
        "preferences": ["sport", "sightseeing", "history_mystery"]
    }
    
    poi = {
        "name": "Wielka Krokiew",
        "priority_level": 11,
        "popularity_score": 6.5,  # Popular
        "cena_bilet_normalny": 12,
        "tags": ["sport", "sightseeing", "iconic"],
        "type": "attraction"
    }
    
    reasons = explain_poi_selection(poi, {}, user)
    
    print(f"Profile: friends + adventure + crowd_tolerance=2")
    print(f"POI: {poi['name']}")
    print(f"Generated reasons: {reasons}")
    
    # Validation
    assert len(reasons) > 0, "Should have reasons"
    
    # Should NOT contain "Quiet, peaceful destination"
    for reason in reasons:
        assert "quiet" not in reason.lower() and "peaceful" not in reason.lower(), \
            f"Friends+adventure should NOT get 'Quiet/peaceful', got: {reason}"
    
    print(f"[PASS] No 'Quiet/peaceful' for friends+adventure ✓")
    
    # Should have appropriate reasons
    has_good_reason = any(
        "must-see" in r.lower() or
        "highly recommended" in r.lower() or
        "preference" in r.lower() or
        "group" in r.lower() or
        "adventure" in r.lower()
        for r in reasons
    )
    
    assert has_good_reason, f"Should have appropriate reason for this profile, got: {reasons}"
    
    print(f"[PASS] Has appropriate reasons for friends+adventure ✓")
    print()


def test_scenario6_family_kids_preference():
    """
    Scenario 6: Family + kids_attractions preference
    
    Client feedback Test 05:
    "preferences = kids_attractions + relaxation, a w why_selected brak 'Matches your kids_attractions'"
    
    Profile:
    - target_group: family
    - preferences: ["kids_attractions", "relaxation"]
    
    POI:
    - tags include "kids" or "family"
    
    Expected:
    - Should get "Matches your kids_attractions preference"
    - May also get "Perfect for families with kids"
    """
    print("\\n" + "="*80)
    print("SCENARIO 6: Family + kids_attractions Preference")
    print("="*80)
    
    user = {
        "target_group": "family",
        "travel_style": "relax",
        "preferences": ["kids_attractions", "relaxation"]
    }
    
    poi = {
        "name": "Podwodny Świat",
        "priority_level": 10,
        "tags": ["kids", "family", "interactive", "water"],
        "type": "attraction"
    }
    
    reasons = explain_poi_selection(poi, {}, user)
    
    print(f"Profile: family + preferences={user['preferences']}")
    print(f"POI: {poi['name']}")
    print(f"POI tags: {poi['tags']}")
    print(f"Generated reasons: {reasons}")
    
    # Validation
    assert len(reasons) > 0, "Should have reasons"
    
    # Should mention kids_attractions preference OR family profile
    has_kids_mention = any(
        "kids" in r.lower() or
        "family" in r.lower() or
        "preference" in r.lower()
        for r in reasons
    )
    
    assert has_kids_mention, \
        f"Should mention kids/family preference or profile, got: {reasons}"
    
    print(f"[PASS] Mentions kids/family in reasons ✓")
    print()


if __name__ == "__main__":
    print("\\n" + "="*80)
    print("ISSUE #4 FIX VALIDATION - why_selected refinement 2.0")
    print("="*80)
    print("\\nTesting:")
    print("1. Remove 'Quiet, peaceful destination' spam")
    print("2. Add profile-aware crowd reasoning")
    print("3. Add profile-based reasons (friends+adventure, etc.)")
    print("4. Add fallback for empty reasons")
    print("5. Validate UAT examples")
    print("\\n")
    
    # Run all scenarios
    try:
        test_scenario1_friends_adventure_no_quiet()
        test_scenario2_seniors_relax_peaceful_ok()
        test_scenario3_profile_match_friends_adventure()
        test_scenario4_empty_reasons_fallback()
        test_scenario5_uat_example_test07()
        test_scenario6_family_kids_preference()
        
        print("\\n" + "="*80)
        print("[SUCCESS] ALL TESTS PASSED - Issue #4 fix validated! ✓")
        print("="*80)
        print("\\nSummary:")
        print("✓ 'Quiet, peaceful destination' spam removed")
        print("✓ Profile-aware crowd reasoning works")
        print("✓ Profile-based reasons added (friends+adventure, family+kids, seniors+relax)")
        print("✓ Fallback ensures no empty why_selected")
        print("✓ UAT example Test 07 validates successfully")
        print("\\n[SUCCESS] ISSUE #4 FIX COMPLETE")
        print("="*80)
        
    except AssertionError as e:
        print("\\n" + "="*80)
        print("[FAIL] TEST FAILED")
        print("="*80)
        print(f"Error: {e}")
        raise
