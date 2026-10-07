"""FIX #368 P4 ? recompute stale walk/drive distance+duration from coords."""
from __future__ import annotations

from scripts.plan_quality_validator import Report, validate_day


def _svc():
    from app.application.services.plan_service import PlanService
    from app.infrastructure.repositories.poi_repository import POIRepository
    return PlanService(POIRepository("data/zakopane.xlsx"))


def _tv(it):
    t = getattr(it, "type", None)
    return t.value if hasattr(t, "value") else str(t or "")


def test_bulwary_obwarzanek_stale_short_leg_recomputed():
    """UAT: declared 0.275 km while endpoints are ~2 km apart."""
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )
    from app.infrastructure.routing.haversine import haversine_km

    svc = _svc()
    # Approx Krakow Bulwary vs Obwarzanek Museum area (~2km)
    bul = (50.0545, 19.9330)
    obw = (50.0615, 19.9375)
    real = haversine_km(bul[0], bul[1], obw[0], obw[1])
    assert real >= 0.8, real

    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Bulwary Wislane",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=bul[0], lng=bul[1], city="Krakow",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:05",
            duration_min=5, from_location="Bulwary Wislane",
            to_location="Muzeum Obwarzanka", mode=TransitMode.WALK,
            distance_km=0.275,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="o", name="Muzeum Obwarzanka",
            description_short="x", why_selected=["x"],
            start_time="11:05", end_time="11:45", duration_min=40,
            lat=obw[0], lng=obw[1], city="Krakow",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Krakow", "has_car": True, "day_end": "19:00"}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    legs = [it for it in out if _tv(it) == "transit"]
    assert legs, legs
    leg = next(
        it for it in legs
        if "obwarz" in (getattr(it, "to_location", "") or "").lower()
        or "obwarz" in (getattr(it, "from_location", "") or "").lower()
    )
    km = float(getattr(leg, "distance_km", 0) or 0)
    assert km >= 0.8, km
    assert int(getattr(leg, "duration_min", 0) or 0) >= 10


def test_rogalinek_nooks_long_understated_becomes_car():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    # ~16 km apart-ish (Rogalin-ish vs Poznan center)
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="r", name="Rogalinek",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=52.2444, lng=16.9000, city="Poznan",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:10",
            duration_min=10, from_location="Rogalinek",
            to_location="NOOKS", mode=TransitMode.WALK, distance_km=0.4,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="n", name="NOOKS",
            description_short="x", why_selected=["x"],
            start_time="11:10", end_time="12:00", duration_min=50,
            lat=52.406, lng=16.925, city="Poznan",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Poznan", "has_car": True, "day_end": "19:00"}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    legs = [
        it for it in out
        if _tv(it) == "transit"
        and "nooks" in (getattr(it, "to_location", "") or "").lower()
    ]
    assert legs, legs
    leg = legs[0]
    km = float(getattr(leg, "distance_km", 0) or 0)
    assert km >= 10.0, km
    mode = str(getattr(getattr(leg, "mode", None), "value", getattr(leg, "mode", ""))).lower()
    assert "car" in mode, mode


def test_botaniczny_sorrento_stale_leg_recomputed():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Ogrod Botaniczny",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=50.063, lng=19.955, city="Krakow",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:05",
            duration_min=5, from_location="Ogrod Botaniczny",
            to_location="Sorrento", mode=TransitMode.WALK, distance_km=0.2,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="s", name="Sorrento",
            description_short="x", why_selected=["x"],
            start_time="11:05", end_time="12:00", duration_min=55,
            lat=50.052, lng=19.940, city="Krakow",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Krakow", "has_car": True, "day_end": "19:00"}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    legs = [
        it for it in out
        if _tv(it) == "transit"
        and "sorrento" in (getattr(it, "to_location", "") or "").lower()
    ]
    assert legs
    assert float(getattr(legs[0], "distance_km", 0) or 0) >= 0.8


def test_wroclaw_stale_leg_not_recomputed_by_seal():
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
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:05",
            duration_min=5, from_location="Rynek",
            to_location="Hala Stulecia", mode=TransitMode.WALK, distance_km=0.2,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Hala Stulecia",
            description_short="x", why_selected=["x"],
            start_time="11:05", end_time="12:00", duration_min=55,
            lat=51.107, lng=17.077, city="Wroclaw",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Wroclaw", "has_car": True}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    legs = [it for it in out if _tv(it) == "transit"]
    assert legs and float(getattr(legs[0], "distance_km", 0) or 0) == 0.2


def test_validator_flags_stale_leg_distance():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Bulwary Wislane",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=50.0545, lng=19.9330, city="Krakow",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:05",
            duration_min=5, from_location="Bulwary Wislane",
            to_location="Muzeum Obwarzanka", mode=TransitMode.WALK,
            distance_km=0.275,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Muzeum Obwarzanka",
            description_short="x", why_selected=["x"],
            start_time="11:05", end_time="11:45", duration_min=40,
            lat=50.0615, lng=19.9375, city="Krakow",
        ),
        DayEndItem(time="19:00"),
    ]
    report = Report()
    validate_day(city="Krakow", num=1, day_num=1, items=items, report=report)
    codes = {h.code for h in report.hits}
    assert "stale_leg_distance" in codes, codes
