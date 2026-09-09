"""FIX #319 — satellite cluster-or-drop, return hop, meal travels with the body.

Does not call generate_plan.
"""
from __future__ import annotations

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    DayEndItem,
    DayStartItem,
    ItemType,
    LunchBreakItem,
    RestaurantSuggestion,
    TransitItem,
    TransitMode,
)


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur=60, *, lat=51.11, lng=17.03):
    return AttractionItem.model_construct(
        type=ItemType.ATTRACTION,
        poi_id=f"id-{name}",
        name=name,
        description_short="",
        start_time=start,
        end_time=end,
        duration_min=dur,
        lat=lat,
        lng=lng,
        address="Wrocław",
        city="Wrocław",
        cost_estimate=0,
    )


def _tr(frm, to, start, end, *, km=1.0, dur=10,
        mode=TransitMode.CAR, src="estimated_road"):
    return TransitItem.model_construct(
        type=ItemType.TRANSIT,
        from_location=frm,
        to_location=to,
        start_time=start,
        end_time=end,
        duration_min=dur,
        distance_km=km,
        mode=mode,
        routing_source=src,
    )


def _ctx(**extra):
    base = {
        "requested_city": "Wrocław",
        "has_car": True,
        "day_start": "09:00",
        "day_end": "20:00",
        "num_days": 7,
    }
    base.update(extra)
    return base


def _names(items):
    return [
        (getattr(it, "name", "") or "")
        for it in items
        if getattr(it, "type", None) == ItemType.ATTRACTION
    ]


def test_lonely_dolina_65km_drive_is_dropped():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Dolina Tatarska", "09:00", "10:00", km=64.6, dur=60),
        _attr("Dolina Tatarska", "10:00", "10:50", 50,
              lat=50.725, lng=16.852),
        DayEndItem(time="10:50"),
    ]
    out = _svc()._complete_thin_daytrip(
        items, [], _ctx(), {}, day_num=6,
    )
    blob = " ".join(_names(out)).lower()
    assert "dolina tatarska" not in blob
    assert "tatarsk" not in blob


def test_zabkowice_cluster_keeps_castle_and_gets_return_hop():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Zamek w Ząbkowicach Śląskich", "09:00", "10:10",
            km=62.0, dur=70),
        _attr("Zamek w Ząbkowicach Śląskich", "10:10", "12:00", 110,
              lat=50.589, lng=16.810),
        _attr("Laboratorium Frankensteina", "12:15", "13:15", 60,
              lat=50.591, lng=16.812),
        DayEndItem(time="14:37"),
    ]
    out = _svc()._complete_thin_daytrip(
        items, [], _ctx(), {}, day_num=3,
    )
    names = " ".join(_names(out)).lower()
    assert "ząbkow" in names or "zabkow" in names
    assert "frankenstein" in names
    returns = [
        it for it in out
        if getattr(it, "type", None) == ItemType.TRANSIT
        and "wrocław" in (getattr(it, "to_location", "") or "").lower()
        and "ząbkow" not in (getattr(it, "to_location", "") or "").lower()
    ]
    assert returns, "Ząbkowice day must drive back to Wrocław"


def test_ida_location_context_cleared_on_satellite_lunch():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Dolina Tatarska", "10:00", "10:50", 50,
              lat=50.725, lng=16.852),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="12:00", end_time="13:00", duration_min=60,
            suggestions=[RestaurantSuggestion.model_construct(
                id="ida", name="IDA kuchnia i wino",
                lat=51.11, lng=17.03, city="Wrocław", address="",
            )],
            label="IDA kuchnia i wino",
            location_context="IDA kuchnia i wino",
        ),
        DayEndItem(time="13:00"),
    ]
    out = _svc()._strip_far_meal_only_hops(items, day_num=6)
    meal = next(
        it for it in out if getattr(it, "type", None) == ItemType.LUNCH_BREAK
    )
    assert not (meal.suggestions or [])
    assert "ida" not in (meal.location_context or "").lower()
    assert "ida" not in (meal.label or "").lower()
