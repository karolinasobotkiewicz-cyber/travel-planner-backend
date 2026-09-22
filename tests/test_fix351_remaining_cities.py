"""FIX #351 — Poznań remaining-city kids floors, ping-pong hops, 18:00 dinner."""
from __future__ import annotations


def _svc():
    from app.application.services.plan_service import PlanService
    from app.infrastructure.repositories.poi_repository import POIRepository
    return PlanService(POIRepository("data/zakopane.xlsx"))


def test_pixel_xl_family_visit_is_padded_to_sixty():
    from app.domain.models.plan import AttractionItem, DayEndItem, DayStartItem, ItemType

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="p", name="Pixel XL Poznań",
            description_short="", why_selected=["x"],
            start_time="10:00", end_time="10:30", duration_min=30,
            lat=52.4069, lng=16.9239, city="Poznań",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {
        "requested_city": "Poznań", "group_type": "family_kids",
        "children_age": 8, "day_start": "09:00", "day_end": "19:00",
    }
    out = svc._pad_remaining_kids_visits(items, ctx, day_num=2)
    pixel = next(it for it in out if "Pixel" in (getattr(it, "name", "") or ""))
    assert int(getattr(pixel, "duration_min")) >= 60
    wro = svc._pad_remaining_kids_visits(
        items, {**ctx, "requested_city": "Wrocław"}, day_num=2,
    )
    wro_px = next(it for it in wro if "Pixel" in (getattr(it, "name", "") or ""))
    assert int(getattr(wro_px, "duration_min")) == 30


def test_hub_pingpong_after_car_is_dropped():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:30"),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="13:41", end_time="13:51",
            duration_min=10, from_location="Poznań",
            to_location="Park Sołacki", mode=TransitMode.CAR, distance_km=3.0,
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="13:51", end_time="14:01",
            duration_min=10, from_location="Park Sołacki",
            to_location="Poznań", mode=TransitMode.WALK, distance_km=0.5,
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="14:01", end_time="14:11",
            duration_min=10, from_location="Poznań",
            to_location="Park Sołacki", mode=TransitMode.WALK, distance_km=0.5,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="s", name="Park Sołacki",
            description_short="", why_selected=["x"],
            start_time="14:22", end_time="15:22", duration_min=60,
            lat=52.4232, lng=16.9020, city="Poznań",
        ),
        DayEndItem(time="18:00"),
    ]
    ctx = {"requested_city": "Poznań"}
    out = svc._scrub_remaining_car_pingpong(items, ctx, day_num=4)
    walks = [
        it for it in out
        if str(getattr(getattr(it, "type", None), "value", "")) == "transit"
        and "walk" in str(getattr(getattr(it, "mode", None), "value", "")).lower()
    ]
    assert len(walks) == 0


def test_remaining_dinner_plants_when_window_is_eighteen():
    from app.domain.models.plan import AttractionItem, DayEndItem, DayStartItem, ItemType

    svc = _svc()
    items = [
        DayStartItem(time="10:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="r", name="Ratusz w Poznaniu",
            description_short="", why_selected=["x"],
            start_time="15:14", end_time="15:44", duration_min=30,
            lat=52.4085, lng=16.9341, city="Poznań",
        ),
        DayEndItem(time="18:00"),
    ]
    ctx = {"requested_city": "Poznań", "day_end": "18:00"}
    out = svc._ensure_dinner_present(items, "18:00", ctx)
    types = [
        str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        for it in out
    ]
    assert "dinner_break" in types
    wro = svc._ensure_dinner_present(
        items, "18:00", {**ctx, "requested_city": "Wrocław"},
    )
    wro_types = [
        str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        for it in wro
    ]
    assert "dinner_break" not in wro_types


def test_pre_dinner_hole_pulls_kolacja_onto_last_stop():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, DinnerBreakItem, ItemType,
    )
    from app.domain.planner.time_utils import time_to_minutes

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="p", name="Pixel XL Poznań",
            description_short="", why_selected=["x"],
            start_time="15:18", end_time="16:18", duration_min=60,
            lat=52.4069, lng=16.9239, city="Poznań",
        ),
        DinnerBreakItem.model_construct(
            type=ItemType.DINNER_BREAK,
            start_time="18:30", end_time="19:30", duration_min=60,
            suggestions=[],
        ),
        DayEndItem(time="19:30"),
    ]
    ctx = {"requested_city": "Poznań", "day_end": "19:30"}
    out = svc._cover_remaining_pre_dinner_gap(items, ctx, day_num=2)
    dinner = next(
        it for it in out
        if str(getattr(getattr(it, "type", None), "value", "")) == "dinner_break"
    )
    st = time_to_minutes(dinner.start_time)
    assert 17 * 60 <= st <= 17 * 60 + 20
    wro = svc._cover_remaining_pre_dinner_gap(
        items, {**ctx, "requested_city": "Wrocław"}, day_num=2,
    )
    wro_d = next(
        it for it in wro
        if str(getattr(getattr(it, "type", None), "value", "")) == "dinner_break"
    )
    assert wro_d.start_time == "18:30"


def test_unvisited_museum_hop_is_dropped():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="r", name="Stary Rynek w Poznaniu",
            description_short="", why_selected=["x"],
            start_time="15:43", end_time="16:21", duration_min=38,
            lat=52.4085, lng=16.9341, city="Poznań",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="16:59", end_time="17:09",
            duration_min=10, from_location="Brama Poznania",
            to_location="Park Jana Pawła II", mode=TransitMode.CAR,
            distance_km=3.0,
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="17:09", end_time="17:27",
            duration_min=18, from_location="Muzeum Instrumentów Muzycznych",
            to_location="Brama Poznania", mode=TransitMode.WALK,
            distance_km=0.8, routing_source="return_to_car",
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="p", name="Park Jana Pawła II",
            description_short="", why_selected=["x"],
            start_time="17:27", end_time="17:57", duration_min=30,
            lat=52.3910, lng=16.9470, city="Poznań",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Poznań"}
    out = svc._scrub_remaining_unvisited_from(items, ctx, day_num=1)
    ghost = [
        it for it in out
        if "Instrument" in (getattr(it, "from_location", "") or "")
    ]
    assert ghost == []
