"""Test configuration and fixtures."""

import os
import tempfile

import pytest

from app.infrastructure.config.settings import settings
from app.infrastructure.routing.cache import clear_memory_cache


@pytest.fixture(scope="session", autouse=True)
def _offline_routing():
    """FIX #253: regression runs must not depend on the ORS network or on cache.

    Two sources made the same client json produce different plans on different
    runs. First, a live key in .env meant every plan issued real HTTP calls, so
    a leg that hit a 429 silently fell back to haversine. Second, travel times
    are cached on disk for 60 days under .cache/ors_routes, and
    test_fix220_routing writes a mocked Wrocław route into that very cache — so
    plans depended on which tests had ever run on the machine. Tests get a
    throwaway cache directory and haversine only; production keeps both.
    """
    previous_enabled = settings.ors_enabled
    previous_dir = os.environ.get("ORS_CACHE_DIR")
    tmp = tempfile.TemporaryDirectory(prefix="ors_routes_test_")
    settings.ors_enabled = False
    os.environ["ORS_CACHE_DIR"] = tmp.name
    clear_memory_cache()
    yield
    settings.ors_enabled = previous_enabled
    if previous_dir is None:
        os.environ.pop("ORS_CACHE_DIR", None)
    else:
        os.environ["ORS_CACHE_DIR"] = previous_dir
    clear_memory_cache()
    tmp.cleanup()


@pytest.fixture(autouse=True)
def _empty_route_cache():
    """FIX #253: no test inherits travel times computed by an earlier test."""
    clear_memory_cache()
    cache_dir = os.environ.get("ORS_CACHE_DIR")
    if cache_dir and os.path.isdir(cache_dir):
        for entry in os.listdir(cache_dir):
            try:
                os.remove(os.path.join(cache_dir, entry))
            except OSError:
                pass
    yield


@pytest.fixture
def sample_trip_input() -> dict:
    """Sample trip input for testing.
    
    TODO: add more test cases for different group types
    """
    return {
        "location": {
            "query": "Kraków",
            "location_id": "krakow",
            "type": "city",
            "country": "PL",
        },
        "group": {"type": "couple"},
        "travel_style": "cultural",
        "interests": ["museums", "castles"],
        "trip_length": {"days": 1, "start_date": "2026-01-25"},
        "daily_time_window": {"start": "10:00", "end": "19:00"},
        "budget": {"level": "standard", "currency": "PLN"},
        "transport_modes": ["car", "walk"],
        "start_point": {"type": "city_center"},
        "meta": {"language": "pl", "timezone": "Europe/Warsaw"},
    }


@pytest.fixture
def sample_poi() -> dict:
    # Basic POI structure for tests
    return {
        "name": "Wawel Castle",
        "lat": 50.054,
        "lng": 19.935,
        "time_min": 60,
        "time_max": 120,
        "must_see_score": 5,
        "target_group": "couple",
        "type_of_attraction": "castle",
        "tags": ["history", "architecture"],
        "opening_hours": "09:00-17:00",
        "budget_type": "standard",
        "crowd_level": 2,
        "ticket_normal": 30,
        "ticket_reduced": 20,
        "free_entry": False,
        "parking_name": "Parking Wawel",
        "parking_lat": 50.053,
        "parking_lng": 19.934,
        "weather_dependent": False,
        "seasonal_availability": "all",
    }
