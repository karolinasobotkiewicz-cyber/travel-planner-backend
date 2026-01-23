"""Test configuration and fixtures."""

import pytest


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
