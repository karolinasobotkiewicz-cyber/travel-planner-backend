"""FIX #234 — client feedback round 5 (5 cities)."""
from __future__ import annotations

import pytest

from app.application.services.plan_service import (
    _filter_meal_suggestions,
    _is_generic_meal_suggestion,
    _restaurant_dict_to_suggestion,
)
from app.domain.filters.seasonality import filter_by_season
from app.domain.planner.city_copy import dinner_suggestions
from app.domain.planner.engine import (
    _meal_restaurant_geo_ok,
    choose_duration,
    is_seasonal_water_poi_out_of_season,
    poi_geo_region_key,
    should_block_premature_excursion_return,
)
from app.domain.scoring.profile_poi_rules import (
    profile_poi_score_delta,
    should_deny_poi_for_profile,
)
from app.infrastructure.repositories.normalizer import normalize_poi
from datetime import datetime


def test_no_generic_dinner_suggestions_city():
    assert dinner_suggestions(False) == []


def test_filter_generic_meal_suggestions():
    generic = _restaurant_dict_to_suggestion("Restauracja w centrum", "dinner")
    real = _restaurant_dict_to_suggestion(
        {"id": "r1", "name": "Pod Wawelem", "lat": 50.05, "lng": 19.94},
        "dinner",
    )
    out = _filter_meal_suggestions([generic, real])
    assert len(out) == 1
    assert out[0].name == "Pod Wawelem"
    assert _is_generic_meal_suggestion(generic)


def test_wieliczka_restaurant_blocked_in_krakow_centre():
    krakow_poi = {"name": "Rynek Główny", "city": "Kraków", "lat": 50.06, "lng": 19.94}
    wieliczka_rest = {"name": "Restauracja Solna", "city": "Wieliczka", "lat": 49.98, "lng": 20.06}
    assert _meal_restaurant_geo_ok(wieliczka_rest, krakow_poi, {}) is False


def test_balanced_museum_demote():
    user = {"target_group": "couples", "travel_style": "balanced", "preferences": []}
    poi = {"name": "Muzeum Test", "tags": ["museum_heritage"]}
    ctx = {"trip_museum_count": 2, "day_museum_count": 1}
    assert profile_poi_score_delta(poi, user, context=ctx) <= -80


def test_couples_cultural_park_wodny_deny():
    user = {"target_group": "couples", "travel_style": "cultural", "preferences": []}
    poi = {"name": "Park Wodny Kraków", "tags": ["aquapark"]}
    assert should_deny_poi_for_profile(poi, user) is True


def test_winter_rejs_blocked():
    poi = {"name": "Rejs statkiem po Odrze", "tags": []}
    ctx = {"season": "winter", "date": datetime(2026, 2, 15)}
    assert is_seasonal_water_poi_out_of_season(poi, ctx) is True


def test_seasonality_filter_rejs_winter():
    pois = [{"name": "Rejs po Odrze", "season_fit": {"winter": 1, "spring": 1, "summer": 1, "autumn": 1}}]
    out = filter_by_season(pois, datetime(2026, 1, 10))
    assert len(out) == 0


def test_excursion_requires_full_cluster():
    ctx = {"day_geo_region": "region_ojcow"}
    city_poi = {"name": "Wawel", "city": "Kraków"}
    plan = [{"type": "attraction", "poi": {"name": "Maczuga Herkulesa", "city": "Ojców"}}]
    ctx["_day_plan_snapshot"] = plan
    assert should_block_premature_excursion_return(city_poi, ctx, plan) is True


def test_pixel_xl_duration():
    poi = {"name": "Pixel XL Poznań", "time_min": 15, "time_max": 30, "type": "poi"}
    user = {"target_group": "friends", "travel_style": "adventure", "preferences": ["active_sport"]}
    dur = choose_duration(poi, 540, 1200, True, user=user)
    assert dur >= 45


def test_fontanna_description_fix():
    raw = {
        "Name": "Fontanna Multimedialna",
        "City": "Wrocław",
        "description_long": "atrakcji letnich w Warszawie",
    }
    norm = normalize_poi(raw, 0)
    assert "Wrocław" in norm["description_long"]
    assert "Warszawie" not in norm["description_long"]


def test_zabrze_geo_region():
    poi = {"name": "Podziemia Zabrze", "city": "Zabrze"}
    assert poi_geo_region_key(poi) == "region_zabrze"
