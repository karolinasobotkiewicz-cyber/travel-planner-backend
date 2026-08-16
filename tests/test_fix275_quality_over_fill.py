"""FIX #275 — quality over filling the daily window."""
from __future__ import annotations

from app.application.services.plan_service import (
    PlanService,
    _generate_day_title,
    _quality_first_trip,
    _strip_trailing_free_time,
    _timeline_content_end_minutes,
    _trim_midday_free_time_blocks,
)
from app.domain.models.plan import (
    AttractionItem,
    DinnerBreakItem,
    FreeTimeItem,
    ItemType,
    LunchBreakItem,
)


def _attr(name: str, start: str, end: str, dur: int) -> AttractionItem:
    return AttractionItem.model_construct(
        type=ItemType.ATTRACTION,
        poi_id=f"id-{name}",
        name=name,
        description_short="",
        start_time=start,
        end_time=end,
        duration_min=dur,
        lat=51.1,
        lng=17.0,
        address="",
        cost_estimate=0,
    )


def _ft(start: str, end: str, dur: int) -> FreeTimeItem:
    return FreeTimeItem(
        type=ItemType.FREE_TIME,
        start_time=start,
        end_time=end,
        duration_min=dur,
        label="Czas wolny",
        suggestions=[],
    )


def test_fix275_quality_first_is_long_trip_only():
    assert _quality_first_trip({"num_days": 7})
    assert _quality_first_trip({"num_days": 5})
    assert not _quality_first_trip({"num_days": 3})
    assert not _quality_first_trip({})


def test_fix275_no_dinner_when_content_ends_afternoon():
    svc = PlanService.__new__(PlanService)
    items = [
        _attr("Rynek", "09:00", "11:00", 120),
        LunchBreakItem(
            type=ItemType.LUNCH_BREAK,
            start_time="12:00",
            end_time="12:40",
            duration_min=40,
            suggestions=[],
        ),
        _attr("Hala Stulecia", "13:00", "15:30", 150),
        _ft("15:30", "19:00", 210),
    ]
    out = svc._guarantee_dinner_before_day_end(
        items, {"day_end": "19:00", "num_days": 7}, day_num=6,
    )
    assert not any(
        getattr(it, "type", None) == ItemType.DINNER_BREAK
        or str(getattr(getattr(it, "type", None), "value", "")).lower()
        == "dinner_break"
        for it in out
    )


def test_fix275_dinner_still_on_short_trip():
    svc = PlanService.__new__(PlanService)
    items = [
        _attr("Rynek", "09:00", "11:00", 120),
        LunchBreakItem(
            type=ItemType.LUNCH_BREAK,
            start_time="12:00",
            end_time="12:40",
            duration_min=40,
            suggestions=[],
        ),
        _attr("Hala Stulecia", "13:00", "15:30", 150),
        _ft("15:30", "19:00", 210),
    ]
    out = svc._guarantee_dinner_before_day_end(
        items, {"day_end": "19:00", "num_days": 3}, day_num=2,
    )
    assert any(
        str(getattr(getattr(it, "type", None), "value", it.type)).lower()
        == "dinner_break"
        for it in out
    )


def test_fix275_dinner_when_evening_content_on_long_trip():
    svc = PlanService.__new__(PlanService)
    items = [
        _attr("Rynek", "10:00", "12:00", 120),
        LunchBreakItem(
            type=ItemType.LUNCH_BREAK,
            start_time="12:30",
            end_time="13:10",
            duration_min=40,
            suggestions=[],
        ),
        _attr("Neon Side", "17:20", "18:20", 60),
    ]
    out = svc._guarantee_dinner_before_day_end(
        items, {"day_end": "20:00", "num_days": 7}, day_num=2,
    )
    assert any(
        str(getattr(getattr(it, "type", None), "value", it.type)).lower()
        == "dinner_break"
        for it in out
    )


def test_fix275_midday_holes_still_trimmed_tail_kept():
    items = [
        _attr("A", "09:00", "11:00", 120),
        _ft("11:00", "12:20", 80),
        _attr("B", "12:20", "14:00", 100),
        _ft("14:00", "19:00", 300),
    ]
    out = _trim_midday_free_time_blocks(items, max_min=25)
    mids = [
        it for it in out
        if getattr(it, "type", None) == ItemType.FREE_TIME
        and it.start_time == "11:00"
    ]
    tails = [
        it for it in out
        if getattr(it, "type", None) == ItemType.FREE_TIME
        and it.start_time == "14:00"
    ]
    assert mids and int(mids[0].duration_min) <= 25
    assert tails and int(tails[0].duration_min) >= 180


def test_fix275_old_trailing_strip_still_drops_urban_tail():
    items = [
        _attr("A", "09:00", "16:00", 420),
        _ft("16:00", "19:00", 180),
    ]
    out = _strip_trailing_free_time(items, max_min=12)
    assert not any(getattr(it, "type", None) == ItemType.FREE_TIME for it in out)


def test_fix275_content_end_ignores_free_time():
    items = [
        _attr("A", "09:00", "11:00", 120),
        _ft("11:00", "19:00", 480),
    ]
    assert _timeline_content_end_minutes(items) == 11 * 60


def test_fix275_light_day_title():
    items = [
        _attr("Rynek we Wrocławiu", "09:00", "11:00", 120),
        _attr("Most Tumski", "11:30", "12:00", 30),
        _ft("12:00", "16:00", 240),
    ]
    title = _generate_day_title(items, 7)
    assert "luźniejszy" in title.lower() or "luzniejszy" in title.lower()


def test_fix275_hygiene_keeps_afternoon_on_long_trip():
    svc = PlanService.__new__(PlanService)
    items = [
        _attr("Rynek", "09:00", "11:00", 120),
        _attr("Hala", "12:00", "14:00", 120),
        _ft("14:00", "19:00", 300),
    ]
    out = svc._apply_free_time_final_hygiene(
        items, {"num_days": 7, "requested_city": "Wrocław"},
    )
    ft = [it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME]
    assert ft
    assert sum(int(it.duration_min or 0) for it in ft) >= 90
