"""FIX #368 P3 ? opening hours, season, min visit, day_end."""
from __future__ import annotations

from datetime import date

from scripts.plan_quality_validator import Report, validate_day


def _svc():
    from app.application.services.plan_service import PlanService
    from app.infrastructure.repositories.poi_repository import POIRepository
    return PlanService(POIRepository("data/zakopane.xlsx"))


def _tv(it):
    t = getattr(it, "type", None)
    return t.value if hasattr(t, "value") else str(t or "")


def test_mocak_after_closing_dropped_or_rescheduled():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="m", name="Muzeum Sztuki Wspolczesnej MOCAK",
            description_short="x", why_selected=["x"],
            start_time="18:30", end_time="19:30", duration_min=60,
            lat=50.047, lng=19.961, city="Krakow",
        ),
        DayEndItem(time="20:00"),
    ]
    # Tuesday 2026-03-10 ? MOCAK open 11-19
    ctx = {
        "requested_city": "Krakow", "has_car": True, "day_end": "20:00",
        "date": date(2026, 3, 10),
    }
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    mocaks = [
        it for it in out
        if _tv(it) == "attraction" and "mocak" in (getattr(it, "name", "") or "").lower()
    ]
    # Either dropped or fully inside open window (close margin 18:45)
    for it in mocaks:
        en = getattr(it, "end_time", "")
        assert en <= "18:45", en


def test_galicja_after_1800_dropped_or_fit():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="g",
            name="Muzeum Historii Zydow Galicji",
            description_short="x", why_selected=["x"],
            start_time="17:30", end_time="18:30", duration_min=60,
            lat=50.051, lng=19.945, city="Krakow",
        ),
        DayEndItem(time="20:00"),
    ]
    ctx = {
        "requested_city": "Krakow", "has_car": True, "day_end": "20:00",
        "date": date(2026, 4, 15),
    }
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    gals = [
        it for it in out
        if _tv(it) == "attraction" and "galicj" in (getattr(it, "name", "") or "").lower()
    ]
    for it in gals:
        assert getattr(it, "end_time", "") <= "17:45"


def test_wieza_ratuszowa_before_season_dropped():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="w", name="Wieza Ratuszowa",
            description_short="x", why_selected=["x"],
            start_time="12:00", end_time="12:40", duration_min=40,
            lat=50.061, lng=19.937, city="Krakow",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {
        "requested_city": "Krakow", "has_car": True, "day_end": "19:00",
        "date": date(2026, 3, 1),  # before 2026-03-08
    }
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    names = [getattr(it, "name", "") or "" for it in out if _tv(it) == "attraction"]
    assert not any("ratuszowa" in n.lower() for n in names), names


def test_day_end_before_visit_end_clipped_or_dropped():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Sukiennice",
            description_short="x", why_selected=["x"],
            start_time="18:30", end_time="19:30", duration_min=60,
            lat=50.0617, lng=19.9373, city="Krakow",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {
        "requested_city": "Krakow", "has_car": True, "day_end": "19:00",
        "date": date(2026, 5, 1),
    }
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    for it in out:
        if _tv(it) != "attraction":
            continue
        assert getattr(it, "end_time", "00:00") <= "19:00"


def test_mocak_five_minute_paid_visit_dropped_or_extended():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="m", name="MOCAK",
            description_short="x", why_selected=["x"],
            start_time="14:00", end_time="14:05", duration_min=5,
            lat=50.047, lng=19.961, city="Krakow",
        ),
        DayEndItem(time="20:00"),
    ]
    ctx = {
        "requested_city": "Krakow", "has_car": True, "day_end": "20:00",
        "date": date(2026, 3, 10),
    }
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    mocaks = [
        it for it in out
        if _tv(it) == "attraction" and "mocak" in (getattr(it, "name", "") or "").lower()
    ]
    for it in mocaks:
        assert int(getattr(it, "duration_min", 0) or 0) >= 60


def test_wroclaw_hours_seal_untouched():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="m", name="MOCAK",
            description_short="x", why_selected=["x"],
            start_time="18:30", end_time="19:30", duration_min=60,
            lat=51.1, lng=17.0, city="Wroclaw",
        ),
        DayEndItem(time="20:00"),
    ]
    ctx = {
        "requested_city": "Wroclaw", "has_car": True, "day_end": "20:00",
        "date": date(2026, 3, 10),
    }
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    mocaks = [it for it in out if _tv(it) == "attraction"]
    assert len(mocaks) == 1
    assert getattr(mocaks[0], "end_time", None) == "19:30"


def test_validator_flags_hours_season_min_day_end():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType,
    )

    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="m", name="MOCAK",
            description_short="x", why_selected=["x"],
            start_time="18:50", end_time="19:20", duration_min=30,
            lat=50.047, lng=19.961, city="Krakow",
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="w", name="Wieza Ratuszowa",
            description_short="x", why_selected=["x"],
            start_time="12:00", end_time="12:40", duration_min=40,
            lat=50.061, lng=19.937, city="Krakow",
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="s", name="Sukiennice",
            description_short="x", why_selected=["x"],
            start_time="18:40", end_time="19:20", duration_min=40,
            lat=50.0617, lng=19.9373, city="Krakow",
        ),
        DayEndItem(time="19:00"),
    ]
    report = Report()
    validate_day(
        city="Krakow", num=1, day_num=1, items=items, report=report,
        trip_date=date(2026, 3, 1),
    )
    codes = {h.code for h in report.hits}
    assert "outside_opening_hours" in codes or "min_visit_duration" in codes, codes
    assert "before_season" in codes, codes
    assert "day_end_before_visit_end" in codes, codes
