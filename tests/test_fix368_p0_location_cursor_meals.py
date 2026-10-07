"""FIX #368 P0 ? location cursor, meal anchors, ABA, generic hubs."""
from __future__ import annotations

from scripts.plan_quality_validator import Report, validate_day


def _svc():
    from app.application.services.plan_service import PlanService
    from app.infrastructure.repositories.poi_repository import POIRepository
    return PlanService(POIRepository("data/zakopane.xlsx"))


def _tv(it):
    t = getattr(it, "type", None)
    return t.value if hasattr(t, "value") else str(t or "")


def _sug(name: str):
    from app.domain.models.plan import RestaurantSuggestion
    return RestaurantSuggestion(
        id="r1", name=name, address="x", lat=50.06, lng=19.94,
        cuisine_type="polish", meal_type="lunch",
    )


def test_fix368_helpers_include_open_mail_not_locked():
    from app.application.services.plan_service import (
        _is_fix368_p0_city,
        _is_fix367_city,
        _timeline_meal_place_label,
    )
    from app.domain.models.plan import LunchBreakItem, ItemType

    assert _is_fix368_p0_city({"requested_city": "Krakow"})
    assert _is_fix368_p0_city({"requested_city": "Poznan"})
    assert _is_fix368_p0_city({"requested_city": "Katowice"})
    assert _is_fix368_p0_city({"requested_city": "Gdansk"})
    assert not _is_fix368_p0_city({"requested_city": "Wroclaw"})
    assert not _is_fix368_p0_city({"requested_city": "Zakopane"})
    assert not _is_fix367_city({"requested_city": "Krakow"})

    meal = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="12:00", end_time="13:00", duration_min=60,
        label="Lunch / przerwa regeneracyjna",
        suggestions=[_sug("Szalone Widelce")],
        location_context="centrum",
    )
    assert _timeline_meal_place_label(meal) == "Szalone Widelce"


def test_aba_motyl_revisit_after_leave_dropped():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="m", name="Muzeum Zywego Motyla",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=50.06, lng=19.94, city="Krakow",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:20",
            duration_min=20, from_location="Muzeum Zywego Motyla",
            to_location="Kosciol sw. Wojciecha", mode=TransitMode.WALK,
            distance_km=0.9,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="w", name="Kosciol sw. Wojciecha",
            description_short="x", why_selected=["x"],
            start_time="11:20", end_time="12:00", duration_min=40,
            lat=50.061, lng=19.937, city="Krakow",
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="m2", name="Muzeum Zywego Motyla",
            description_short="x", why_selected=["x"],
            start_time="12:30", end_time="13:00", duration_min=30,
            lat=50.06, lng=19.94, city="Krakow",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Krakow", "has_car": True, "day_end": "19:00"}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    motyls = [
        it for it in out
        if _tv(it) == "attraction"
        and "motyl" in (getattr(it, "name", "") or "").lower()
    ]
    assert len(motyls) == 1, [getattr(m, "name", None) for m in motyls]


def test_aba_meal_after_leave_scrubbed():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType,
        LunchBreakItem, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="12:00", end_time="13:00", duration_min=60,
            label="Lunch / przerwa regeneracyjna",
            suggestions=[_sug("Szalone Widelce")],
            location_context="centrum",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="13:00", end_time="13:20",
            duration_min=20, from_location="Szalone Widelce",
            to_location="Bulwary Wislane", mode=TransitMode.WALK,
            distance_km=1.0,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Bulwary Wislane",
            description_short="x", why_selected=["x"],
            start_time="13:20", end_time="14:20", duration_min=60,
            lat=50.055, lng=19.95, city="Krakow",
        ),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="14:30", end_time="15:15", duration_min=45,
            label="Lunch",
            suggestions=[_sug("Szalone Widelce")],
            location_context="Szalone Widelce",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Krakow", "has_car": True, "day_end": "19:00"}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    meals = [it for it in out if _tv(it) == "lunch_break"]
    assert len(meals) >= 1
    last = meals[-1]
    sugs = getattr(last, "suggestions", None) or []
    names = []
    for s in sugs:
        names.append(s.get("name") if isinstance(s, dict) else getattr(s, "name", ""))
    assert not any("szalone" in (n or "").lower() for n in names), names


def test_generic_hub_krakow_midday_dropped():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
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
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:10",
            duration_min=10, from_location="Wawel",
            to_location="Krakow", mode=TransitMode.WALK, distance_km=0.5,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Sukiennice",
            description_short="x", why_selected=["x"],
            start_time="11:30", end_time="12:00", duration_min=30,
            lat=50.0617, lng=19.9373, city="Krakow",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Krakow", "has_car": True, "day_end": "19:00"}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    hubs = [
        it for it in out
        if _tv(it) == "transit"
        and (
            (getattr(it, "to_location", "") or "").strip().lower() in ("krak?w", "krakow")
            or (getattr(it, "from_location", "") or "").strip().lower() in ("krak?w", "krakow")
        )
    ]
    assert not hubs, hubs


def test_return_to_car_without_drive_dropped_krakow():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Parking Florianska",
            description_short="x", why_selected=["x"],
            start_time="09:30", end_time="10:00", duration_min=30,
            lat=50.065, lng=19.941, city="Krakow",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="10:00", end_time="10:15",
            duration_min=15, from_location="Parking Florianska",
            to_location="Barbakan", mode=TransitMode.WALK, distance_km=0.6,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Barbakan",
            description_short="x", why_selected=["x"],
            start_time="10:15", end_time="11:00", duration_min=45,
            lat=50.0655, lng=19.9415, city="Krakow",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:15",
            duration_min=15, from_location="Barbakan",
            to_location="Parking Florianska", mode=TransitMode.WALK,
            distance_km=0.6, routing_source="return_to_car",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:15", end_time="11:30",
            duration_min=15, from_location="Parking Florianska",
            to_location="Planty", mode=TransitMode.WALK, distance_km=0.5,
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Krakow", "has_car": True, "day_end": "19:00"}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    returns = [
        it for it in out
        if "return" in str(getattr(it, "routing_source", "") or "").lower()
    ]
    assert not returns, returns


def test_validator_flags_aba_meal_and_stale_walk():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType,
        LunchBreakItem, TransitItem, TransitMode,
    )

    items = [
        DayStartItem(time="09:00"),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="12:00", end_time="13:00", duration_min=60,
            label="Lunch",
            suggestions=[_sug("Lokalna Restauracja")],
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="13:00", end_time="13:30",
            duration_min=30, from_location="Lokalna Restauracja",
            to_location="Rynek", mode=TransitMode.CAR, distance_km=4.0,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="r", name="Rynek",
            description_short="x", why_selected=["x"],
            start_time="13:30", end_time="14:30", duration_min=60,
            lat=52.4, lng=16.9, city="Poznan",
        ),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="14:40", end_time="15:20", duration_min=40,
            label="Lunch",
            suggestions=[_sug("Lokalna Restauracja")],
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="15:20", end_time="15:40",
            duration_min=20, from_location="Lokalna Restauracja",
            to_location="Fotoplastykon", mode=TransitMode.WALK, distance_km=0.8,
        ),
        DayEndItem(time="19:00"),
    ]
    report = Report()
    validate_day(city="Poznan", num=1, day_num=1, items=items, report=report)
    codes = {h.code for h in report.hits}
    assert "aba_visit_after_leave" in codes or "stale_walk_start" in codes, codes


def test_validator_flags_generic_hub_poznan():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Stary Rynek",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=52.408, lng=16.934, city="Poznan",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:10",
            duration_min=10, from_location="Stary Rynek",
            to_location="Ratusz", mode=TransitMode.WALK, distance_km=0.3,
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:15", end_time="11:25",
            duration_min=10, from_location="Ratusz",
            to_location="Poznan", mode=TransitMode.WALK, distance_km=0.4,
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:30", end_time="11:50",
            duration_min=20, from_location="Poznan",
            to_location="Muzeum Bambrow", mode=TransitMode.WALK, distance_km=0.7,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Muzeum Bambrow",
            description_short="x", why_selected=["x"],
            start_time="11:50", end_time="12:30", duration_min=40,
            lat=52.41, lng=16.93, city="Poznan",
        ),
        DayEndItem(time="19:00"),
    ]
    report = Report()
    validate_day(city="Poznan", num=2, day_num=1, items=items, report=report)
    codes = {h.code for h in report.hits}
    assert "generic_hub" in codes, codes
