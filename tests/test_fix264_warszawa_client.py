"""FIX #264 — Warszawa retest: caps, geometry ends, meals, Browary, Park Linowy."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.application.services.plan_service import PlanService, _filter_meal_suggestions
from app.domain.models.plan import (
    ItemType,
    RestaurantSuggestion,
    TransitItem,
    TransitMode,
)
from app.domain.planner.engine import visit_duration_hard_cap
from app.domain.planner.poi_copy import build_fallback_copy, classify_poi_category
from app.domain.scoring.family_fit import (
    restaurant_hard_denied_for_group,
    restaurant_matches_target_group,
)
from app.domain.scoring.profile_poi_rules import should_deny_poi_for_profile
from app.infrastructure.repositories import POIRepository
from app.infrastructure.repositories.normalizer import normalize_poi


def _svc() -> PlanService:
    return PlanService(POIRepository(str(Path("data") / "multi_city_attractions.xlsx")))


def test_fix264_kopiec_cap_60():
    assert visit_duration_hard_cap(
        {"name": "Kopiec Powstania Warszawskiego"}, for_scheduling=True,
    ) == 60


def test_fix264_most_swietokrzyski_cap_30():
    assert visit_duration_hard_cap(
        {"name": "Most Świętokrzyski"}, for_scheduling=True,
    ) == 30


def test_fix264_jeziorko_cap_150():
    assert visit_duration_hard_cap(
        {"name": "Jeziorko Czerniakowskie"}, for_scheduling=True,
    ) == 150


def test_fix264_browary_coords_forced():
    poi = normalize_poi(
        {
            "name": "Browary Warszawskie",
            "city": "Warszawa",
            "lat": 52.2223,
            "lng": 21.0110,
            "time_min": 60,
            "time_max": 120,
        },
        0,
    )
    assert abs(float(poi["lat"]) - 52.2345) < 0.001
    assert abs(float(poi["lng"]) - 20.9877) < 0.001


def test_fix264_geometry_end_mismatch_rebuilt():
    svc = _svc()
    it = TransitItem(
        type=ItemType.TRANSIT,
        mode=TransitMode.WALK,
        from_location="Bulwary Wiślane",
        to_location="Restauracja Delicja Polska",
        start_time="12:00",
        end_time="12:15",
        duration_min=15,
        distance_km=1.2,
        routing_source="estimated_walk",
        # Ends at wrong place (Manufaktura-ish) while to is Delicja.
        geometry=[[21.01, 52.24], [20.99, 52.23]],
        geometry_latlng=[[52.24, 21.01], [52.23, 20.99]],
    )
    cmap = {
        "Bulwary Wiślane": {"name": "Bulwary Wiślane", "lat": 52.241, "lng": 21.028},
        "Restauracja Delicja Polska": {
            "name": "Restauracja Delicja Polska", "lat": 52.248, "lng": 21.015,
        },
    }
    out = svc._normalize_transit_routing_item(it, cmap, {"requested_city": "Warszawa"})
    gll = getattr(out, "geometry_latlng", None) or []
    assert gll and abs(float(gll[-1][0]) - 52.248) < 0.002
    assert abs(float(gll[-1][1]) - 21.015) < 0.002


def test_fix264_solo_hard_denies_family_meals():
    assert restaurant_hard_denied_for_group(
        {"name": "Gospoda", "target_groups": ["family_kids", "friends"]},
        {"target_group": "solo"},
    )
    assert restaurant_matches_target_group(
        {"name": "Lindleya", "target_groups": ["friends", "seniors"]},
        {"target_group": "solo"},
    )


def test_fix264_couples_hard_denies_friends_only():
    assert restaurant_hard_denied_for_group(
        {"name": "Pianka drink & food", "target_groups": ["friends"]},
        {"target_group": "couples"},
    )


def test_fix264_seniors_filter_prefers_senior_tags():
    sugs = [
        RestaurantSuggestion(
            id="1", name="Gospoda", lat=52.24, lng=21.01,
            cuisine_type="polish", meal_type="all",
            target_groups=["family_kids", "friends"],
        ),
        RestaurantSuggestion(
            id="2", name="Lindleya", lat=52.22, lng=21.00,
            cuisine_type="polish", meal_type="all",
            target_groups=["friends", "seniors"],
        ),
    ]
    out = _filter_meal_suggestions(sugs, target_group="seniors")
    assert out and out[0].name == "Lindleya"


def test_fix264_filter_solo_prefers_seniors_friendly():
    sugs = [
        RestaurantSuggestion(
            id="1", name="Gospoda", lat=52.24, lng=21.01,
            cuisine_type="polish", meal_type="all",
            target_groups=["family_kids", "friends"],
        ),
        RestaurantSuggestion(
            id="2", name="Lindleya", lat=52.22, lng=21.00,
            cuisine_type="polish", meal_type="all",
            target_groups=["friends", "seniors"],
        ),
    ]
    out = _filter_meal_suggestions(sugs, target_group="solo")
    assert out and out[0].name == "Lindleya"


def test_fix264_muzeum_ewolucji_is_museum_not_amusement():
    assert classify_poi_category({"name": "Muzeum Ewolucji"}) == "museum"
    desc, tip = build_fallback_copy(
        {
            "name": "Muzeum Ewolucji",
            "city": "Warszawa",
            "ticket_normal": 0,
            "pro_tip": "Kup bilet z wyprzedzeniem.",
        }
    )
    assert "park tematycznego" not in (desc or "").lower()
    assert "bilet" not in (tip or "").lower()


def test_fix264_park_linowy_denied_for_relax_solo():
    assert should_deny_poi_for_profile(
        {"name": "Park Linowy Warszawa", "tags": []},
        {
            "target_group": "solo",
            "travel_style": "relax",
            "preferences": ["nature_landscape", "relaxation"],
        },
    )


def test_fix264_force_browary_on_timeline():
    svc = _svc()
    it = SimpleNamespace(
        type=ItemType.ATTRACTION,
        name="Browary Warszawskie",
        lat=52.2223,
        lng=21.0110,
        model_copy=lambda update: SimpleNamespace(
            type=ItemType.ATTRACTION,
            name="Browary Warszawskie",
            lat=update["lat"],
            lng=update["lng"],
        ),
    )
    out = svc._force_known_good_poi_coords([it], day_num=1)
    assert abs(float(out[0].lat) - 52.2345) < 0.001
    assert abs(float(out[0].lng) - 20.9877) < 0.001
