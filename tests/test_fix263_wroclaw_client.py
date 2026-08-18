"""FIX #263 — Wrocław retest: meals, free_time merge, parking, Loopy, far POI."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.application.services.plan_service import (
    PlanService,
    _filter_meal_suggestions,
    _restaurant_dict_to_suggestion,
)
from app.domain.models.plan import (
    DinnerBreakItem,
    FreeTimeItem,
    ItemType,
    LunchBreakItem,
    TransitItem,
    TransitMode,
)
from app.domain.planner.poi_copy import build_fallback_copy
from app.domain.scoring.family_fit import (
    restaurant_hard_denied_for_group,
    should_exclude_by_target_group,
)
from app.infrastructure.repositories import POIRepository


def _svc() -> PlanService:
    return PlanService(POIRepository(str(Path("data") / "multi_city_attractions.xlsx")))


def test_fix263_restaurant_description_from_pro_tip():
    sug = _restaurant_dict_to_suggestion(
        {
            "id": "r1",
            "name": "Bernard",
            "lat": 51.1,
            "lng": 17.0,
            "cuisine_type": "polish,regional",
            "pro_tip": "Zarezerwuj stolik z wyprzedzeniem, zwłaszcza w weekendy.",
            "target_groups": ["friends"],
        },
        "dinner",
    )
    assert sug.description
    assert "Zarezerwuj" in sug.description or "polish" in sug.description.lower()


def test_fix263_cork_denied_for_family():
    assert restaurant_hard_denied_for_group(
        {"name": "The Cork", "target_groups": ["couples"]},
        {"target_group": "family_kids"},
    )


def test_fix263_filter_drops_couples_only_for_family():
    from app.domain.models.plan import RestaurantSuggestion

    sugs = [
        RestaurantSuggestion(
            id="1", name="The Cork", lat=51.1, lng=17.0,
            target_groups=["couples"], meal_type="dinner",
        ),
        RestaurantSuggestion(
            id="2", name="Pierogarnia Ze Smakiem", lat=51.1, lng=17.0,
            target_groups=["family_kids", "friends"], meal_type="dinner",
        ),
    ]
    out = _filter_meal_suggestions(sugs, target_group="family_kids")
    assert out
    assert "cork" not in out[0].name.lower()


def test_fix263_loopy_denied_for_solo():
    assert should_exclude_by_target_group(
        {"name": "Park Rozrywki Loopy's World", "target_groups": ["family_kids"]},
        {"target_group": "solo"},
    )


def test_fix263_mamuta_free_tip_no_ticket():
    desc, tip = build_fallback_copy({
        "name": "Park Mamuta",
        "city": "Wrocław",
        "ticket_normal": 0,
        "pro_tip": "Kup bilet online z wyprzedzeniem.",
        "description_short": "",
    })
    assert tip
    assert "bilet" not in tip.lower() or "darmow" in tip.lower()


def test_fix263_merge_abutting_free_time():
    svc = _svc()
    items = [
        FreeTimeItem(
            type=ItemType.FREE_TIME,
            start_time="16:00",
            end_time="16:52",
            duration_min=52,
            label="Popołudniowa przerwa",
        ),
        FreeTimeItem(
            type=ItemType.FREE_TIME,
            start_time="16:52",
            end_time="17:27",
            duration_min=35,
            label="Czas dla siebie",
        ),
    ]
    out = svc._merge_abutting_free_time_hard(items, day_num=1)
    fts = [it for it in out if it.type == ItemType.FREE_TIME]
    assert len(fts) == 1
    assert fts[0].duration_min == 87


def test_fix263_strip_far_last_without_return():
    svc = _svc()
    items = [
        SimpleNamespace(
            type=ItemType.ATTRACTION,
            name="Rynek we Wrocławiu",
            start_time="10:00",
            end_time="12:00",
            duration_min=120,
            lat=51.11,
            lng=17.03,
        ),
        SimpleNamespace(
            type=ItemType.ATTRACTION,
            name="Arboretum Wojsławice",
            start_time="15:00",
            end_time="18:00",
            duration_min=180,
            lat=50.75,
            lng=16.85,
        ),
    ]
    out = svc._strip_far_last_excursion(
        items, {"requested_city": "Wrocław", "day_end": "20:00"}, day_num=5,
    )
    names = [getattr(it, "name", "") for it in out if _is_attr(it)]
    assert "Arboretum Wojsławice" in names
    trans = [
        it for it in out
        if str(getattr(getattr(it, "type", None), "value", it.type)).lower()
        == "transit"
    ]
    assert trans
    assert "wrocław" in (getattr(trans[-1], "to_location", "") or "").lower()


def _is_attr(it) -> bool:
    t = getattr(it, "type", None)
    return str(getattr(t, "value", t) or "") == ItemType.ATTRACTION.value


def test_fix263_parking_walk_preserves_zero():
    svc = _svc()
    # Direct unit: generation path uses explicit 0, not default 5.
    poi = {
        "poi_id": "x",
        "id": "x",
        "name": "Test POI",
        "lat": 51.1,
        "lng": 17.0,
        "address": "Wrocław",
        "city": "Wrocław",
        "description_short": "x",
        "ticket_normal": 0,
        "ticket_reduced": 0,
        "parking_walk_time_min": 0,
        "parking_name": "P",
        "time_min": 30,
        "time_max": 60,
    }
    item = svc._generate_attraction_item(
        poi, "10:00", {"target_group": "couples"}, "couples", {}, None,
    )
    assert item.parking.walk_time_min == 0


def test_fix263_implausible_car_duration_stretched():
    svc = _svc()
    it = TransitItem(
        type=ItemType.TRANSIT,
        mode=TransitMode.CAR,
        from_location="A",
        to_location="B",
        start_time="12:00",
        end_time="12:02",
        duration_min=2,
        distance_km=6.0,
        routing_source="estimated_road",
    )
    cmap = {
        "A": {"name": "A", "lat": 51.10, "lng": 17.00},
        "B": {"name": "B", "lat": 51.14, "lng": 17.06},
    }
    out = svc._fix_implausible_transit_duration(
        it, cmap, {"has_car": True},
    )
    assert int(out.duration_min) >= 8
