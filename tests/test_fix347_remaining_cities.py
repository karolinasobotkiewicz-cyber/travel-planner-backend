"""FIX #347 — morning-before-lunch plant + collapse hub-walk then car."""
from __future__ import annotations


def _svc():
    from app.application.services.plan_service import PlanService
    from app.infrastructure.repositories.poi_repository import POIRepository
    return PlanService(POIRepository("data/zakopane.xlsx"))


def test_collapse_hub_walk_then_car():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a",
            name="Śląskie Centrum Wolności i Solidarności",
            description_short="", why_selected=["x"],
            start_time="09:10", end_time="11:00", duration_min=110,
            lat=50.264, lng=19.023, city="Katowice",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:10",
            duration_min=10, from_location="Śląskie Centrum Wolności i Solidarności",
            to_location="Katowice", mode=TransitMode.WALK, distance_km=0.5,
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:10", end_time="11:30",
            duration_min=20, from_location="Katowice",
            to_location="Muzeum Śląskie", mode=TransitMode.CAR, distance_km=5.5,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Muzeum Śląskie",
            description_short="", why_selected=["x"],
            start_time="11:30", end_time="13:00", duration_min=90,
            lat=50.261, lng=19.035, city="Katowice",
        ),
        DayEndItem(time="18:00"),
    ]
    out = svc._collapse_phantom_hub_detours(
        items, {"requested_city": "Katowice"}, day_num=1,
    )
    hops = [
        it for it in out
        if str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "transit"
    ]
    assert len(hops) == 1
    assert "wolności" in (getattr(hops[0], "from_location", "") or "").lower()
    assert "śląskie" in (getattr(hops[0], "to_location", "") or "").lower()
    wro = svc._collapse_phantom_hub_detours(
        items, {"requested_city": "Wrocław"}, day_num=1,
    )
    wro_hops = [
        it for it in wro
        if str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "transit"
    ]
    assert len(wro_hops) == 2


def test_real_parking_return_is_not_collapsed():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="09:00", end_time="09:12",
            duration_min=12, from_location="Kraków", to_location="Planty",
            mode=TransitMode.WALK, distance_km=0.8,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="p", name="Planty",
            description_short="", why_selected=["x"],
            start_time="09:12", end_time="10:00", duration_min=48,
            lat=50.061, lng=19.937, city="Kraków",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="10:00", end_time="10:05",
            duration_min=5, from_location="Planty", to_location="Kraków",
            mode=TransitMode.WALK, distance_km=0.1,
            routing_source="estimated_walk",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="10:05", end_time="10:20",
            duration_min=15, from_location="Kraków",
            to_location="Fabryka Emalia Oskara Schindlera",
            mode=TransitMode.CAR, distance_km=3.4,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="s",
            name="Fabryka Emalia Oskara Schindlera",
            description_short="", why_selected=["x"],
            start_time="10:20", end_time="12:00", duration_min=100,
            lat=50.047, lng=19.961, city="Kraków",
        ),
        DayEndItem(time="18:00"),
    ]
    out = svc._collapse_phantom_hub_detours(
        items, {"requested_city": "Kraków"}, day_num=1,
    )
    hops = [
        it for it in out
        if str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "transit"
    ]
    assert len(hops) == 3
    cars = [
        it for it in hops
        if "car" in str(getattr(getattr(it, "mode", None), "value", getattr(it, "mode", ""))).lower()
    ]
    assert "planty" not in (getattr(cars[0], "from_location", "") or "").lower()


def test_planetarium_and_wieliczka_have_seed_coords():
    from app.application.services.plan_service import _seed_first_stop_coords

    plat = _seed_first_stop_coords("Planetarium Śląskie")
    assert plat is not None
    assert abs(plat[0] - 50.29) < 0.05
    wiel = _seed_first_stop_coords("Rynek Górny w Wieliczce")
    assert wiel is not None
    assert abs(wiel[0] - 49.98) < 0.05
    ojcow = _seed_first_stop_coords("Rezerwat przyrody Dolina Eliaszówki")
    assert ojcow is not None


def test_morning_fill_unknown_hours_are_not_closed():
    from app.application.services.plan_service import PlanService

    svc = _svc()
    poi = {"name": "Spodek w Katowicach", "lat": 50.266, "lng": 19.023, "time_min": 40}
    assert svc._poi_open_window(poi, "2026-02-20") is None
    # Plant path: unknown hours + _morning_fill must not skip.
    ctx = {
        "requested_city": "Katowice",
        "_morning_fill": True,
        "day_start": "09:00",
        "day_end": "18:00",
        "has_car": True,
        "user": {"target_group": "friends", "preferences": ["active_sport"]},
    }
    from app.domain.models.plan import DayEndItem, DayStartItem, ItemType, LunchBreakItem

    items = [
        DayStartItem(time="09:00"),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="12:00", end_time="13:00", duration_min=60,
            suggestions=[], label="BUŁKĘS",
        ),
        DayEndItem(time="18:00"),
    ]
    ctx["poi_pool"] = [poi]
    out = svc._fill_naked_midday_gaps(items, ctx, day_num=2)
    names = [getattr(it, "name", "") for it in out]
    assert any("spodek" in (n or "").lower() for n in names)
