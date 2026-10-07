"""FIX #368 P5 ? profile bans, dedupe, cost_estimate, transit-without-visit."""
from __future__ import annotations

from scripts.plan_quality_validator import Report, validate_day, validate_plan


def _svc():
    from app.application.services.plan_service import PlanService
    from app.infrastructure.repositories.poi_repository import POIRepository
    return PlanService(POIRepository("data/zakopane.xlsx"))


def _tv(it):
    t = getattr(it, "type", None)
    return t.value if hasattr(t, "value") else str(t or "")


def test_pixel_dropped_for_seniors_relax():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="p", name="Pixel XL",
            description_short="x", why_selected=["x"],
            start_time="11:00", end_time="12:00", duration_min=60,
            lat=52.39, lng=16.89, city="Poznan", cost_estimate=60,
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {
        "requested_city": "Poznan", "has_car": True, "day_end": "19:00",
        "group_type": "seniors", "travel_style": "relax",
        "preferences": ["relaxation"],
    }
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    names = [getattr(it, "name", "") or "" for it in out if _tv(it) == "attraction"]
    assert not any("pixel" in n.lower() for n in names), names


def test_generic_walk_dropped_for_kids():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="w", name="Spacer po miescie",
            description_short="", why_selected=["preference_fill"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=50.06, lng=19.94, city="Krakow", cost_estimate=0,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="z", name="Zoo Krakow",
            description_short="x", why_selected=["x"],
            start_time="12:00", end_time="14:00", duration_min=120,
            lat=50.05, lng=19.85, city="Krakow", cost_estimate=50,
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {
        "requested_city": "Krakow", "has_car": True, "day_end": "19:00",
        "group_type": "family_kids",
    }
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    names = [getattr(it, "name", "") or "" for it in out if _tv(it) == "attraction"]
    assert not any("spacer" in n.lower() for n in names), names
    assert any("zoo" in n.lower() for n in names)


def test_within_day_duplicate_attraction_dropped():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a1", name="Wawel",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=50.054, lng=19.935, city="Krakow", cost_estimate=40,
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:20",
            duration_min=20, from_location="Wawel", to_location="Sukiennice",
            mode=TransitMode.WALK, distance_km=0.8,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Sukiennice",
            description_short="x", why_selected=["x"],
            start_time="11:20", end_time="12:00", duration_min=40,
            lat=50.0617, lng=19.9373, city="Krakow", cost_estimate=0,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a2", name="Wawel",
            description_short="x", why_selected=["x"],
            start_time="15:00", end_time="16:00", duration_min=60,
            lat=50.054, lng=19.935, city="Krakow", cost_estimate=40,
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Krakow", "has_car": True, "day_end": "19:00"}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    wawels = [
        it for it in out
        if _tv(it) == "attraction" and "wawel" in (getattr(it, "name", "") or "").lower()
    ]
    assert len(wawels) == 1, wawels


def test_missing_cost_estimate_filled():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="m", name="MOCAK",
            description_short="x", why_selected=["x"],
            start_time="12:00", end_time="13:00", duration_min=60,
            lat=50.047, lng=19.961, city="Krakow",
            # cost_estimate intentionally omitted
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {
        "requested_city": "Krakow", "has_car": True, "day_end": "19:00",
        "date": __import__("datetime").date(2026, 4, 10),
    }
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    mocaks = [
        it for it in out
        if _tv(it) == "attraction" and "mocak" in (getattr(it, "name", "") or "").lower()
    ]
    assert mocaks
    assert getattr(mocaks[0], "cost_estimate", None) is not None


def test_transit_to_zoo_without_visit_dropped():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, FreeTimeItem, ItemType,
        TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Rynek",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=50.06, lng=19.94, city="Krakow", cost_estimate=0,
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:30",
            duration_min=30, from_location="Rynek", to_location="Zoo Krakow",
            mode=TransitMode.CAR, distance_km=5.0,
        ),
        FreeTimeItem(
            start_time="11:30", end_time="12:00", duration_min=30, label="Czas",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Krakow", "has_car": True, "day_end": "19:00"}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    zoo_hops = [
        it for it in out
        if _tv(it) == "transit"
        and "zoo" in (getattr(it, "to_location", "") or "").lower()
    ]
    assert not zoo_hops, zoo_hops


def test_wroclaw_p5_untouched():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="p", name="Pixel XL",
            description_short="x", why_selected=["x"],
            start_time="11:00", end_time="12:00", duration_min=60,
            lat=51.1, lng=17.0, city="Wroclaw", cost_estimate=60,
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {
        "requested_city": "Wroclaw", "group_type": "seniors",
        "travel_style": "relax",
    }
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    assert any(
        "pixel" in (getattr(it, "name", "") or "").lower()
        for it in out if _tv(it) == "attraction"
    )


def test_validator_p5_codes_and_open_mail_gate_owned():
    """Unit-level strengthened gate assertions for Krakow/Katowice/Poznan."""
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem,
        ItemType, TransitItem, TransitMode, FreeTimeItem,
    )

    OWNED = {
        "profile_mismatch",
        "missing_cost_estimate",
        "transit_without_visit",
        "preference_uncovered",
        "duplicate_poi",
        "target_group",
    }

    # Day defects
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="p", name="Pixel XL",
            description_short="x", why_selected=["x"],
            start_time="11:00", end_time="12:00", duration_min=60,
            lat=52.39, lng=16.89, city="Poznan", cost_estimate=60,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="m", name="MOCAK",
            description_short="x", why_selected=["x"],
            start_time="13:00", end_time="14:00", duration_min=60,
            lat=50.047, lng=19.961, city="Krakow",
            # missing cost_estimate
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="14:00", end_time="14:30",
            duration_min=30, from_location="MOCAK", to_location="Zoo Krakow",
            mode=TransitMode.CAR, distance_km=6.0,
        ),
        FreeTimeItem(start_time="14:30", end_time="15:00", duration_min=30, label="x"),
        DayEndItem(time="19:00"),
    ]
    report = Report()
    validate_day(
        city="Krakow", num=1, day_num=1, items=items, report=report,
        group_type="seniors", travel_style="relax",
        preferences=["active_sport", "underground", "nature_landscape"],
    )
    codes = {h.code for h in report.hits}
    assert "profile_mismatch" in codes or "target_group" in codes, codes
    assert "missing_cost_estimate" in codes, codes
    assert "transit_without_visit" in codes, codes
    assert "preference_uncovered" in codes, codes
    assert OWNED & codes, codes

    # Cross-day duplicate
    class _Day:
        def __init__(self, day, items):
            self.day = day
            self.items = items

    a1 = AttractionItem.model_construct(
        type=ItemType.ATTRACTION, poi_id="w", name="Wawel",
        description_short="x", why_selected=["x"],
        start_time="10:00", end_time="11:00", duration_min=60,
        lat=50.054, lng=19.935, city="Krakow", cost_estimate=40,
    )
    a2 = AttractionItem.model_construct(
        type=ItemType.ATTRACTION, poi_id="w2", name="Wawel",
        description_short="x", why_selected=["x"],
        start_time="10:00", end_time="11:00", duration_min=60,
        lat=50.054, lng=19.935, city="Krakow", cost_estimate=40,
    )
    class _Plan:
        days = [_Day(1, [a1]), _Day(2, [a2])]
    report2 = Report()
    validate_plan(city="Krakow", num=2, plan=_Plan(), group_type="couples", report=report2)
    assert any(h.code == "duplicate_poi" for h in report2.hits), report2.hits
