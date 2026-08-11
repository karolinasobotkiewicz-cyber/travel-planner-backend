"""FIX #262 — Warszawa retest: caps, underground, day_end, meals, walk realism."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    DinnerBreakItem,
    ItemType,
    LunchBreakItem,
    RestaurantSuggestion,
    TransitItem,
    TransitMode,
)
from app.domain.planner.engine import visit_duration_hard_cap
from app.domain.scoring.preference_coverage import poi_covers_preference_report
from app.infrastructure.repositories import POIRepository


def _svc() -> PlanService:
    return PlanService(POIRepository(str(Path("data") / "multi_city_attractions.xlsx")))


def _rest(name: str, lat: float = 52.24, lng: float = 21.01) -> RestaurantSuggestion:
    return RestaurantSuggestion(
        id=f"id-{name.lower().replace(' ', '-')}",
        name=name,
        lat=lat,
        lng=lng,
        cuisine_type="polish",
        meal_type="all",
    )


def test_fix262_swiat_iluzji_cap_90():
    assert visit_duration_hard_cap(
        {"name": "Muzeum Świat Iluzji"}, for_scheduling=True,
    ) == 90


def test_fix262_stare_miasto_cap_120():
    assert visit_duration_hard_cap(
        {"name": "Stare Miasto w Warszawie"}, for_scheduling=True,
    ) == 120


def test_fix262_powstanie_covers_underground():
    poi = {
        "name": "Muzeum Powstania Warszawskiego",
        "city": "Warszawa",
        "tags": [],
    }
    assert poi_covers_preference_report(poi, "underground")


def test_fix262_clamp_drops_past_day_end_transit():
    svc = _svc()
    items = [
        TransitItem(
            type=ItemType.TRANSIT,
            mode=TransitMode.CAR,
            from_location="A",
            to_location="B",
            start_time="20:00",
            end_time="20:18",
            duration_min=18,
            distance_km=3.0,
            routing_source="estimated_road",
        ),
    ]
    out = svc._clamp_timeline_to_day_end(
        items, {"day_end": "20:00"}, day_num=2,
    )
    assert out == []


def test_fix262_walk_estimated_road_becomes_car_when_far():
    svc = _svc()
    it = TransitItem(
        type=ItemType.TRANSIT,
        mode=TransitMode.WALK,
        from_location="Miniciti",
        to_location="Gosciniec",
        start_time="12:00",
        end_time="12:10",
        duration_min=10,
        distance_km=3.56,
        routing_source="estimated_road",
    )
    cmap = {
        "Miniciti": {"name": "Miniciti", "lat": 52.23, "lng": 21.01},
        "Gosciniec": {"name": "Gosciniec", "lat": 52.25, "lng": 21.04},
    }
    out = svc._fix_unrealistic_transit_modes(
        [it], cmap,
        {"has_car": True, "transport_modes": ["car"]},
        day_num=3,
    )
    assert len(out) == 1
    mode = getattr(out[0].mode, "value", out[0].mode)
    assert str(mode) == "car"
    assert "road" in str(out[0].routing_source or "").lower()


def test_fix262_dedupe_lunch_dinner_same_restaurant():
    svc = _svc()
    lunch = LunchBreakItem(
        type=ItemType.LUNCH_BREAK,
        start_time="12:00",
        end_time="13:00",
        duration_min=60,
        suggestions=[_rest("U Szwejka")],
    )
    dinner = DinnerBreakItem(
        type=ItemType.DINNER_BREAK,
        start_time="18:00",
        end_time="19:00",
        duration_min=60,
        suggestions=[_rest("U Szwejka")],
    )
    ctx = {
        "restaurants_available": [
            {
                "name": "U Szwejka",
                "lat": 52.24,
                "lng": 21.01,
                "meal_type": "all",
            },
            {
                "name": "Medusa Warszawa",
                "lat": 52.23,
                "lng": 21.02,
                "meal_type": "dinner",
            },
        ],
    }
    out = svc._dedupe_lunch_dinner_restaurants(
        [lunch, dinner], ctx, day_num=3,
    )
    dinner_out = next(
        it for it in out if it.type == ItemType.DINNER_BREAK
    )
    name = dinner_out.suggestions[0].name if dinner_out.suggestions else ""
    assert "szwejka" not in name.lower()


def test_fix262_repair_car_chain_rewrites_from():
    svc = _svc()
    items = [
        TransitItem(
            type=ItemType.TRANSIT,
            mode=TransitMode.CAR,
            from_location="Warszawa",
            to_location="Stare Miasto w Warszawie",
            start_time="09:00",
            end_time="09:15",
            duration_min=15,
            distance_km=2.0,
            routing_source="estimated_road",
        ),
        TransitItem(
            type=ItemType.TRANSIT,
            mode=TransitMode.CAR,
            from_location="Restauracja Delicja Polska",
            to_location="Park Wodny Warszawianka",
            start_time="12:35",
            end_time="12:50",
            duration_min=15,
            distance_km=5.0,
            routing_source="estimated_road",
        ),
    ]
    cmap = {
        "Stare Miasto w Warszawie": {
            "name": "Stare Miasto w Warszawie", "lat": 52.25, "lng": 21.01,
        },
        "Restauracja Delicja Polska": {
            "name": "Restauracja Delicja Polska", "lat": 52.249, "lng": 21.012,
        },
        "Park Wodny Warszawianka": {
            "name": "Park Wodny Warszawianka", "lat": 52.18, "lng": 21.05,
        },
    }
    out = svc._repair_car_chain(items, cmap, {"has_car": True}, day_num=3)
    second = out[1]
    assert second.from_location == "Stare Miasto w Warszawie"


def test_fix262_inject_attraction_into_free_time():
    from app.domain.models.plan import FreeTimeItem

    svc = _svc()
    items = [
        SimpleNamespace(
            type=ItemType.ATTRACTION,
            name="Stare Miasto w Warszawie",
            start_time="09:15",
            end_time="11:15",
            duration_min=120,
            lat=52.25,
            lng=21.01,
        ),
        FreeTimeItem(
            type=ItemType.FREE_TIME,
            start_time="12:45",
            end_time="17:15",
            duration_min=270,
            label="Popołudnie",
        ),
    ]
    pool = [
        {
            "name": "Ogród Saski",
            "city": "Warszawa",
            "lat": 52.24,
            "lng": 21.01,
            "type": "poi",
            "time_min": 45,
            "time_max": 90,
            "tags": ["nature_landscape", "relaxation"],
            "ticket_normal": 0,
            "ticket_reduced": 0,
            "address": "Warszawa",
            "description_short": "Park w centrum",
            "poi_id": "ogrod-saski",
        },
    ]
    out = svc._inject_attraction_into_free_time(
        items, pool,
        {"requested_city": "Warszawa", "day_start": "09:00", "day_end": "19:00"},
        {"target_group": "solo", "preferences": ["relaxation"], "travel_style": "relax"},
        day_num=3,
    )
    attrs = [
        it for it in out
        if str(getattr(getattr(it, "type", None), "value", getattr(it, "type", None)))
        == ItemType.ATTRACTION.value
    ]
    assert len(attrs) >= 2
