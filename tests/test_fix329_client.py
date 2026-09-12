"""FIX #329 — opening hours and a meal you can actually eat.

Client: "Kolejkowo jest zaplanowane przed otwarciem. Plan daje wizytę o 09:10
a otwarcie o 10:00", "D3 15 minut na kolację jest zdecydowanie za mało",
"D2 21 minut na kolację to za mało".
"""
from __future__ import annotations

import os

os.environ.setdefault("ORS_ENABLED", "false")

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    DayEndItem,
    DayStartItem,
    DinnerBreakItem,
    ItemType,
    LunchBreakItem,
    RestaurantSuggestion,
    TransitItem,
    TransitMode,
)
from app.infrastructure.repositories.poi_repository import POIRepository

_ALL_WEEK = {
    "mon": "10:00-19:00", "tue": "10:00-19:00", "wed": "10:00-19:00",
    "thu": "10:00-19:00", "fri": "10:00-19:00", "sat": "10:00-19:00",
    "sun": "10:00-19:00",
}


def _svc():
    return PlanService(POIRepository("data/zakopane.xlsx"))


def _poi(name, hours=None, pid="poi-1"):
    return {
        "id": pid,
        "name": name,
        "Name": name,
        "city": "Wrocław",
        "lat": 51.11,
        "lng": 17.03,
        "opening_hours": None,
        "opening_hours_seasonal": [{
            "date_from": "01-01", "date_to": "12-31", **(hours or _ALL_WEEK),
        }],
        "time_min": 60,
        "time_max": 120,
    }


def _attr(name, start, end, dur, pid="poi-1"):
    return AttractionItem.model_construct(
        type=ItemType.ATTRACTION,
        poi_id=pid,
        name=name,
        description_short="",
        start_time=start,
        end_time=end,
        duration_min=dur,
        lat=51.11,
        lng=17.03,
        address="Wrocław",
        city="Wrocław",
        cost_estimate=0,
    )


def _tr(frm, to, start, end, dur, km=1.0):
    return TransitItem.model_construct(
        type=ItemType.TRANSIT,
        from_location=frm,
        to_location=to,
        start_time=start,
        end_time=end,
        duration_min=dur,
        distance_km=km,
        mode=TransitMode.WALK,
        routing_source="estimated_walk",
    )


def _sug(name):
    return RestaurantSuggestion.model_construct(
        id=f"r-{name}", name=name, lat=51.11, lng=17.03, city="Wrocław",
        address="",
    )


def _ctx(**extra):
    base = {
        "requested_city": "Wrocław",
        "date": "2026-02-20",
        "day_start": "09:00",
        "day_end": "20:00",
    }
    base.update(extra)
    return base


def _find(items, type_value):
    for it in items:
        if getattr(getattr(it, "type", None), "value", None) == type_value:
            return it
    return None


def _span(it):
    from app.domain.planner.engine import time_to_minutes

    return time_to_minutes(it.end_time) - time_to_minutes(it.start_time)


# --- opening hours ---

def test_visit_before_opening_is_moved_to_the_opening_hour():
    svc = _svc()
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Kolejkowo Wrocław", "09:00", "09:10", 10),
        _attr("Kolejkowo Wrocław", "09:10", "10:40", 90),
        DayEndItem(time="10:40"),
    ]
    out = svc._respect_opening_hours(
        items, _ctx(poi_pool=[_poi("Kolejkowo Wrocław")]), day_num=1,
    )
    visit = _find(out, "attraction")
    assert visit is not None
    assert visit.start_time == "10:00"


def test_visit_inside_hours_is_left_alone():
    svc = _svc()
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Kolejkowo Wrocław", "09:50", "10:00", 10),
        _attr("Kolejkowo Wrocław", "10:00", "11:30", 90),
        DayEndItem(time="11:30"),
    ]
    out = svc._respect_opening_hours(
        items, _ctx(poi_pool=[_poi("Kolejkowo Wrocław")]), day_num=1,
    )
    visit = _find(out, "attraction")
    assert (visit.start_time, visit.end_time) == ("10:00", "11:30")


def test_visit_running_past_closing_is_trimmed():
    svc = _svc()
    items = [
        DayStartItem(type=ItemType.DAY_START, time="16:00"),
        _tr("Wrocław", "Kolejkowo Wrocław", "16:00", "16:10", 10),
        _attr("Kolejkowo Wrocław", "16:10", "19:00", 170),
        DayEndItem(time="19:00"),
    ]
    out = svc._respect_opening_hours(
        items, _ctx(poi_pool=[_poi("Kolejkowo Wrocław")]), day_num=1,
    )
    visit = _find(out, "attraction")
    # 19:00 close minus the engine's 15 min pre-closing margin.
    assert visit.end_time == "18:45"


def test_visit_on_a_closed_day_is_dropped():
    svc = _svc()
    closed_friday = dict(_ALL_WEEK, fri="closed")
    items = [
        DayStartItem(type=ItemType.DAY_START, time="10:00"),
        _tr("Wrocław", "Kolejkowo Wrocław", "10:00", "10:10", 10),
        _attr("Kolejkowo Wrocław", "10:10", "11:40", 90),
        DayEndItem(time="11:40"),
    ]
    out = svc._respect_opening_hours(
        items,
        _ctx(poi_pool=[_poi("Kolejkowo Wrocław", closed_friday)]),
        day_num=1,
    )
    assert _find(out, "attraction") is None


def test_poi_without_hours_data_is_untouched():
    svc = _svc()
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Rynek we Wrocławiu", "09:10", "10:00", 50, pid="poi-x"),
        DayEndItem(time="10:00"),
    ]
    out = svc._respect_opening_hours(
        items, _ctx(poi_pool=[_poi("Kolejkowo Wrocław")]), day_num=1,
    )
    visit = _find(out, "attraction")
    assert (visit.start_time, visit.end_time) == ("09:10", "10:00")


# --- meal minimum ---

def test_short_lunch_takes_minutes_from_the_previous_visit():
    svc = _svc()
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Muzeum Przyrodnicze we Wrocławiu", "11:00", "12:37", 97),
        _tr("Muzeum Przyrodnicze we Wrocławiu", "Olio", "12:37", "12:53", 16),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="12:53", end_time="13:28", duration_min=35,
            suggestions=[_sug("Olio")], label="Olio", location_context="",
        ),
        _tr("Olio", "Centrum Historii Zajezdnia", "13:28", "13:40", 12),
        _attr("Centrum Historii Zajezdnia", "13:40", "15:10", 90, pid="poi-2"),
        DayEndItem(time="15:10"),
    ]
    out = svc._enforce_meal_minimum(items, _ctx(), day_num=1)
    lunch = _find(out, "lunch_break")
    assert _span(lunch) >= 40
    after = _find(out[out.index(lunch) + 1:], "attraction")
    assert after.start_time == "13:40", "the next visit must not move"


def test_short_dinner_slides_the_evening_when_the_window_allows():
    svc = _svc()
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Rynek we Wrocławiu", "16:10", "17:25", 75),
        _tr("Rynek we Wrocławiu", "The Cork", "17:27", "17:40", 13),
        DinnerBreakItem.model_construct(
            type=ItemType.DINNER_BREAK,
            start_time="17:40", end_time="18:07", duration_min=27,
            suggestions=[_sug("The Cork")], label="The Cork",
        ),
        DayEndItem(time="18:07"),
    ]
    out = svc._enforce_meal_minimum(items, _ctx(), day_num=1)
    dinner = _find(out, "dinner_break")
    assert _span(dinner) >= 45
    from app.domain.planner.engine import time_to_minutes

    assert time_to_minutes(dinner.start_time) >= 17 * 60 + 30, (
        "dinner keeps its 17:30 floor"
    )


def test_meal_that_is_long_enough_is_not_touched():
    svc = _svc()
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="12:00", end_time="12:45", duration_min=45,
            suggestions=[_sug("Olio")], label="Olio", location_context="",
        ),
        DayEndItem(time="12:45"),
    ]
    out = svc._enforce_meal_minimum(items, _ctx(), day_num=1)
    lunch = _find(out, "lunch_break")
    assert (lunch.start_time, lunch.end_time) == ("12:00", "12:45")


def test_dinner_does_not_grow_past_the_asked_window():
    svc = _svc()
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Rynek we Wrocławiu", "17:00", "17:30", 30),
        _tr("Rynek we Wrocławiu", "The Cork", "17:30", "17:40", 10),
        DinnerBreakItem.model_construct(
            type=ItemType.DINNER_BREAK,
            start_time="17:40", end_time="17:55", duration_min=15,
            suggestions=[_sug("The Cork")], label="The Cork",
        ),
        DayEndItem(time="17:55"),
    ]
    out = svc._enforce_meal_minimum(items, _ctx(day_end="18:00"), day_num=1)
    dinner = _find(out, "dinner_break")
    from app.domain.planner.engine import time_to_minutes

    assert time_to_minutes(dinner.end_time) <= 18 * 60
