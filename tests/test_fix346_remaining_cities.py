"""FIX #346 — remaining-city empty days, far satellites, city labels, dinner."""
from __future__ import annotations


def _svc():
    from app.application.services.plan_service import PlanService
    from app.infrastructure.repositories.poi_repository import POIRepository
    return PlanService(POIRepository("data/zakopane.xlsx"))


def test_lunch_only_day_is_not_emptied():
    from app.domain.models.plan import (
        DayEndItem, DayStartItem, ItemType, LunchBreakItem,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="12:10", end_time="13:00", duration_min=50,
            suggestions=[], label="Lunch",
        ),
        DayEndItem(time="18:00"),
    ]
    ctx = {"requested_city": "Katowice", "day_start": "09:00", "day_end": "18:00"}
    out, exhausted = svc._close_day_when_nothing_left(items, ctx, day_num=3)
    assert exhausted is False
    assert any(
        str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "lunch_break"
        for it in out
    )
    wro, wro_ex = svc._close_day_when_nothing_left(
        items, {"requested_city": "Wrocław", "day_start": "09:00"}, day_num=3,
    )
    assert wro_ex is True
    assert not any(
        str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "lunch_break"
        for it in wro
    )


def test_inverted_day_end_snaps_forward():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="18:30"),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="18:30", end_time="18:50",
            duration_min=20, from_location="Spodek", to_location="Nikiszowiec",
            mode=TransitMode.CAR, distance_km=8.0,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="n", name="Nikiszowiec",
            description_short="", why_selected=["x"],
            start_time="18:50", end_time="19:20", duration_min=30,
            lat=50.244, lng=19.081,
        ),
        DayEndItem(time="09:00"),
    ]
    out = svc._snap_day_start_to_first_leg(
        items, {"requested_city": "Katowice"}, day_num=2,
    )
    end = next(
        it for it in out
        if str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "day_end"
    )
    assert getattr(end, "time", None) >= "19:20"


def test_far_low_roi_skansen_is_dropped():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Stary Rynek",
            description_short="", why_selected=["x"],
            start_time="09:30", end_time="10:30", duration_min=60,
            lat=52.408, lng=16.934, city="Poznań",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="10:30", end_time="11:21",
            duration_min=51, from_location="Stary Rynek",
            to_location="Park im. Fryderyka Chopina",
            mode=TransitMode.CAR, distance_km=36.8,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="p",
            name="Park im. Fryderyka Chopina",
            description_short="", why_selected=["x"],
            start_time="11:38", end_time="13:00", duration_min=82,
            lat=50.297, lng=18.665, city="Katowice",
        ),
        DayEndItem(time="18:00"),
    ]
    out = svc._drop_far_low_roi_stops(
        items, {"requested_city": "Katowice"}, day_num=3,
    )
    names = [getattr(it, "name", "") for it in out if getattr(it, "name", None)]
    assert not any("chopina" in (n or "").lower() for n in names)
    wro = svc._drop_far_low_roi_stops(
        items, {"requested_city": "Wrocław"}, day_num=3,
    )
    wro_names = [getattr(it, "name", "") for it in wro if getattr(it, "name", None)]
    assert any("chopina" in (n or "").lower() for n in wro_names)


def test_satellite_city_labels():
    from app.application.services.plan_service import _satellite_city_for_stop
    from app.domain.models.plan import AttractionItem, ItemType
    from app.domain.planner.poi_copy import build_fallback_copy, classify_poi_category

    assert _satellite_city_for_stop("Park Chopina") == "Gliwice"
    assert _satellite_city_for_stop("Park im. Fryderyka Chopina") == "Gliwice"
    assert _satellite_city_for_stop("Szyb Maciej") == "Zabrze"
    assert _satellite_city_for_stop("Ostrów Lednicki") == "Lednogóra"
    assert _satellite_city_for_stop("Park Orientacji Przestrzennej w Pobiedziskach") == "Pobiedziska"
    assert _satellite_city_for_stop("Planetarium Śląskie") == "Chorzów"
    assert _satellite_city_for_stop("Nikiszowiec") == "Katowice"

    svc = _svc()
    items = [
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="l", name="Ostrów Lednicki",
            description_short="", why_selected=["Must-see w Poznaniu"],
            start_time="11:00", end_time="12:30", duration_min=90,
            lat=52.527, lng=17.375, city="Poznań",
        ),
    ]
    out = svc._rewrite_katowice_satellite_copy(items, day_num=2)
    assert getattr(out[0], "city", "") == "Lednogóra"
    assert classify_poi_category({"name": "Bajkowy Labirynt", "tags": []}) == "mirror_maze"
    desc, _tip = build_fallback_copy({"name": "Bajkowy Labirynt", "city": "Katowice"})
    assert "budynku" in desc.lower() or "indoor" in desc.lower()


def test_adventure_caps_museum_stack():
    from app.domain.models.plan import AttractionItem, ItemType

    svc = _svc()
    items = [
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id=f"m{i}", name=f"Muzeum {i}",
            description_short="", why_selected=["x"],
            start_time=f"{10+i}:00", end_time=f"{11+i}:00", duration_min=60,
            lat=50.26, lng=19.02,
        )
        for i in range(3)
    ]
    out = svc._strip_excessive_museums_same_day(
        items,
        {"target_group": "friends", "travel_style": "adventure",
         "preferences": ["active_sport", "history_mystery"]},
        day_num=1,
    )
    mus = [it for it in out if "muzeum" in (getattr(it, "name", "") or "").lower()]
    assert len(mus) == 1


def test_trip_level_kopce_and_dinner_on_long_remaining_trip():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="k", name="Kopiec Kościuszki",
            description_short="", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=50.055, lng=19.893,
        ),
        DayEndItem(time="20:00"),
    ]
    out = svc._drop_repeat_mounds(
        items, day_num=4, context={"trip_attraction_names": {"Kopiec Krakusa"}},
    )
    assert not any(
        "kopiec" in (getattr(it, "name", "") or "").lower() for it in out
    )
    dinner_in = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Wawel",
            description_short="", why_selected=["x"],
            start_time="10:00", end_time="16:00", duration_min=360,
            lat=50.054, lng=19.935,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Sukiennice",
            description_short="", why_selected=["x"],
            start_time="16:10", end_time="16:40", duration_min=30,
            lat=50.061, lng=19.937,
        ),
        DayEndItem(time="20:00"),
    ]
    ctx = {
        "requested_city": "Kraków", "num_days": 7, "day_end": "20:00",
    }
    with_d = svc._ensure_dinner_present(dinner_in, "20:00", ctx)
    assert any(
        str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "dinner_break"
        for it in with_d
    )
    locked = svc._ensure_dinner_present(
        dinner_in, "20:00",
        {"requested_city": "Wrocław", "num_days": 7, "day_end": "20:00"},
    )
    assert not any(
        str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "dinner_break"
        for it in locked
    )
