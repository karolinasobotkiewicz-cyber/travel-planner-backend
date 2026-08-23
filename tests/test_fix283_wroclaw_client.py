"""FIX #283 — Wrocław leftover: Iluzja pin, durations, deny, micro-car, warnings."""
from __future__ import annotations

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    ItemType,
    ParkingInfo,
    ParkingType,
    TransitItem,
    TransitMode,
)
from app.domain.planner.engine import choose_duration, visit_duration_hard_cap
from app.domain.scoring.profile_poi_rules import should_deny_poi_for_profile
from app.infrastructure.repositories.normalizer import normalize_poi


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur, *, lat=51.11, lng=17.03, parking=None):
    kwargs = dict(
        type=ItemType.ATTRACTION,
        poi_id=f"id-{name}",
        name=name,
        description_short="",
        start_time=start,
        end_time=end,
        duration_min=dur,
        lat=lat,
        lng=lng,
        address="Świdnicka 36, 50-066 Wrocław",
        cost_estimate=0,
    )
    if parking is not None:
        kwargs["parking"] = parking
    return AttractionItem.model_construct(**kwargs)


def test_pajakow_cap_is_60():
    assert visit_duration_hard_cap({"name": "Wystawa Pająków"}) == 60
    dur = choose_duration(
        {"name": "Wystawa Pająków", "time_min": 40, "time_max": 180, "type": "museum"},
        10 * 60,
        19 * 60,
        True,
    )
    assert dur <= 60


def test_hydropolis_floor_90():
    dur = choose_duration(
        {"name": "Hydropolis", "time_min": 40, "time_max": 120, "type": "museum"},
        10 * 60,
        19 * 60,
        True,
    )
    assert dur >= 90


def test_japonski_floor_45():
    dur = choose_duration(
        {"name": "Ogród Japoński", "time_min": 20, "time_max": 90, "type": "park"},
        10 * 60,
        16 * 60,
        True,
    )
    assert dur >= 45


def test_adventure_rynek_capped_75():
    dur = choose_duration(
        {"name": "Rynek we Wrocławiu", "time_min": 60, "time_max": 180, "type": "landmark"},
        9 * 60,
        19 * 60,
        True,
        user={"travel_style": "adventure", "target_group": "friends"},
    )
    assert dur <= 75


def test_gojump_denied_for_seniors_relax_cultural():
    poi = {"name": "GoJump Trampoliny"}
    seniors = {
        "target_group": "seniors",
        "travel_style": "relax",
        "preferences": ["museum_heritage", "nature_landscape", "relaxation"],
    }
    cultural = {
        "target_group": "couples",
        "travel_style": "cultural",
        "preferences": ["museum_heritage", "relaxation", "local_food_experience"],
    }
    relax = {
        "target_group": "solo",
        "travel_style": "relax",
        "preferences": ["nature_landscape", "relaxation"],
    }
    assert should_deny_poi_for_profile(poi, seniors) is True
    assert should_deny_poi_for_profile(poi, cultural) is True
    assert should_deny_poi_for_profile(poi, relax) is True
    assert should_deny_poi_for_profile(
        {"name": "CityPaintball Wrocław"}, seniors,
    ) is True


def test_arboretum_not_winter_denied():
    user = {
        "target_group": "solo",
        "travel_style": "balanced",
        "preferences": ["nature_landscape", "museum_heritage"],
        "start_date": "2026-02-20",
    }
    assert should_deny_poi_for_profile({"name": "Arboretum Wojsławice"}, user) is False
    assert should_deny_poi_for_profile({"name": "Grabowy Labirynt"}, user) is True


def test_iluzja_normalizer_and_parking_coords():
    poi = normalize_poi({
        "Name": "Muzeum Świat Iluzji we Wrocławiu",
        "City": "Wrocław",
        "lat": 51.1069,
        "lng": 17.0773,
        "parking_lat": 51.1069,
        "parking_lng": 17.0773,
        "Address": "Świdnicka 36, 50-066 Wrocław",
    }, 0)
    assert abs(float(poi["lat"]) - 51.1070) < 0.002
    assert abs(float(poi["lng"]) - 17.0325) < 0.003
    assert abs(float(poi["parking_lat"]) - 51.1070) < 0.002
    assert abs(float(poi["parking_lng"]) - 17.0325) < 0.003


def test_iluzja_force_rewrites_parking():
    park = ParkingInfo(
        name="Parking",
        address="",
        parking_type=ParkingType.PAID,
        cost=None,
        walk_time_min=5,
        lat=51.1069,
        lng=17.0773,
    )
    items = [
        _attr(
            "Muzeum Świat Iluzji we Wrocławiu",
            "13:30", "14:30", 60,
            lat=51.1070, lng=17.0325, parking=park,
        ),
    ]
    out = _svc()._force_known_good_poi_coords(items, day_num=2)
    assert abs(out[0].lat - 51.1070) < 0.002
    assert abs(out[0].lng - 17.0325) < 0.003
    assert abs(out[0].parking.lat - 51.1070) < 0.002
    assert abs(out[0].parking.lng - 17.0325) < 0.003


def test_micro_38m_is_walk_not_10min_car():
    items = [
        TransitItem(
            type=ItemType.TRANSIT,
            start_time="17:10",
            end_time="17:20",
            duration_min=10,
            mode=TransitMode.CAR,
            from_location="Izba Muzealna Ziemi Oławskiej",
            to_location="Rynek w Oławie",
            routing_source="estimated_road",
            distance_km=0.038,
        ),
    ]
    out = _svc()._sanitize_walk_leg_durations(items, {}, day_num=7)
    assert out[0].mode == TransitMode.WALK
    assert out[0].duration_min <= 6
    assert float(out[0].distance_km) < 0.1


def test_far_return_ignores_38m_wroclaw_label():
    items = [
        _attr("Rynek w Oławie", "15:00", "16:00", 60, lat=50.9430, lng=17.2956),
        TransitItem(
            type=ItemType.TRANSIT,
            start_time="16:00",
            end_time="16:10",
            duration_min=10,
            mode=TransitMode.CAR,
            from_location="Rynek w Oławie",
            to_location="Wrocław centrum",
            routing_source="estimated_road",
            distance_km=0.038,
        ),
    ]
    out = _svc()._ensure_far_excursion_return(
        items,
        {"requested_city": "Wrocław", "day_end": "20:00"},
        day_num=7,
    )
    returns = [
        it for it in out
        if getattr(it, "type", None) == ItemType.TRANSIT
        and "wrocław" in (getattr(it, "to_location", "") or "").lower()
        and float(getattr(it, "distance_km", 0) or 0) >= 15
    ]
    assert returns, "Oława day must get a real ≥15 km drive home"
    assert returns[0].duration_min >= 25


def test_olawa_return_when_last_stop_hits_day_end():
    items = [
        _attr("Rynek w Oławie", "18:30", "20:00", 90, lat=50.9430, lng=17.2956),
    ]
    out = _svc()._ensure_far_excursion_return(
        items,
        {"requested_city": "Wrocław", "day_end": "20:00"},
        day_num=7,
    )
    returns = [
        it for it in out
        if getattr(it, "type", None) == ItemType.TRANSIT
        and "wrocław" in (getattr(it, "to_location", "") or "").lower()
    ]
    assert returns, "return must exist even when the last sight hits 20:00"
    assert returns[0].duration_min >= 25


def test_ghost_aquapark_warning_is_dropped():
    items = [_attr("Rynek we Wrocławiu", "10:00", "11:00", 60)]
    day = type("D", (), {"items": items})()
    warnings = [
        {
            "type": "budget_constraint_active",
            "expensive_item": "Aquapark Wrocław",
            "message": "Dzień 1: 'Aquapark Wrocław' pochłania 80% dziennego budżetu",
        },
        {
            "type": "preference_not_covered",
            "preference": "water_attractions",
            "message": "Preferencja nie pokryta",
        },
    ]
    out = _svc()._scrub_unscheduled_poi_warnings(warnings, [day])
    types = [w["type"] for w in out]
    assert "budget_constraint_active" not in types
    assert "preference_not_covered" in types
