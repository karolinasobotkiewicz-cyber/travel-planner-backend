"""FIX #342 — client mail: early lunch, satellite restaurant after return,
fake hub hop, empty satellite day.
"""
from __future__ import annotations

import os

os.environ.setdefault("ORS_ENABLED", "false")

from app.application.services.plan_service import (
    PlanService,
    _capped_named_hop_minutes,
)
from app.domain.models.plan import (
    AttractionItem,
    DayEndItem,
    DayStartItem,
    FreeTimeItem,
    ItemType,
    LunchBreakItem,
    RestaurantSuggestion,
    TransitItem,
    TransitMode,
)
from app.domain.planner.engine import time_to_minutes
from app.infrastructure.repositories.poi_repository import POIRepository

WENA = (50.9329, 17.2924)
RYNEK = (51.1106992, 17.0323662)
ZABK = (50.589, 16.812)


def _svc():
    return PlanService(POIRepository("data/zakopane.xlsx"))


def _attr(name, start, end, pt=RYNEK, dur=60):
    return AttractionItem.model_construct(
        type=ItemType.ATTRACTION,
        poi_id=f"poi-{name}",
        name=name,
        description_short="Opis",
        why_selected=["bo warto"],
        start_time=start,
        end_time=end,
        duration_min=dur,
        lat=pt[0],
        lng=pt[1],
    )


def _tr(frm, to, start, end, km=1.0, dur=15):
    return TransitItem.model_construct(
        type=ItemType.TRANSIT,
        from_location=frm,
        to_location=to,
        start_time=start,
        end_time=end,
        duration_min=dur,
        distance_km=km,
        mode=TransitMode.CAR,
        routing_source="estimated_road",
    )


def test_lunch_before_noon_is_pushed_to_12():
    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        _attr("CityPaintball", "10:00", "11:00", dur=60),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="11:00",
            end_time="11:45",
            duration_min=45,
            label="Lunch",
            suggestions=[],
        ),
        DayEndItem(time="20:00"),
    ]
    out = svc._push_lunch_not_before_noon(items, day_num=2)
    lunches = [it for it in out if getattr(getattr(it, "type", None), "value", None) == "lunch_break" or str(getattr(it, "type", "")) == "lunch_break"]
    assert lunches, out
    assert lunches[0].start_time == "12:00"


def test_eat_free_time_does_not_pull_lunch_before_noon():
    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        _attr("Bastion Sakwowy", "10:19", "10:40", dur=21),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME,
            start_time="10:40",
            end_time="11:33",
            duration_min=53,
        ),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="12:00",
            end_time="12:45",
            duration_min=45,
            label="VaffaNapoli",
            suggestions=[],
        ),
        DayEndItem(time="18:00"),
    ]
    out = svc._eat_long_free_time_before_attraction(
        items, day_num=4, min_ft=40, keep=10, pull_lunch=True,
    )
    lunches = [
        it for it in out
        if str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "lunch_break"
    ]
    assert lunches
    assert time_to_minutes(lunches[0].start_time) >= 12 * 60


def test_satellite_lunch_after_hub_return_is_dropped():
    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        _attr("Rynek w Ząbkowicach Śląskich", "10:00", "11:00", pt=ZABK),
        _attr("Zamek w Ząbkowicach", "11:15", "12:30", pt=ZABK),
        _tr("Zamek w Ząbkowicach", "Wrocław centrum", "12:30", "13:40", km=60, dur=70),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="14:05",
            end_time="14:45",
            duration_min=40,
            label="Mała Grecja",
            suggestions=[RestaurantSuggestion.model_construct(
                id="r-grecja", name="Mała Grecja", lat=ZABK[0], lng=ZABK[1],
                city="Ząbkowice Śląskie", address="Rynek",
            )],
        ),
        DayEndItem(time="20:00"),
    ]
    out = svc._strip_satellite_meals_on_city_days(items, day_num=5)
    meals = [
        it for it in out
        if str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "lunch_break"
    ]
    assert meals == [], [getattr(m, "label", None) for m in meals]


def test_arrival_leg_after_return_starts_from_the_hub():
    svc = _svc()
    ordered = [
        _attr("Rynek w Oławie", "13:14", "14:14", pt=WENA),
        _tr("Rynek w Oławie", "Wrocław centrum", "14:14", "14:59", km=25.7, dur=45),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME,
            start_time="14:59",
            end_time="18:00",
            duration_min=181,
        ),
    ]
    poi = {"name": "Muzeum Narodowe we Wrocławiu", "lat": RYNEK[0], "lng": RYNEK[1]}
    leg, hop = svc._hole_arrival_leg(
        ordered, 2, poi, 14 * 60 + 59,
        {"requested_city": "Wrocław", "has_car": True},
    )
    assert leg is not None
    assert "wrocław" in (leg.from_location or "").lower() or "centrum" in (
        leg.from_location or ""
    ).lower()
    assert float(leg.distance_km or 0) < 8.0, leg.distance_km
    assert hop < 30, hop


def test_thin_daytrip_does_not_empty_the_day():
    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        _tr("Wrocław", "Rynek w Ząbkowicach Śląskich", "09:00", "10:10", km=62, dur=70),
        _attr("Rynek w Ząbkowicach Śląskich", "10:10", "11:00", pt=ZABK, dur=50),
        DayEndItem(time="20:00"),
    ]
    ctx = {
        "requested_city": "Wrocław",
        "blocked_satellite_kinds": {"zabkowice"},
        "poi_pool": [],
    }
    out = svc._complete_thin_daytrip(items, [], ctx, {}, day_num=5)
    names = [
        getattr(it, "name", "") for it in out
        if str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "attraction"
    ]
    assert names, "day must keep the Ząbkowice stop rather than go blank"


def test_named_olawa_hop_is_neither_sprint_nor_crawl():
    assert _capped_named_hop_minutes(
        "Most Grunwaldzki", "Muzeum Motoryzacji Wena", 33.7, 72,
    ) == 45
    assert _capped_named_hop_minutes(
        "Wrocław", "Rynek w Oławie", 26.0, 8,
    ) == 30


def test_heal_adds_return_after_afternoon_olawa():
    svc = _svc()
    items = [
        DayStartItem(time="09:30"),
        _attr("Most Grunwaldzki", "13:36", "13:56", dur=20),
        _tr(
            "Most Grunwaldzki", "Muzeum Motoryzacji Wena",
            "13:56", "15:08", km=33.7, dur=72,
        ),
        _attr("Muzeum Motoryzacji Wena", "15:08", "15:38", pt=WENA, dur=30),
        _attr(
            "Rynek w Oławie", "15:48", "16:48",
            pt=(50.9429, 17.2956), dur=60,
        ),
        DayEndItem(time="18:00"),
    ]
    ctx = {
        "requested_city": "Wrocław",
        "day_end": "18:00",
        "has_car": True,
        "poi_pool": [],
    }
    out = svc._heal_client_day_shape(items, ctx, day_num=4)
    returns = [
        it for it in out
        if str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "transit"
        and "wrocław" in (getattr(it, "to_location", "") or "").lower()
        and float(getattr(it, "distance_km", 0) or 0) >= 15
    ]
    assert returns, [
        (getattr(it, "from_location", None), getattr(it, "to_location", None),
         getattr(it, "duration_min", None), getattr(it, "distance_km", None))
        for it in out
        if str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "transit"
    ]
    assert 30 <= int(returns[-1].duration_min or 0) <= 45
