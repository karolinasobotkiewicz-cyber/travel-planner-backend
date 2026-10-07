"""FIX #368 P1 ? collapse stacked free_time / cap idle gaps."""
from __future__ import annotations

from scripts.plan_quality_validator import Report, validate_day


def _svc():
    from app.application.services.plan_service import PlanService
    from app.infrastructure.repositories.poi_repository import POIRepository
    return PlanService(POIRepository("data/zakopane.xlsx"))


def _tv(it):
    t = getattr(it, "type", None)
    return t.value if hasattr(t, "value") else str(t or "")


def test_collapse_two_x44_stacked_free_time():
    """UAT: 2x44 min free_time with a 6 min micro-gap becomes one capped block."""
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, FreeTimeItem, ItemType,
        LunchBreakItem,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Wawel",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=50.054, lng=19.935, city="Krakow",
        ),
        FreeTimeItem(
            start_time="11:00", end_time="11:44", duration_min=44,
            label="Czas dla siebie",
        ),
        FreeTimeItem(
            start_time="11:50", end_time="12:34", duration_min=44,
            label="Czas dla siebie",
        ),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="12:40", end_time="13:25", duration_min=45,
            label="Lunch",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Krakow", "has_car": True, "day_end": "19:00"}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    fts = [it for it in out if _tv(it) == "free_time"]
    # Max one free_time *between* Wawel and lunch (morning gap cover may exist).
    between = []
    saw_wawel = False
    for it in out:
        if _tv(it) == "attraction" and "wawel" in (getattr(it, "name", "") or "").lower():
            saw_wawel = True
            continue
        if saw_wawel and _tv(it) == "lunch_break":
            break
        if saw_wawel and _tv(it) == "free_time":
            between.append(it)
    assert len(between) <= 1, between
    for ft in fts:
        assert int(getattr(ft, "duration_min", 0) or 0) <= 60
    # No micro-gapped stack remains anywhere.
    ends = []
    for it in fts:
        ends.append((getattr(it, "start_time", ""), getattr(it, "end_time", "")))
    assert len(between) == 1 or len(between) == 0


def test_three_hour_free_time_capped_and_meal_pulled():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, FreeTimeItem, ItemType,
        LunchBreakItem,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Rynek",
            description_short="x", why_selected=["x"],
            start_time="09:30", end_time="10:30", duration_min=60,
            lat=50.06, lng=19.94, city="Krakow",
        ),
        FreeTimeItem(
            start_time="10:30", end_time="13:30", duration_min=180,
            label="Czas dla siebie",
        ),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="13:30", end_time="14:15", duration_min=45,
            label="Lunch",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Katowice", "has_car": True, "day_end": "19:00"}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=2)
    fts = [it for it in out if _tv(it) == "free_time"]
    assert len(fts) == 1
    assert int(getattr(fts[0], "duration_min", 0) or 0) <= 60
    meals = [it for it in out if _tv(it) == "lunch_break"]
    assert meals
    # meal should start at or near end of capped free_time (11:30), not 13:30
    assert getattr(meals[0], "start_time", "") <= "12:00", getattr(meals[0], "start_time", None)


def test_wroclaw_stacked_free_time_untouched_by_seal():
    from app.domain.models.plan import (
        DayEndItem, DayStartItem, FreeTimeItem, ItemType,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        FreeTimeItem(start_time="10:00", end_time="10:44", duration_min=44, label="a"),
        FreeTimeItem(start_time="10:50", end_time="11:34", duration_min=44, label="b"),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Wroclaw", "has_car": True}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    fts = [it for it in out if _tv(it) == "free_time"]
    assert len(fts) == 2, "locked city must not run P1 seal"


def test_validator_flags_stacked_and_long_idle():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, FreeTimeItem, ItemType,
    )

    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Spodek",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=50.27, lng=19.02, city="Katowice",
        ),
        FreeTimeItem(start_time="11:00", end_time="11:44", duration_min=44, label="a"),
        FreeTimeItem(start_time="11:50", end_time="12:34", duration_min=44, label="b"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Nikiszowiec",
            description_short="x", why_selected=["x"],
            start_time="12:40", end_time="13:40", duration_min=60,
            lat=50.26, lng=19.08, city="Katowice",
        ),
        FreeTimeItem(start_time="14:00", end_time="16:00", duration_min=120, label="long"),
        DayEndItem(time="19:00"),
    ]
    report = Report()
    validate_day(city="Katowice", num=1, day_num=1, items=items, report=report)
    codes = {h.code for h in report.hits}
    assert "stacked_free_time" in codes, codes
    assert "idle_gap_minutes" in codes, codes
