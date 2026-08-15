"""FIX #269 — Wrocław remaining client: gaps, transits, day_end, Pana Tadeusza."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    DinnerBreakItem,
    ItemType,
    LunchBreakItem,
    ParkingInfo,
    RestaurantSuggestion,
    TicketInfo,
    TransitItem,
    TransitMode,
)
from app.domain.planner.engine import (
    get_transport_mode,
    is_evening_preferred_poi,
    poi_geo_region_key,
    travel_time_minutes,
)
from app.domain.scoring.profile_poi_rules import poi_trip_repeat_key, should_deny_poi_for_profile
from app.infrastructure.repositories import POIRepository
from app.infrastructure.repositories.normalizer import normalize_poi


def _attr(name: str, st: str, en: str, lat: float, lng: float) -> AttractionItem:
    sh, sm = (int(x) for x in st.split(":"))
    eh, em = (int(x) for x in en.split(":"))
    dur = eh * 60 + em - (sh * 60 + sm)
    return AttractionItem(
        poi_id="t",
        name=name,
        start_time=st,
        end_time=en,
        duration_min=dur,
        description_short="d",
        lat=lat,
        lng=lng,
        address="a",
        cost_estimate=0,
        ticket_info=TicketInfo(ticket_normal=0, ticket_reduced=0),
        parking=ParkingInfo(name="p", walk_time_min=0),
    )


def _svc() -> PlanService:
    return PlanService(POIRepository(str(Path("data") / "multi_city_attractions.xlsx")))


def test_fix269_pana_tadeusza_trip_key():
    assert poi_trip_repeat_key("Muzeum Pana Tadeusza") == "wro_pana_tadeusza"


def test_fix269_cross_day_pana_stripped():
    def _attr(name: str):
        return SimpleNamespace(
            type=ItemType.ATTRACTION,
            name=name,
            start_time="10:00",
            end_time="11:00",
            duration_min=60,
            poi_id=None,
            lat=51.1,
            lng=17.0,
        )

    days = [
        SimpleNamespace(
            day=1, quality_badges=None, date=None, weekday=None,
            items=[_attr("Muzeum Pana Tadeusza")],
        ),
        SimpleNamespace(
            day=3, quality_badges=None, date=None, weekday=None,
            items=[_attr("Muzeum Pana Tadeusza"), _attr("Hydropolis")],
        ),
    ]
    out = _svc()._strip_cross_day_trip_repeats(days)
    d3 = [getattr(it, "name", "") for it in (out[1].items or [])]
    assert not any("tadeusza" in n.lower() for n in d3)
    assert any("Hydropolis" in n for n in d3)


def test_fix269_iluzja_address_forced():
    poi = normalize_poi(
        {
            "Name": "Muzeum Świat Iluzji we Wrocławiu",
            "City": "Wrocław",
            "lat": 51.1069,
            "lng": 17.0773,
            "address": "",
            "time_min": 60,
            "time_max": 90,
        },
        0,
    )
    assert (poi.get("address") or "").strip()
    assert "świdnicka" in (poi.get("address") or "").lower() or "swidnicka" in (
        (poi.get("address") or "").lower()
    )


def test_fix269_ostrow_evening_preferred():
    assert is_evening_preferred_poi({"name": "Ostrów Tumski"})


def test_fix269_dinner_label_not_static_regional():
    d = DinnerBreakItem(
        type=ItemType.DINNER_BREAK,
        start_time="18:00",
        end_time="19:00",
        duration_min=60,
        suggestions=[],
    )
    assert "regionalne" not in (d.label or "").lower()


def test_fix269_retarget_transit_from_prev_stop():
    svc = _svc()
    items = [
        SimpleNamespace(
            type=ItemType.ATTRACTION, name="Movie Gate",
            start_time="10:00", end_time="11:00", duration_min=60,
        ),
        TransitItem(
            type=ItemType.TRANSIT,
            mode=TransitMode.CAR,
            from_location="Konspira",
            to_location="Hala Stulecia",
            start_time="11:00",
            end_time="11:15",
            duration_min=15,
        ),
        SimpleNamespace(
            type=ItemType.ATTRACTION, name="Hala Stulecia",
            start_time="11:15", end_time="12:15", duration_min=60,
        ),
    ]
    out = svc._retarget_all_legs_to_prev_stop(items, day_num=2)
    trans = [x for x in out if getattr(x, "type", None) == ItemType.TRANSIT]
    assert trans
    assert trans[0].from_location == "Movie Gate"


def test_fix269_leading_gap_is_a_hole():
    svc = _svc()
    items = [
        SimpleNamespace(
            type=ItemType.ATTRACTION,
            name="GoJump",
            start_time="12:00",
            end_time="13:00",
        )
    ]
    holes = svc._find_day_holes(items, 21 * 60, 9 * 60, min_span=10)
    assert holes
    assert holes[0][0] == 9 * 60
    assert holes[0][1] == 12 * 60


def test_fix269_clamp_drops_past_day_end():
    svc = _svc()
    items = [
        SimpleNamespace(
            type=ItemType.FREE_TIME,
            start_time="19:10",
            end_time="19:50",
            duration_min=40,
            name="bufor",
            model_copy=lambda update: SimpleNamespace(
                type=ItemType.FREE_TIME,
                start_time=update.get("start_time", "19:10"),
                end_time=update.get("end_time", "19:50"),
                duration_min=update.get("duration_min", 40),
            ),
        )
    ]
    out = svc._clamp_timeline_to_day_end(
        items, {"day_end": "19:00"}, day_num=1,
    )
    assert not any(
        getattr(x, "end_time", None) and str(x.end_time) > "19:00"
        for x in out
    )


def test_fix269_abutting_lunch_gets_transit():
    svc = _svc()
    lunch = LunchBreakItem(
        type=ItemType.LUNCH_BREAK,
        start_time="12:40",
        end_time="13:10",
        duration_min=30,
        suggestions=[
            RestaurantSuggestion(
                id="r1",
                name="VaffaNapoli",
                lat=51.1070,
                lng=17.0320,
            )
        ],
    )
    katedra = _attr("Katedra Wrocławska", "13:10", "14:19", 51.1144, 17.0465)
    coords = {
        "VaffaNapoli": {"lat": 51.1070, "lng": 17.0320, "name": "VaffaNapoli"},
        "Katedra Wrocławska": {
            "lat": 51.1144, "lng": 17.0465, "name": "Katedra Wrocławska",
        },
    }
    out = svc._ensure_stop_to_stop_legs(
        [lunch, katedra], coords,
        {"has_car": True, "transport_modes": ["car"], "trip_type": "city_tourism"},
        day_num=3, min_km=0.08,
    )
    trans = [x for x in out if getattr(x, "type", None) == ItemType.TRANSIT]
    assert trans, "abutting lunch → attraction must show a transit"
    assert trans[0].from_location == "VaffaNapoli"
    assert "Katedra" in trans[0].to_location


def test_fix269_wojslawice_drive_not_15_min():
    b = {
        "name": "Arboretum Wojsławice",
        "lat": 50.725, "lng": 16.852, "city": "Niemcza",
    }
    a = {
        "name": "Rynek we Wrocławiu",
        "lat": 51.110, "lng": 17.032, "city": "Wrocław",
    }
    assert poi_geo_region_key(b) == "region_wojslawice"
    ctx = {
        "has_car": True,
        "transport_modes": ["car"],
        "trip_type": "city_tourism",
        "region_type": "city",
    }
    there = travel_time_minutes(a, b, ctx)
    back = travel_time_minutes(b, a, ctx)
    assert there >= 35
    assert back >= 35
    assert abs(there - back) <= 15


def test_fix269_centre_hop_stays_on_foot():
    a = {"name": "Rynek", "lat": 51.1100, "lng": 17.0300}
    b = {"name": "Hala Targowa", "lat": 51.1100, "lng": 17.0555}
    ctx = {
        "has_car": True,
        "transport_modes": ["car"],
        "trip_type": "city_tourism",
        "day_used_car": True,
    }
    assert get_transport_mode(a, b, ctx) == "walking"


def test_fix269_iluzja_denied_for_underground_adventure():
    poi = {"name": "Muzeum Świat Iluzji we Wrocławiu", "tags": []}
    user = {
        "target_group": "friends",
        "preferences": ["underground", "history_mystery", "museum_heritage"],
        "travel_style": "adventure",
    }
    assert should_deny_poi_for_profile(poi, user)


def test_fix269_hala_stulecia_denied_for_underground_adventure():
    poi = {"name": "Hala Stulecia", "tags": []}
    user = {
        "target_group": "friends",
        "preferences": ["underground", "history_mystery", "museum_heritage"],
        "travel_style": "adventure",
    }
    assert should_deny_poi_for_profile(poi, user)


def test_fix269_exact_name_cross_day_stripped():
    def _a(name: str):
        return SimpleNamespace(
            type=ItemType.ATTRACTION,
            name=name,
            start_time="10:00",
            end_time="11:00",
            duration_min=60,
            poi_id=None,
            lat=51.1,
            lng=17.0,
        )

    days = [
        SimpleNamespace(
            day=3, quality_badges=None, date=None, weekday=None,
            items=[_a("Muzeum Przyrodnicze we Wrocławiu")],
        ),
        SimpleNamespace(
            day=5, quality_badges=None, date=None, weekday=None,
            items=[_a("Muzeum Przyrodnicze we Wrocławiu"), _a("Hydropolis")],
        ),
    ]
    out = _svc()._strip_cross_day_trip_repeats(days)
    d5 = [getattr(it, "name", "") for it in (out[1].items or [])]
    assert not any("przyrodnicze" in n.lower() for n in d5)
    assert any("Hydropolis" in n for n in d5)
