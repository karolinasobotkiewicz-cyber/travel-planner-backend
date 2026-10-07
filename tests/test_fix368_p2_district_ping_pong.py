"""FIX #368 P2 ? district clustering / anti ping-pong."""
from __future__ import annotations

from scripts.plan_quality_validator import Report, validate_day


def _svc():
    from app.application.services.plan_service import PlanService
    from app.infrastructure.repositories.poi_repository import POIRepository
    return PlanService(POIRepository("data/zakopane.xlsx"))


def _tv(it):
    t = getattr(it, "type", None)
    return t.value if hasattr(t, "value") else str(t or "")


def test_wawel_podgorze_wawel_ping_pong_dropped():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="w1", name="Wawel",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=50.054, lng=19.935, city="Krakow",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:25",
            duration_min=25, from_location="Wawel",
            to_location="Kopiec Krakusa", mode=TransitMode.WALK, distance_km=2.0,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="p", name="Kopiec Krakusa",
            description_short="x", why_selected=["x"],
            start_time="11:25", end_time="12:00", duration_min=35,
            lat=50.038, lng=19.958, city="Krakow",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="12:00", end_time="12:25",
            duration_min=25, from_location="Kopiec Krakusa",
            to_location="Wawel", mode=TransitMode.WALK, distance_km=2.0,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="w2", name="Smok Wawelski",
            description_short="x", why_selected=["x"],
            start_time="12:25", end_time="12:45", duration_min=20,
            lat=50.053, lng=19.934, city="Krakow",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Krakow", "has_car": True, "day_end": "19:00"}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    names = [getattr(it, "name", "") or "" for it in out if _tv(it) == "attraction"]
    assert names.count("Wawel") == 1
    assert "Kopiec Krakusa" in names
    assert not any("smok" in n.lower() for n in names), names


def test_rynek_pixel_rynek_poznan_dropped():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="r1", name="Stary Rynek",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=52.408, lng=16.934, city="Poznan",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:20",
            duration_min=20, from_location="Stary Rynek",
            to_location="Pixel XL", mode=TransitMode.CAR, distance_km=4.0,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="px", name="Pixel XL",
            description_short="x", why_selected=["x"],
            start_time="11:20", end_time="12:20", duration_min=60,
            lat=52.39, lng=16.89, city="Poznan",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="12:20", end_time="12:40",
            duration_min=20, from_location="Pixel XL",
            to_location="Stary Rynek", mode=TransitMode.CAR, distance_km=4.0,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="r2", name="Ratusz Poznan",
            description_short="x", why_selected=["x"],
            start_time="12:40", end_time="13:20", duration_min=40,
            lat=52.4085, lng=16.9345, city="Poznan",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Poznan", "has_car": True, "day_end": "19:00"}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    names = [getattr(it, "name", "") or "" for it in out if _tv(it) == "attraction"]
    assert "Pixel XL" in names
    assert not any("ratusz" in n.lower() for n in names), names
    assert sum(1 for n in names if "rynek" in n.lower()) == 1


def test_unjustified_cross_subregion_short_walk_dropped():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Neptun",
            description_short="x", why_selected=["x"],
            start_time="09:30", end_time="10:30", duration_min=60,
            lat=54.3486, lng=18.6532, city="Gdansk",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="10:30", end_time="10:40",
            duration_min=10, from_location="Neptun",
            to_location="Orlowo", mode=TransitMode.WALK, distance_km=0.4,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Orlowo",
            description_short="x", why_selected=["x"],
            start_time="10:40", end_time="11:40", duration_min=60,
            lat=54.4810, lng=18.5580, city="Gdynia",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Gdansk", "has_car": True, "day_end": "19:00"}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    names = [getattr(it, "name", "") or "" for it in out if _tv(it) == "attraction"]
    assert "Neptun" in names
    assert not any("orlowo" in n.lower() or "or?owo" in n.lower() for n in names), names


def test_wroclaw_ping_pong_untouched():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Rynek",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=51.11, lng=17.03, city="Wroclaw",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:20",
            duration_min=20, from_location="Rynek",
            to_location="Pixel XL", mode=TransitMode.CAR, distance_km=3.0,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Hala Stulecia",
            description_short="x", why_selected=["x"],
            start_time="11:20", end_time="12:00", duration_min=40,
            lat=51.107, lng=17.077, city="Wroclaw",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="12:00", end_time="12:20",
            duration_min=20, from_location="Hala Stulecia",
            to_location="Rynek", mode=TransitMode.CAR, distance_km=3.0,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="c", name="Sukiennice Fake",
            description_short="x", why_selected=["x"],
            start_time="12:20", end_time="13:00", duration_min=40,
            lat=51.11, lng=17.031, city="Wroclaw",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Wroclaw", "has_car": True}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    attrs = [it for it in out if _tv(it) == "attraction"]
    assert len(attrs) == 3, "locked city must not run P2 seal"


def test_validator_flags_district_ping_pong():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="s", name="Fabryka Schindlera",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=50.047, lng=19.961, city="Krakow",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:30",
            duration_min=30, from_location="Fabryka Schindlera",
            to_location="Sukiennice", mode=TransitMode.CAR, distance_km=3.5,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="o", name="Sukiennice",
            description_short="x", why_selected=["x"],
            start_time="11:30", end_time="12:30", duration_min=60,
            lat=50.0617, lng=19.9373, city="Krakow",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="12:30", end_time="13:00",
            duration_min=30, from_location="Sukiennice",
            to_location="Fabryka Schindlera", mode=TransitMode.CAR, distance_km=3.5,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="s2", name="Muzeum Schindlera",
            description_short="x", why_selected=["x"],
            start_time="13:00", end_time="14:00", duration_min=60,
            lat=50.047, lng=19.961, city="Krakow",
        ),
        DayEndItem(time="19:00"),
    ]
    report = Report()
    validate_day(city="Krakow", num=1, day_num=1, items=items, report=report)
    codes = {h.code for h in report.hits}
    assert "district_ping_pong" in codes, codes
