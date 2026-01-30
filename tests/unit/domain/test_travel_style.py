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

    assert score == 6.0  # Perfect match


def test_perfect_match_relax():
    """Test perfect match - relax user + relax POI."""
    user = {"travel_style": "relax"}
    poi = {"activity_style": "relax"}

    score = calculate_travel_style_score(poi, user)

    assert score == 6.0  # Perfect match


def test_perfect_match_cultural():
    """Test perfect match - cultural user + balanced POI."""
    user = {"travel_style": "cultural"}
    poi = {"activity_style": "balanced"}

    score = calculate_travel_style_score(poi, user)

    assert score == 6.0  # Perfect match


def test_partial_match_cultural_active():
    """Test partial match - cultural user + active POI."""
    user = {"travel_style": "cultural"}
    poi = {"activity_style": "active"}

    score = calculate_travel_style_score(poi, user)

    assert score == 3.0  # Partial match


def test_balanced_user_always_ok():
    """Test balanced user - zawsze dostaje bonus."""
    user = {"travel_style": "balanced"}
    poi = {"activity_style": "active"}

    score = calculate_travel_style_score(poi, user)

    assert score == 3.0  # Balanced user OK z wszystkim


def test_balanced_poi_always_ok():
    """Test balanced POI - zawsze dostaje bonus."""
    user = {"travel_style": "adventure"}
    poi = {"activity_style": "balanced"}

    score = calculate_travel_style_score(poi, user)

    assert score == 3.0  # Balanced POI OK z wszystkim


def test_mismatch():
    """Test mismatch - relax user + active POI."""
    user = {"travel_style": "relax"}
    poi = {"activity_style": "active"}

    score = calculate_travel_style_score(poi, user)

    assert score == 0.0  # Mismatch


def test_user_no_travel_style():
    """Test user bez travel_style - default balanced."""
    user = {}  # Brak travel_style
    poi = {"activity_style": "active"}

    score = calculate_travel_style_score(poi, user)

    assert score == 3.0  # Default balanced → partial match


def test_poi_no_activity_style():
    """Test POI bez activity_style - default balanced."""
    user = {"travel_style": "adventure"}
    poi = {}  # Brak activity_style

    score = calculate_travel_style_score(poi, user)

    assert score == 3.0  # Default balanced → partial match


def test_both_balanced():
    """Test oba balanced - partial match."""
    user = {"travel_style": "balanced"}
    poi = {"activity_style": "balanced"}

    score = calculate_travel_style_score(poi, user)

    assert score == 3.0  # Balanced + balanced = partial


def test_empty_strings():
    """Test puste stringi - default do balanced."""
    user = {"travel_style": ""}
    poi = {"activity_style": ""}

    score = calculate_travel_style_score(poi, user)

    assert score == 3.0  # Empty strings → balanced → partial


def test_none_values():
    """Test None values - default do balanced."""
    user = {"travel_style": None}
    poi = {"activity_style": None}

    score = calculate_travel_style_score(poi, user)

    assert score == 3.0  # None → balanced → partial
