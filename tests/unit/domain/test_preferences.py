"""
Unit tests dla preferences scoring module.
"""
from app.domain.scoring.preferences import calculate_preference_score


def test_perfect_match_two_tags():
    """Test perfect match - 2 matching tags."""
    user = {"preferences": ["outdoor", "family"]}
    poi = {"tags": ["outdoor", "family", "hiking"]}

    score = calculate_preference_score(poi, user)

    assert score == 10.0  # 2 matches * 5 points each


def test_partial_match_one_tag():
    """Test partial match - 1 matching tag."""
    user = {"preferences": ["outdoor", "family"]}
    poi = {"tags": ["outdoor", "mountain", "hiking"]}

    score = calculate_preference_score(poi, user)

    assert score == 5.0  # 1 match * 5 points


def test_no_match():
    """Test no match - brak wspólnych tagów."""
    user = {"preferences": ["outdoor", "family"]}
    poi = {"tags": ["museums", "culture", "history"]}

    score = calculate_preference_score(poi, user)

    assert score == 0.0  # No matches


def test_user_no_preferences():
    """Test user bez preferences - neutralne."""
    user = {"preferences": []}
    poi = {"tags": ["outdoor", "mountain", "hiking"]}

    score = calculate_preference_score(poi, user)

    assert score == 0.0  # No preferences = neutral


def test_poi_no_tags():
    """Test POI bez tagów - neutralne."""
    user = {"preferences": ["outdoor", "family"]}
    poi = {"tags": []}

    score = calculate_preference_score(poi, user)

    assert score == 0.0  # No tags = neutral


def test_user_missing_preferences_key():
    """Test user bez klucza preferences - neutralne."""
    user = {}  # Brak klucza "preferences"
    poi = {"tags": ["outdoor", "mountain"]}

    score = calculate_preference_score(poi, user)

    assert score == 0.0  # Missing key treated as empty


def test_poi_missing_tags_key():
    """Test POI bez klucza tags - neutralne."""
    user = {"preferences": ["outdoor", "family"]}
    poi = {}  # Brak klucza "tags"

    score = calculate_preference_score(poi, user)

    assert score == 0.0  # Missing key treated as empty


def test_multiple_matches():
    """Test wiele matchów - wszystkie preferencje pasują."""
    user = {"preferences": ["outdoor", "family", "hiking", "nature"]}
    poi = {"tags": ["outdoor", "family", "hiking", "nature", "mountain"]}

    score = calculate_preference_score(poi, user)

    assert score == 20.0  # 4 matches * 5 points each


def test_case_sensitivity():
    """Test case sensitivity - tags muszą matchować dokładnie."""
    user = {"preferences": ["Outdoor", "Family"]}
    poi = {"tags": ["outdoor", "family"]}

    score = calculate_preference_score(poi, user)

    # Case sensitive - no matches expected
    assert score == 0.0
