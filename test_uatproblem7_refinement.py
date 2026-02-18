"""
UAT Problem #7 REFINEMENT - Test why_selected scoring signals

18.02.2026 - Client feedback:
"Chciałabym, żeby why_selected było generowane wprost z tych samych sygnałów 
co scoring (match do preferencji, travel_style, crowd_tolerance, budżet), 
a nie z „szablonu" na typ grupy."

Test scenarios:
1. Preference match → "Matches your museum_heritage preference"
2. Crowd tolerance fit → "Low-crowd option (fits your crowd_tolerance: 1)"
3. Budget fit → "Budget-friendly (ticket: 15 PLN)"
4. Travel style match → "Cultural experience (matches your style)"
5. No empty why_selected [] - all POI must have reasons
"""
import pytest
from app.domain.planner.explainability import explain_poi_selection


def test_preference_match_reason():
    """
    Test 1: Preference match generates scoring signal reason.
    
    BEFORE (template): "Matches your museum interests - perfect for couples"
    AFTER (scoring): "Matches your museum_heritage preference"
    """
    # POI with museum_heritage tag
    poi = {
        "poi_id": "24",
        "name": "Muzeum Tatrzańskie",
        "type": "museum",
        "tags": ["museum", "heritage", "cultural", "history"],
        "priority_level": 12,
        "popularity_score": 6.5,
        "cena_bilet_normalny": 15
    }
    
    # User with museum_heritage preference
    user = {
        "target_group": "couples",
        "preferences": ["museum_heritage", "relaxation"],
        "travel_style": "cultural",
        "budget_level": 2,
        "crowd_tolerance": 1
    }
    
    context = {"time_of_day": "afternoon"}
    
    # Generate reasons
    reasons = explain_poi_selection(poi, context, user)
    
    # Assert
    print(f"\n✅ Generated reasons: {reasons}")
    assert len(reasons) > 0, "why_selected must not be empty"
    
    # Check for preference match reason (scoring signal)
    # Note: "museum_heritage" preference becomes "museum heritage" in reason
    pref_match = any(
        "museum" in r.lower() and "heritage" in r.lower() for r in reasons
    )
    assert pref_match, f"Expected preference match reason, got: {reasons}"
    
    # Check NO template-based reasons
    template_phrases = [
        "perfect for couples",
        "well-suited for",
        "great for couples"
    ]
    for phrase in template_phrases:
        assert not any(
            phrase in r.lower() for r in reasons
        ), f"Template phrase '{phrase}' found in: {reasons}"
    
    print("✅ Test PASSED - Preference match uses scoring signals, not templates")


def test_crowd_tolerance_reason():
    """
    Test 2: Crowd tolerance fit generates scoring signal reason.
    
    NEW (scoring): "Low-crowd option (fits your crowd_tolerance: 1)"
    """
    # POI with LOW popularity
    poi = {
        "poi_id": "30",
        "name": "Kaplica Jaszczurówka",
        "type": "chapel",
        "tags": ["religious", "architecture", "peaceful"],
        "priority_level": 10,
        "popularity_score": 3.5,  # LOW crowd
        "cena_bilet_normalny": 0
    }
    
    # User with LOW crowd tolerance
    user = {
        "target_group": "seniors",
        "preferences": ["relaxation"],
        "travel_style": "relax",
        "budget_level": 1,
        "crowd_tolerance": 1  # LOW tolerance
    }
    
    context = {"time_of_day": "morning"}
    
    # Generate reasons
    reasons = explain_poi_selection(poi, context, user)
    
    # Assert
    print(f"\n✅ Generated reasons: {reasons}")
    assert len(reasons) > 0, "why_selected must not be empty"
    
    # Check for crowd fit reason (scoring signal)
    crowd_fit = any(
        "low-crowd" in r.lower() or "crowd_tolerance" in r.lower()
        for r in reasons
    )
    assert crowd_fit, f"Expected crowd fit reason, got: {reasons}"
    
    print("✅ Test PASSED - Crowd tolerance fit reflected in why_selected")


def test_budget_fit_reason():
    """
    Test 3: Budget fit generates scoring signal reason.
    
    NEW (scoring): "Budget-friendly (ticket: 15 PLN)"
    """
    # POI with LOW price
    poi = {
        "poi_id": "6",
        "name": "Sanktuarium Matki Bożej Fatimskiej",
        "type": "church",
        "tags": ["religious", "free_entry"],
        "priority_level": 8,
        "popularity_score": 4.0,
        "cena_bilet_normalny": 0  # FREE
    }
    
    # User with LOW budget
    user = {
        "target_group": "solo",
        "preferences": ["relaxation"],
        "travel_style": "relax",
        "budget_level": 1,  # TIGHT budget
        "crowd_tolerance": 2
    }
    
    context = {"time_of_day": "afternoon"}
    
    # Generate reasons
    reasons = explain_poi_selection(poi, context, user)
    
    # Assert
    print(f"\n✅ Generated reasons: {reasons}")
    assert len(reasons) > 0, "why_selected must not be empty"
    
    # Check for budget fit reason (scoring signal)
    budget_fit = any(
        "budget" in r.lower() or "free entry" in r.lower()
        for r in reasons
    )
    assert budget_fit, f"Expected budget fit reason, got: {reasons}"
    
    print("✅ Test PASSED - Budget fit reflected in why_selected")


def test_travel_style_match_reason():
    """
    Test 4: Travel style match generates scoring signal reason.
    
    NEW (scoring): "Cultural experience (matches your style)"
    """
    # POI with cultural type
    poi = {
        "poi_id": "27",
        "name": "Galeria sztuki w willi Oksza",
        "type": "gallery",
        "tags": ["art", "cultural", "museum", "heritage"],
        "priority_level": 10,
        "popularity_score": 5.0,
        "cena_bilet_normalny": 20
    }
    
    # User with cultural style
    user = {
        "target_group": "couples",
        "preferences": ["museum_heritage"],
        "travel_style": "cultural",  # CULTURAL style
        "budget_level": 2,
        "crowd_tolerance": 2
    }
    
    context = {"time_of_day": "afternoon"}
    
    # Generate reasons
    reasons = explain_poi_selection(poi, context, user)
    
    # Assert
    print(f"\n✅ Generated reasons: {reasons}")
    assert len(reasons) > 0, "why_selected must not be empty"
    
    # Check for style match reason (scoring signal)
    style_match = any(
        "cultural" in r.lower() and "style" in r.lower()
        for r in reasons
    )
    
    # Also accept preference match as valid reason
    pref_match = any("museum_heritage" in r.lower() for r in reasons)
    
    assert (
        style_match or pref_match
    ), f"Expected style/preference match reason, got: {reasons}"
    
    print("✅ Test PASSED - Travel style match reflected in why_selected")


def test_no_empty_why_selected():
    """
    Test 5: No empty why_selected [] - all POI must have reasons.
    
    Problem in test02/test05: Many POI have empty why_selected []
    Solution: Always generate at least 1 reason (must-see, preference, etc.)
    """
    # POI with minimal data (no priority, no clear preference match)
    poi = {
        "poi_id": "999",
        "name": "Some Random POI",
        "type": "viewpoint",
        "tags": ["scenic", "nature"],
        "priority_level": 8,
        "popularity_score": 5.0,
        "cena_bilet_normalny": 10
    }
    
    # User with different preferences (no direct match)
    user = {
        "target_group": "family_kids",
        "preferences": ["kids_attractions"],  # No match with POI
        "travel_style": "active",
        "budget_level": 2,
        "crowd_tolerance": 2
    }
    
    context = {"time_of_day": "afternoon"}
    
    # Generate reasons
    reasons = explain_poi_selection(poi, context, user)
    
    # Assert
    print(f"\n✅ Generated reasons: {reasons}")
    
    # CRITICAL: why_selected must NEVER be empty
    assert len(reasons) > 0, (
        "FAILED: why_selected is empty []. "
        "All POI must have at least 1 reason!"
    )
    
    print(f"✅ Test PASSED - No empty why_selected (got {len(reasons)} reasons)")


def test_multiple_scoring_signals():
    """
    Test 6: Multiple scoring signals combine correctly.
    
    POI matching MULTIPLE signals:
    - Must-see (priority_level = 12)
    - Preference match (museum_heritage)
    - Crowd fit (low tolerance + low popularity)
    - Budget fit (low budget + cheap ticket)
    """
    # POI with multiple good signals
    poi = {
        "poi_id": "24",
        "name": "Muzeum Tatrzańskie",
        "type": "museum",
        "tags": ["museum", "heritage", "cultural", "history"],
        "priority_level": 12,  # MUST-SEE
        "popularity_score": 4.0,  # LOW crowd
        "cena_bilet_normalny": 15  # CHEAP
    }
    
    # User matching all signals
    user = {
        "target_group": "couples",
        "preferences": ["museum_heritage"],  # MATCH
        "travel_style": "cultural",  # MATCH
        "budget_level": 1,  # LOW budget
        "crowd_tolerance": 1  # LOW tolerance
    }
    
    context = {"time_of_day": "afternoon"}
    
    # Generate reasons
    reasons = explain_poi_selection(poi, context, user)
    
    # Assert
    print(f"\n✅ Generated reasons (top 3): {reasons}")
    assert len(reasons) == 3, f"Expected top 3 reasons, got {len(reasons)}"
    
    # Check for must-see (highest priority)
    must_see = any("must-see" in r.lower() for r in reasons)
    assert must_see, "Must-see should be in top 3 reasons"
    
    # Check for preference match
    # Note: "museum_heritage" preference becomes "museum heritage" in reason
    pref_match = any(
        "museum" in r.lower() and "heritage" in r.lower() for r in reasons
    )
    assert pref_match, "Preference match should be in top 3 reasons"
    
    # Check for scoring signals (crowd OR budget OR style)
    scoring_signals = any(
        "crowd" in r.lower()
        or "budget" in r.lower()
        or "style" in r.lower()
        for r in reasons
    )
    assert scoring_signals, "At least 1 scoring signal should be in top 3"
    
    print("✅ Test PASSED - Multiple scoring signals prioritized correctly")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("UAT PROBLEM #7 REFINEMENT - why_selected scoring signals")
    print("=" * 70)
    
    test_preference_match_reason()
    test_crowd_tolerance_reason()
    test_budget_fit_reason()
    test_travel_style_match_reason()
    test_no_empty_why_selected()
    test_multiple_scoring_signals()
    
    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED - Problem #7 refinement complete!")
    print("=" * 70)
