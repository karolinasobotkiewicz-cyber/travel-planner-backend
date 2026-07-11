"""FIX #235 — client feedback round 6 (transit, meals, kids context, rankings)."""
from __future__ import annotations

import pytest

from app.application.services.plan_service import (
    PlanService,
    _find_next_attraction,
    _is_timeline_attraction,
)
from app.domain.models.plan import (
    AttractionItem,
    DayStartItem,
    ItemType,
    LunchBreakItem,
    ParkingInfo,
    ParkingType,
    TicketInfo,
    TransitItem,
    TransitMode,
)
from app.domain.planner.engine import (
    _tiered_nearby_restaurants,
    should_block_far_region_reentry,
)
from app.domain.scoring.preference_coverage import preference_coverage_adequate
from app.domain.scoring.profile_poi_rules import (
    profile_poi_score_delta,
    should_deny_poi_for_profile,
)
from app.infrastructure.repositories.normalizer import normalize_poi


def _svc() -> PlanService:
    from unittest.mock import MagicMock
    return PlanService(MagicMock())


def _attr(name: str, poi_id: str, start: str, end: str, dur: int) -> AttractionItem:
    return AttractionItem(
        type=ItemType.ATTRACTION,
        poi_id=poi_id,
        name=name,
        start_time=start,
        end_time=end,
        duration_min=dur,
        description_short="test",
        lat=51.1,
        lng=17.0,
        address="test",
        city="Test",
        cost_estimate=0,
        ticket_info=TicketInfo(ticket_normal=0, ticket_reduced=0),
        parking=ParkingInfo(name="Parking", walk_time_min=5, parking_type=ParkingType.FREE),
    )


def test_find_next_attraction_skips_lunch():
    items = [
        _attr("A", "a", "10:00", "11:00", 60),
        TransitItem(type=ItemType.TRANSIT, from_location="A", to_location="B", start_time="11:00", end_time="11:15", duration_min=15, mode=TransitMode.WALK),
        LunchBreakItem(type=ItemType.LUNCH_BREAK, start_time="12:00", end_time="13:00", duration_min=60, suggestions=[]),
        _attr("B", "b", "13:00", "14:00", 60),
    ]
    nxt = _find_next_attraction(items, 1)
    assert nxt is not None
    assert nxt.name == "B"


def test_transit_not_orphaned_before_lunch():
    svc = _svc()
    items = [
        _attr("Rynek", "r", "10:00", "11:00", 60),
        TransitItem(type=ItemType.TRANSIT, from_location="Rynek", to_location="old", start_time="11:00", end_time="11:20", duration_min=20, mode=TransitMode.CAR),
        LunchBreakItem(type=ItemType.LUNCH_BREAK, start_time="12:00", end_time="13:00", duration_min=60, suggestions=[]),
        _attr("Ostrów Tumski", "o", "13:00", "14:00", 60),
    ]
    coords = {
        "Rynek": {"name": "Rynek", "lat": 51.109, "lng": 17.032},
        "Ostrów Tumski": {"name": "Ostrów Tumski", "lat": 51.114, "lng": 17.046},
    }
    out = svc._update_transit_destinations(items, coords)
    transits = [it for it in out if it.type == ItemType.TRANSIT]
    assert len(transits) == 1
    assert transits[0].from_location == "Rynek"
    assert transits[0].to_location == "Ostrów Tumski"


def test_ensure_transits_injects_missing_leg():
    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        _attr("A", "a", "09:00", "10:00", 60),
        _attr("B", "b", "10:30", "11:30", 60),
    ]
    coords = {
        "A": {"name": "A", "lat": 51.10, "lng": 17.03},
        "B": {"name": "B", "lat": 51.12, "lng": 17.05},
    }
    ctx = {"has_car": True, "transport": "car"}
    out = svc._ensure_transits_between_attractions(items, coords, ctx)
    transits = [it for it in out if it.type == ItemType.TRANSIT]
    assert len(transits) == 1
    assert transits[0].from_location == "A"
    assert transits[0].to_location == "B"
    assert transits[0].duration_min >= 5


def test_tiered_meals_nearest_fallback():
    last = {"name": "Rynek", "lat": 51.109, "lng": 17.032}
    restaurants = [
        {"name": "Far Away", "lat": 51.20, "lng": 17.20, "city": "Kraków"},
        {"name": "Near One", "lat": 51.110, "lng": 17.033, "city": "Kraków"},
        {"name": "Near Two", "lat": 51.111, "lng": 17.034, "city": "Kraków"},
    ]
    out = _tiered_nearby_restaurants(restaurants, last, {}, limit=2)
    assert len(out) >= 1
    assert out[0]["name"] in ("Near One", "Near Two")


def test_relaxation_coverage_one_poi_ok():
    pois = [{"name": "Bulwary Wiślane", "tags": ["city_park"]}]
    assert preference_coverage_adequate("relaxation", pois) is True


def test_trip_kids_demote_parks_early():
    user = {"target_group": "family_kids", "travel_style": "balanced", "preferences": []}
    poi = {"name": "Park miejski", "tags": ["park"]}
    ctx = {"trip_kids_attraction_count": 0}
    assert profile_poi_score_delta(poi, user, context=ctx) <= -80


def test_katowice_scw_deny_family_kids():
    user = {"target_group": "family_kids", "travel_style": "balanced", "preferences": []}
    poi = {"name": "Śląskie Centrum Wolności i Solidarności", "tags": ["museum_heritage"]}
    assert should_deny_poi_for_profile(poi, user) is True


def test_far_region_reentry_blocked():
    ctx = {}
    plan = [
        {"type": "attraction", "poi": {"name": "Maczuga", "city": "Ojców"}},
        {"type": "attraction", "poi": {"name": "Wawel", "city": "Kraków"}},
    ]
    opn_poi = {"name": "Jaskinia Ciemna", "city": "Ojców"}
    assert should_block_far_region_reentry(opn_poi, ctx, plan) is True


def test_wedel_description_fix():
    raw = {
        "Name": "Pijalnia Czekolady E.Wedel",
        "City": "Warszawa",
        "description_long": "Muzeum Fabryki Czekolady",
    }
    norm = normalize_poi(raw, 0)
    assert "Pijalnia Czekolady" in norm["description_long"]
    assert "nie mylić" in norm["description_long"].lower()


def test_dworzec_swiebodzki_demote():
    user = {"target_group": "couples", "travel_style": "cultural", "preferences": []}
    poi = {"name": "Dworzec Świebodzki", "tags": []}
    assert profile_poi_score_delta(poi, user, context={}) <= -100
