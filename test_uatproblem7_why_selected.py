"""
Unit test - Verify Problem #7 (why_selected dynamic explanations) fix

UAT Problem #7:
- ISSUE: Generic "Perfect for couples seeking romantic experiences" for ALL POI
- EXPECTED: Dynamic explanations based on user preferences, travel_style, POI characteristics

Tests cover:
- Test 02: couples + museum/relaxation preferences
- Test 05: family_kids + kids_attractions preferences
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.domain.planner.explainability import explain_poi_selection


def test_why_selected_couples_museum_preference():
    """
    Test 02 scenario: couples + museum_heritage preference
    
    BEFORE: "Perfect for couples seeking romantic experiences" (generic)
    AFTER: "Matches your museum and heritage interests - perfect for couples" (dynamic)
    """
    # Mock POI: Muzeum Tatrzańskie
    poi = {
        "name": "Muzeum Tatrzańskie",
        "type": "museum",
        "tags": ["museum", "heritage", "cultural", "historical"],
        "target_groups": "couples,solo,seniors",
        "priority_level": 11
    }
    
    # Mock user: Test 02 (couples, cultural style, museum preference)
    user = {
        "target_group": "couples",
        "travel_style": "cultural",
        "preferences": ["museum_heritage", "relaxation", "local_food_experience"]
    }
    
    context = {"time_of_day": "morning"}
    
    # Generate why_selected
    reasons = explain_poi_selection(poi, context, user)
    
    # Verify
    assert len(reasons) > 0, "Should generate at least one reason"
    
    # Should NOT be generic
    generic_reasons = [
        "Perfect for couples seeking romantic experiences",
        "Well-suited for couples"
    ]
    
    for reason in reasons:
        assert reason not in generic_reasons, (
            f"Reason should not be generic, got: '{reason}'"
        )
    
    # Should mention preference match
    preference_mentioned = any(
        "museum" in reason.lower() or "heritage" in reason.lower()
        for reason in reasons
    )
    
    assert preference_mentioned, (
        f"Should mention museum/heritage preference match. Got: {reasons}"
    )
    
    print(f"✅ Test PASSED - Dynamic reasons: {reasons}")


def test_why_selected_couples_non_matching_poi():
    """
    Test 02 scenario: couples with museum preference but POI is kids attraction
    
    SHOULD NOT say "romantic" for Mini Zoo when user wants museums!
    """
    # Mock POI: Mini Zoo (kids attraction, not cultural)
    poi = {
        "name": "Mini Zoo",
        "type": "zoo",
        "tags": ["kids", "animals", "outdoor", "family"],
        "target_groups": "family_kids,couples",
        "priority_level": 10
    }
    
    # Mock user: Test 02 (couples, cultural style, museum preference)
    user = {
        "target_group": "couples",
        "travel_style": "cultural",
        "preferences": ["museum_heritage", "relaxation", "local_food_experience"]
    }
    
    context = {"time_of_day": "afternoon"}
    
    # Generate why_selected
    reasons = explain_poi_selection(poi, context, user)
    
    # Should NOT claim preference match (no museum/heritage tags)
    bad_reasons = [
        "Matches your museum",
        "Matches your heritage",
        "Perfect for couples seeking romantic"
    ]
    
    for reason in reasons:
        for bad in bad_reasons:
            assert bad not in reason, (
                f"Should NOT claim preference match for Mini Zoo. Got: '{reason}'"
            )
    
    print(f"✅ Test PASSED - No false preference claims: {reasons}")


def test_why_selected_family_kids_attractions():
    """
    Test 05 scenario: family_kids + kids_attractions preference
    
    Should generate: "Great family activities experience for families with kids"
    NOT: "Perfect for couples" (wrong target group)
    """
    # Mock POI: Podwodny Świat (kids attraction)
    poi = {
        "name": "Podwodny Świat",
        "type": "attraction",
        "tags": ["kids", "educational", "indoor", "family_friendly"],
        "target_groups": "family_kids",
        "priority_level": 10
    }
    
    # Mock user: Test 05 (family_kids, relax style, kids_attractions preference)
    user = {
        "target_group": "family_kids",
        "travel_style": "relax",
        "preferences": ["kids_attractions", "relaxation", "local_food"]
    }
    
    context = {"time_of_day": "morning"}
    
    # Generate why_selected
    reasons = explain_poi_selection(poi, context, user)
    
    # Verify
    assert len(reasons) > 0, "Should generate at least one reason"
    
    # Should mention family/kids
    family_mentioned = any(
        "family" in reason.lower() or "kids" in reason.lower() or "children" in reason.lower()
        for reason in reasons
    )
    
    assert family_mentioned, (
        f"Should mention family/kids for family_kids target group. Got: {reasons}"
    )
    
    # Should NOT mention couples
    couples_mentioned = any("couples" in reason.lower() for reason in reasons)
    assert not couples_mentioned, (
        f"Should NOT mention couples for family_kids group. Got: {reasons}"
    )
    
    print(f"✅ Test PASSED - Family-specific reasons: {reasons}")


def test_why_selected_travel_style_fallback():
    """
    Test travel_style + POI type fallback when no preference match
    
    Example: couples + cultural style + museum POI (but no museum preference)
    Should generate: "Cultural museum experience for couples"
    """
    # Mock POI: Museum
    poi = {
        "name": "Test Museum",
        "type": "museum",
        "tags": ["cultural"],
        "target_groups": "couples,solo",
        "priority_level": 10
    }
    
    # Mock user: couples + cultural style BUT no museum preference
    user = {
        "target_group": "couples",
        "travel_style": "cultural",
        "preferences": ["relaxation", "nature_landscape"]  # No museum!
    }
    
    context = {}
    
    # Generate why_selected
    reasons = explain_poi_selection(poi, context, user)
    
    # Should use travel_style + POI type
    style_mentioned = any(
        "cultural" in reason.lower() or "museum" in reason.lower()
        for reason in reasons
    )
    
    assert style_mentioned, (
        f"Should use travel_style + POI type when no pref match. Got: {reasons}"
    )
    
    print(f"✅ Test PASSED - Travel style fallback: {reasons}")


def test_why_selected_no_generic_templates():
    """
    Comprehensive test: Ensure NO generic templates used across all scenarios
    """
    generic_templates = [
        "Perfect for couples seeking romantic experiences",
        "Family-friendly with activities for kids",
        "Great for groups of friends",
        "Senior-friendly with comfortable pace"
    ]
    
    test_scenarios = [
        # Scenario 1: couples + museum
        {
            "poi": {
                "name": "Museum", "type": "museum",
                "tags": ["museum", "heritage"],
                "target_groups": "couples"
            },
            "user": {
                "target_group": "couples",
                "preferences": ["museum_heritage"]
            }
        },
        # Scenario 2: family + kids POI
        {
            "poi": {
                "name": "Mini Zoo", "type": "zoo",
                "tags": ["kids", "family"],
                "target_groups": "family_kids"
            },
            "user": {
                "target_group": "family_kids",
                "preferences": ["kids_attractions"]
            }
        }
    ]
    
    for i, scenario in enumerate(test_scenarios):
        reasons = explain_poi_selection(scenario["poi"], {}, scenario["user"])
        
        for reason in reasons:
            for template in generic_templates:
                assert template not in reason, (
                    f"Scenario {i+1}: Generic template found: '{template}' in '{reason}'"
                )
    
    print("✅ Test PASSED - No generic templates used")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
