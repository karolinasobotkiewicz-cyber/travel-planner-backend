"""FIX #332 - a window to 18:00 does not close at noon.

Client leftovers after #331: J4 D4 ends 11:57, J8 D6 is five 45-min
free_time blocks (still 221 min of nothing), J2 D3 has 101 min between
Hydropolis and Wyspa Slodowa.
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
    FreeTimeItem,
    ItemType,
    LunchBreakItem,
    RestaurantSuggestion,
    TransitItem,
    TransitMode,
)
from app.domain.validators.client_invariants import audit_day
from app.infrastructure.repositories.poi_repository import POIRepository

WENA = (50.9329, 17.2924)
RYNEK = (51.1100, 17.0313)
HYDRO = (51.1035, 17.0572)


def _svc():
    return PlanService(POIRepository("data/zakopane.xlsx"))


def _attr(name, start, end, pt, pid="poi-1"):
    return AttractionItem.model_construct(
        type=ItemType.ATTRACTION,
        poi_id=pid,
        name=name,
        description_short="",
        start_time=start,
        end_time=end,
        duration_min=None,
        lat=pt[0],
        lng=pt[1],
    )


def _ft(start, end, label="Czas dla siebie"):
    return FreeTimeItem.model_construct(
        type=ItemType.FREE_TIME,
        start_time=start,
        end_time=end,
        duration_min=None,
        label=label,
        suggestions=[],
    )


def _codes(items, **ctx):
    base = {
        "city": "Wroclaw",
        "requested_city": "Wroclaw",
        "day_end": "18:00",
    }
    base.update(ctx)
    return {d.code for d in audit_day(items, day=1, context=base)}


def test_auditor_merges_adjacent_free_time_into_one_hole():
    """Five 45-min blocks after Wena is still 221 min of nothing."""
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Muzeum Motoryzacji Wena", "11:02", "12:32", WENA),
        _ft("13:32", "14:17"),
        _ft("14:17", "15:02"),
        _ft("15:02", "15:47"),
        _ft("15:47", "16:32"),
        _ft("16:32", "17:13"),
        DayEndItem(time="17:13"),
    ]
    got = [d for d in audit_day(items, day=6, context={"day_end": "20:00"})]
    assert any(d.code == "long_free_time" and d.meta["minutes"] >= 200 for d in got)


def test_auditor_flags_a_day_that_ends_before_15():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:30"),
        _attr("Bastion Sakwowy", "11:27", "11:57", RYNEK),
        DayEndItem(time="11:57"),
    ]
    assert "short_day" in _codes(items, day_end="18:00")


def test_empty_satellite_afternoon_is_cut_so_the_guest_goes_home():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="12:52",
        end_time="13:32",
        duration_min=40,
        suggestions=[
            RestaurantSuggestion.model_construct(
                id="r-1", name="INCANTO Restauracja",
                lat=50.94, lng=17.29, city="Olawa", address="",
            ),
        ],
        label="INCANTO Restauracja",
    )
    dinner = DinnerBreakItem.model_construct(
        type=ItemType.DINNER_BREAK,
        start_time="17:30",
        end_time="18:30",
        duration_min=60,
        suggestions=[],
        label="Przystanek ze smakiem",
    )
    items = [
        _attr("Muzeum Motoryzacji Wena", "11:02", "12:32", WENA),
        lunch,
        _ft("13:32", "17:13"),
        dinner,
        DayEndItem(time="18:30"),
    ]
    out = _svc()._send_home_before_empty_satellite_afternoon(
        items, {"requested_city": "Wroclaw"}, day_num=6,
    )
    assert not any(
        getattr(x.type, "value", x.type) == "free_time" for x in out
    )
    assert not any(
        getattr(x.type, "value", x.type) == "dinner_break" for x in out
    )


def test_short_day_gets_an_afternoon_stop_from_the_pool():
    pool = [{
        "id": "poi-2",
        "name": "Wyspa Slodowa",
        "lat": 51.1160,
        "lng": 17.0380,
        "time_min": 45,
        "time_max": 75,
        "opening_hours_seasonal": [{
            "date_from": "01-01", "date_to": "12-31",
            "mon": "09:00-20:00", "tue": "09:00-20:00",
            "wed": "09:00-20:00", "thu": "09:00-20:00",
            "fri": "09:00-20:00", "sat": "09:00-20:00",
            "sun": "09:00-20:00",
        }],
    }]
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:30"),
        _attr("Bastion Sakwowy", "11:27", "11:57", RYNEK),
        DayEndItem(time="11:57"),
    ]
    out = _svc()._extend_short_day(
        items,
        {
            "day_end": "18:00",
            "date": "2026-02-23",
            "requested_city": "Wroclaw",
            "has_car": True,
            "poi_pool": pool,
        },
        day_num=4,
    )
    names = [
        getattr(x, "name", "") for x in out
        if getattr(x.type, "value", x.type) == "attraction"
    ]
    assert "Wyspa Slodowa" in names
    ends = [
        getattr(x, "end_time", "") for x in out
        if getattr(x.type, "value", x.type) == "attraction"
    ]
    assert max(ends) > "11:57"
