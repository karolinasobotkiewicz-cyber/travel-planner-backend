"""FIX #321 — Neon after dusk; city min-close 16:30–17:30, no FT pad.

Does not call generate_plan.
"""
from __future__ import annotations

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    DayEndItem,
    DayStartItem,
    FreeTimeItem,
    ItemType,
)
from app.domain.planner.time_utils import time_to_minutes


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


def _ft(start, end, dur, label="Czas dla siebie"):
    return FreeTimeItem.model_construct(
        type=ItemType.FREE_TIME,
        start_time=start,
        end_time=end,
        duration_min=dur,
        label=label,
        suggestions=[],
    )


def _ctx(**extra):
    base = {
        "requested_city": "Wrocław",
        "has_car": True,
        "day_start": "09:00",
        "day_end": "19:00",
    }
    base.update(extra)
    return base


def test_neon_at_1600_shifts_to_1800():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Hydropolis", "10:00", "12:00", 120, lat=51.104, lng=17.056),
        _attr("Neon Side", "15:58", "16:43", 45, lat=51.109, lng=17.033),
        DayEndItem(time="16:43"),
    ]
    out = _svc()._enforce_neon_after_dark(items, _ctx(day_end="19:00"), day_num=2)
    neon = next(
        it for it in out
        if "neon" in (getattr(it, "name", "") or "").lower()
    )
    assert neon.start_time >= "17:30"
    assert neon.start_time == "18:00"


def test_neon_dropped_when_window_too_early():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Hydropolis", "10:00", "12:00", 120, lat=51.104, lng=17.056),
        _attr("Neon Side", "15:58", "16:43", 45, lat=51.109, lng=17.033),
        DayEndItem(time="17:00"),
    ]
    out = _svc()._enforce_neon_after_dark(items, _ctx(day_end="17:00"), day_num=2)
    names = " ".join(
        (getattr(it, "name", "") or "").lower()
        for it in out if getattr(it, "type", None) == ItemType.ATTRACTION
    )
    assert "neon" not in names


def test_city_day_ending_1413_gets_afternoon_stop():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Hydropolis", "10:00", "12:00", 120, lat=51.104, lng=17.056),
        _attr("Most Tumski", "12:30", "14:13", 103, lat=51.114, lng=17.047),
        DayEndItem(time="14:13"),
    ]
    pool = [{
        "id": "p-rynek",
        "name": "Rynek we Wrocławiu",
        "lat": 51.1099,
        "lng": 17.0325,
        "city": "Wrocław",
        "tags": ["attraction", "must_see"],
        "duration_min": 45,
        "time_min": 40,
        "time_max": 60,
    }]
    out = _svc()._close_city_day_toward_evening(
        items, pool, _ctx(day_end="18:00"), {"preferences": []}, day_num=3,
    )
    last = _svc()._timeline_last_real_end(out)
    assert last is not None
    assert last >= 15 * 60, "window 18:00 must not die at 14:13"
    assert last <= 18 * 60
    tail = [
        it for it in out
        if it.type == ItemType.FREE_TIME
        and time_to_minutes(it.start_time) >= last - 2
    ]
    assert not tail, "must not pad leftover FT to day_end"


def test_window_2000_does_not_pad_ft_to_2000():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Hydropolis", "10:00", "12:00", 120, lat=51.104, lng=17.056),
        _attr("Most Tumski", "12:30", "14:14", 104, lat=51.114, lng=17.047),
        _ft("14:14", "20:00", 346),
        DayEndItem(time="20:00"),
    ]
    pool = [{
        "id": "p-rynek",
        "name": "Rynek we Wrocławiu",
        "lat": 51.1099,
        "lng": 17.0325,
        "city": "Wrocław",
        "tags": ["attraction"],
        "duration_min": 45,
        "time_min": 40,
        "time_max": 60,
    }]
    out = _svc()._close_city_day_toward_evening(
        items, pool, _ctx(day_end="20:00"), {"preferences": []}, day_num=4,
    )
    last = _svc()._timeline_last_real_end(out)
    assert last is not None
    assert last >= 15 * 60
    assert last <= 18 * 60 + 15
    fts = [it for it in out if it.type == ItemType.FREE_TIME]
    assert all(int(it.duration_min) < 180 for it in fts)
