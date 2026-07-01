"""
Unit tests dla travel_style scoring module.
"""
import pytest
from app.domain.scoring.travel_style import calculate_travel_style_score


def test_perfect_match_adventure():
    """Test perfect match - adventure user + active POI."""
    user = {"travel_style": "adventure"}
    poi = {"activity_style": "active"}

    score = calculate_travel_style_score(poi, user)

    assert score == 18.0  # FIX #229: stronger adventure weight


def test_perfect_match_relax():
    """Test perfect match - relax user + relax POI."""
    user = {"travel_style": "relax"}
    poi = {"activity_style": "relax"}

    score = calculate_travel_style_score(poi, user)

    assert score == 12.0


def test_perfect_match_cultural():
    """Test perfect match - cultural user + balanced POI."""
    user = {"travel_style": "cultural"}
    poi = {"activity_style": "balanced"}

    score = calculate_travel_style_score(poi, user)

    assert score == 10.0


def test_partial_match_cultural_active():
    """Test partial match - cultural user + active POI."""
    user = {"travel_style": "cultural"}
    poi = {"activity_style": "active"}

    score = calculate_travel_style_score(poi, user)

    assert score == 5.0


def test_balanced_user_always_ok():
    """Test balanced user - zawsze dostaje bonus."""
    user = {"travel_style": "balanced"}
    poi = {"activity_style": "active"}

    score = calculate_travel_style_score(poi, user)

    assert score == 4.0


def test_balanced_poi_always_ok():
    """Test balanced POI - zawsze dostaje bonus."""
    user = {"travel_style": "adventure"}
    poi = {"activity_style": "balanced"}

    score = calculate_travel_style_score(poi, user)

    assert score == 8.0


def test_mismatch():
    """Test mismatch - relax user + active POI."""
    user = {"travel_style": "relax"}
    poi = {"activity_style": "active"}

    score = calculate_travel_style_score(poi, user)

    assert score == 0.0  # Mismatch


def test_adventure_relax_penalty():
    """FIX #229: adventure user should penalise passive relax POIs."""
    user = {"travel_style": "adventure"}
    poi = {"activity_style": "relax"}

    score = calculate_travel_style_score(poi, user)

    assert score == -8.0


def test_user_no_travel_style():
    """Test user bez travel_style - default balanced."""
    user = {}  # Brak travel_style
    poi = {"activity_style": "active"}

    score = calculate_travel_style_score(poi, user)

    assert score == 4.0


def test_poi_no_activity_style():
    """Test POI bez activity_style - default balanced."""
    user = {"travel_style": "adventure"}
    poi = {}  # Brak activity_style

    score = calculate_travel_style_score(poi, user)

    assert score == 8.0


def test_both_balanced():
    """Test oba balanced - partial match."""
    user = {"travel_style": "balanced"}
    poi = {"activity_style": "balanced"}

    score = calculate_travel_style_score(poi, user)

    assert score == 4.0


def test_empty_strings():
    """Test puste stringi - default do balanced."""
    user = {"travel_style": ""}
    poi = {"activity_style": ""}

    score = calculate_travel_style_score(poi, user)

    assert score == 4.0


def test_none_values():
    """Test None values - default do balanced."""
    user = {"travel_style": None}
    poi = {"activity_style": None}

    score = calculate_travel_style_score(poi, user)

    assert score == 4.0
