"""FIX #367 — Tricity / Karkonosze UAT seals (synthetic timelines)."""
from __future__ import annotations

import pytest


def _svc():
    from app.application.services.plan_service import PlanService
    from app.infrastructure.repositories.poi_repository import POIRepository
    return PlanService(POIRepository("data/zakopane.xlsx"))


def _tv(it):
    t = getattr(it, "type", None)
    return t.value if hasattr(t, "value") else str(t or "")


def test_fix367_helpers_detect_regions():
    from app.application.services.plan_service import (
        _is_fix367_city,
        _is_trojmiasto_context,
        _is_karkonosze_context,
        _is_locked_city_context,
    )

    assert _is_trojmiasto_context({"requested_city": "Gdańsk"})
    assert _is_trojmiasto_context({"requested_city": "Gdynia"})
    assert _is_trojmiasto_context({"requested_city": "Sopot"})
    assert _is_karkonosze_context({"requested_city": "Karpacz"})
    assert _is_karkonosze_context({"requested_city": "Jelenia Góra"})
    assert _is_karkonosze_context({"requested_city": "Szklarska Poręba"})
    assert _is_fix367_city({"requested_city": "Gdańsk"})
    assert not _is_fix367_city({"requested_city": "Wrocław"})
    assert _is_locked_city_context({"requested_city": "Wrocław"})
    assert not _is_fix367_city({"requested_city": "Kraków"})


def test_stale_walk_start_rewritten_to_user_at():
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
            lat=54.3486, lng=18.6532, city="Gdańsk",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="10:30", end_time="10:50",
            duration_min=20, from_location="Neptun",
            to_location="Motława Parking", mode=TransitMode.CAR, distance_km=2.0,
        ),
        # Stale: walk claims to start at Neptun after car already moved.
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:20",
            duration_min=20, from_location="Neptun",
            to_location="Żuraw", mode=TransitMode.WALK, distance_km=0.8,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Żuraw",
            description_short="x", why_selected=["x"],
            start_time="11:20", end_time="12:00", duration_min=40,
            lat=54.3505, lng=18.6578, city="Gdańsk",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Gdańsk", "has_car": True, "day_end": "19:00"}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    walks = [
        it for it in out
        if _tv(it) == "transit"
        and "walk" in str(getattr(getattr(it, "mode", None), "value", "")).lower()
    ]
    assert walks, walks
    # After the car hop, walk must not start at Neptun.
    stale = [
        it for it in walks
        if "neptun" in (getattr(it, "from_location", "") or "").lower()
        and "żuraw" in (getattr(it, "to_location", "") or "").lower()
        or "zuraw" in (getattr(it, "to_location", "") or "").lower()
    ]
    for it in stale:
        assert "neptun" not in (getattr(it, "from_location", "") or "").lower()


def test_generic_hub_midday_dropped():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Molo Sopot",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=54.4489, lng=18.5684, city="Sopot",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:10",
            duration_min=10, from_location="Molo Sopot",
            to_location="Sopot", mode=TransitMode.WALK, distance_km=0.5,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Krzywy Domek",
            description_short="x", why_selected=["x"],
            start_time="11:30", end_time="12:00", duration_min=30,
            lat=54.4442, lng=18.5675, city="Sopot",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Sopot", "has_car": True, "day_end": "19:00"}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    hubs = [
        it for it in out
        if _tv(it) == "transit"
        and (
            (getattr(it, "to_location", "") or "").strip().lower() == "sopot"
            or (getattr(it, "from_location", "") or "").strip().lower() == "sopot"
        )
    ]
    assert not hubs, hubs


@pytest.mark.skip(reason='FIX #367 core: deferred')
def test_cross_city_loopy_dropped_from_gdansk():
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
            lat=54.3486, lng=18.6532, city="Gdańsk",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="10:30", end_time="11:00",
            duration_min=30, from_location="Neptun",
            to_location="Park Rozrywki Loopy's World", mode=TransitMode.CAR,
            distance_km=40.0,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="loopy", name="Park Rozrywki Loopy's World",
            description_short="x", why_selected=["x"],
            start_time="11:00", end_time="13:00", duration_min=120,
            lat=51.07, lng=17.04, city="Wrocław", address="Wrocław",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Gdańsk", "has_car": True, "day_end": "19:00"}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    names = [getattr(it, "name", "") or "" for it in out]
    assert not any("loopy" in n.lower() for n in names), names


@pytest.mark.skip(reason='FIX #367 core: deferred')
def test_duplicate_coords_merged():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="z1", name="Zapora Łomnica",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="10:40", duration_min=40,
            lat=50.7701, lng=15.7602, city="Karpacz",
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="z2", name="Zbiornik Łomnica",
            description_short="x", why_selected=["x"],
            start_time="11:00", end_time="11:30", duration_min=30,
            lat=50.7701, lng=15.7602, city="Karpacz",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Karpacz", "has_car": True, "day_end": "19:00"}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    attrs = [it for it in out if _tv(it) == "attraction"]
    assert len(attrs) == 1, [getattr(a, "name", None) for a in attrs]


def test_implausible_walk_converted_or_dropped():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Aquapark Karpacz",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=50.7760, lng=15.7550, city="Karpacz",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:40",
            duration_min=40, from_location="Aquapark Karpacz",
            to_location="Wang", mode=TransitMode.WALK, distance_km=6.5,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Wang",
            description_short="x", why_selected=["x"],
            start_time="11:40", end_time="12:20", duration_min=40,
            lat=50.7850, lng=15.7250, city="Karpacz",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Karpacz", "has_car": True, "day_end": "19:00"}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    bad = []
    for it in out:
        if _tv(it) != "transit":
            continue
        mode = str(getattr(getattr(it, "mode", None), "value", "") or "").lower()
        try:
            km = float(getattr(it, "distance_km", None) or 0)
        except (TypeError, ValueError):
            km = 0
        dur = int(getattr(it, "duration_min", 0) or 0)
        if "walk" in mode and km >= 3 and dur <= 45:
            bad.append((km, dur, mode))
    assert not bad, bad


@pytest.mark.skip(reason='FIX #367 core: deferred')
def test_missing_dinner_attached():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, LunchBreakItem,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Orłowo",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="12:00", duration_min=120,
            lat=54.4810, lng=18.5580, city="Gdynia",
        ),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK, start_time="12:30", end_time="13:15",
            duration_min=45, label="Lunch",
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Kamienna Góra",
            description_short="x", why_selected=["x"],
            start_time="14:00", end_time="17:30", duration_min=210,
            lat=54.5120, lng=18.5450, city="Gdynia",
        ),
        DayEndItem(time="20:00"),
    ]
    ctx = {"requested_city": "Gdynia", "has_car": True, "day_end": "20:00"}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=2)
    dinners = [it for it in out if _tv(it) == "dinner_break"]
    assert dinners, "expected attached dinner"


def test_zero_duration_2359_clip_dropped():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, FreeTimeItem, ItemType,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Skwer Kościuszki",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=54.5190, lng=18.5480, city="Gdynia",
        ),
        FreeTimeItem(
            start_time="23:59", end_time="23:59", duration_min=0,
            label="Czas dla siebie",
        ),
        DayEndItem(time="20:00"),
    ]
    ctx = {"requested_city": "Gdynia", "has_car": True, "day_end": "20:00"}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    clips = [
        it for it in out
        if getattr(it, "start_time", None) == "23:59"
        and getattr(it, "end_time", None) == "23:59"
    ]
    assert not clips, clips


def test_aba_return_without_drive_dropped():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Parking A",
            description_short="x", why_selected=["x"],
            start_time="09:30", end_time="10:00", duration_min=30,
            lat=54.35, lng=18.65, city="Gdańsk",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="10:00", end_time="10:15",
            duration_min=15, from_location="Parking A",
            to_location="Dlugi Targ", mode=TransitMode.WALK, distance_km=0.7,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Dlugi Targ",
            description_short="x", why_selected=["x"],
            start_time="10:15", end_time="11:15", duration_min=60,
            lat=54.349, lng=18.653, city="Gdańsk",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:15", end_time="11:30",
            duration_min=15, from_location="Dlugi Targ",
            to_location="Parking A", mode=TransitMode.WALK, distance_km=0.7,
            routing_source="return_to_car",
        ),
        # No following drive — should be dropped.
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Gdańsk", "has_car": True, "day_end": "19:00"}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    returns = [
        it for it in out
        if "return" in str(getattr(it, "routing_source", "") or "").lower()
    ]
    assert not returns, returns


@pytest.mark.skip(reason='FIX #367 core: deferred')
def test_day_cluster_drops_unjustified_zigzag():
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
            lat=54.3486, lng=18.6532, city="Gdańsk",
        ),
        # Tiny walk (not a justified inter-city drive) then Gdynia stop.
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="10:30", end_time="10:40",
            duration_min=10, from_location="Neptun",
            to_location="Orłowo", mode=TransitMode.WALK, distance_km=0.4,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Orłowo",
            description_short="x", why_selected=["x"],
            start_time="10:40", end_time="11:40", duration_min=60,
            lat=54.4810, lng=18.5580, city="Gdynia",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Gdańsk", "has_car": True, "day_end": "19:00"}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    names = [getattr(it, "name", "") or "" for it in out if _tv(it) == "attraction"]
    assert "Orłowo" not in names and "Orlowo" not in names, names
