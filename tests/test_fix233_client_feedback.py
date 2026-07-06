"""FIX #233 — unit tests for client feedback rules (global + per-city)."""

from __future__ import annotations

from app.domain.planner.engine import (
    choose_duration,
    is_seasonal_water_poi_out_of_season,
    poi_geo_region_key,
    should_block_premature_excursion_return,
)
from app.domain.scoring.profile_poi_rules import (
    is_active_city_poi,
    profile_poi_score_delta,
    should_deny_poi_for_profile,
)
from app.infrastructure.repositories.normalizer import _normalize_parking_type


def test_parking_type_defaults_paid():
    assert _normalize_parking_type("") == "paid"
    assert _normalize_parking_type(None) == "paid"
    assert _normalize_parking_type("free") == "free"
    assert _normalize_parking_type("darmowy") == "free"
    assert _normalize_parking_type("paid") == "paid"
    assert _normalize_parking_type("płatny") == "paid"


def test_choose_duration_minimums_fix233():
    poi = {"name": "Kopiec Krakusa", "time_min": 15, "time_max": 30, "type": "poi"}
    dur = choose_duration(poi, 9 * 60, 20 * 60, lunch_done=True)
    assert dur >= 45

    poi2 = {
        "name": "Górnośląski Park Etnograficzny",
        "time_min": 25,
        "time_max": 120,
        "type": "poi",
    }
    dur2 = choose_duration(poi2, 9 * 60, 20 * 60, lunch_done=True)
    assert dur2 >= 90

    poi3 = {
        "name": "Muzeum Powstania Wielkopolskiego 1918-1919",
        "time_min": 23,
        "time_max": 60,
        "type": "museum",
    }
    dur3 = choose_duration(poi3, 9 * 60, 20 * 60, lunch_done=True)
    assert dur3 >= 45


def test_geo_regions_gniezno_gliwice_suntago_modlin():
    assert poi_geo_region_key({"name": "Katedra Gnieźnieńska", "city": "Gniezno"}) == "region_gniezno"
    assert poi_geo_region_key({"name": "Kolejkowo", "city": "Gliwice"}) == "region_gliwice"
    assert poi_geo_region_key({"name": "Suntago", "city": "Wręcza"}) == "region_suntago"
    assert poi_geo_region_key({"name": "Twierdza Modlin", "city": "Nowy Dwór"}) == "region_modlin"


def test_block_premature_excursion_return():
    plan = [{"type": "attraction", "poi": {"name": "Katedra Gnieźnieńska", "city": "Gniezno"}}]
    ctx = {"day_geo_region": "region_gniezno"}
    city_poi = {"name": "Rynek", "city": "Poznań"}
    assert should_block_premature_excursion_return(city_poi, ctx, plan) is True
    gniezno2 = {"name": "Muzeum Początków Państwa", "city": "Gniezno"}
    assert should_block_premature_excursion_return(gniezno2, ctx, plan) is False


def test_seasonal_water_winter_block():
    poi = {"name": "Rejs po Odrze"}
    assert is_seasonal_water_poi_out_of_season(poi, {"season": "winter"}) is True
    assert is_seasonal_water_poi_out_of_season(poi, {"season": "summer"}) is False


def test_family_kids_denies_powazki_and_schindler():
    user = {"target_group": "family_kids", "preferences": [], "travel_style": "balanced"}
    assert should_deny_poi_for_profile({"name": "Cmentarz Powązkowski"}, user)
    assert should_deny_poi_for_profile({"name": "Fabryka Schindlera"}, user)


def test_adventure_active_boost_and_museum_demote():
    user = {
        "target_group": "friends",
        "travel_style": "adventure",
        "preferences": ["active_sport"],
    }
    hydropolis = {"name": "Hydropolis", "tags": ["interactive_exhibits"]}
    assert profile_poi_score_delta(hydropolis, user, context={"day_active_count": 1}) > 0
    museum = {"name": "Muzeum Geologiczne", "tags": ["museum_heritage"]}
    assert profile_poi_score_delta(museum, user, context={"day_active_count": 1}) < 0


def test_water_attractions_malta_boost():
    user = {"target_group": "couples", "preferences": ["water_attractions"], "travel_style": "relax"}
    malta = {"name": "Jezioro Maltańskie", "tags": ["lake"]}
    assert profile_poi_score_delta(malta, user) >= 80


def test_is_active_city_poi():
    assert is_active_city_poi({"name": "Pixel XL", "tags": []})
    assert is_active_city_poi({"name": "Park Linowy", "tags": []})
    assert not is_active_city_poi({"name": "Muzeum Geologiczne", "tags": ["museum_heritage"]})
