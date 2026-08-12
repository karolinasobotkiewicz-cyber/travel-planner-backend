"""FIX #265 — Wrocław client retest: overlaps, Mamuta, dates, far POI, meals."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from app.application.services.plan_service import PlanService, _apply_day_dates
from app.domain.models.plan import DayPlan, ItemType, TransitItem, TransitMode
from app.domain.planner.engine import travel_time_minutes
from app.domain.planner.poi_copy import build_fallback_copy, classify_poi_category
from app.domain.scoring.family_fit import (
    is_child_oriented_attraction,
    restaurant_hard_denied_for_group,
    should_exclude_by_target_group,
)
from app.domain.scoring.preference_coverage import poi_covers_preference_report
from app.domain.scoring.profile_poi_rules import (
    poi_trip_repeat_key,
    should_deny_poi_for_profile,
)
from app.infrastructure.repositories import POIRepository
from app.infrastructure.repositories.normalizer import normalize_poi


def _svc() -> PlanService:
    return PlanService(POIRepository(str(Path("data") / "multi_city_attractions.xlsx")))


def test_fix265_day_dates_survive_rebuild():
    days = [
        DayPlan(day=1, title="D1", items=[]),
        DayPlan(day=2, title="D2", items=[]),
        DayPlan(day=3, title="D3", items=[]),
    ]
    _apply_day_dates(days, "2026-06-15")
    assert days[0].date == "2026-06-15"
    assert days[0].weekday == "poniedziałek"
    assert days[1].date == "2026-06-16"
    assert days[2].weekday == "środa"


def test_fix265_mamuta_is_child_oriented_and_denied_for_adults():
    poi = {"name": "Park Mamuta", "tags": ["dinosaur_theme"], "kids_only": False}
    assert is_child_oriented_attraction(poi)
    assert should_exclude_by_target_group(poi, {"target_group": "friends"})
    assert should_exclude_by_target_group(poi, {"target_group": "seniors"})
    assert should_exclude_by_target_group(poi, {"target_group": "solo"})
    assert should_deny_poi_for_profile(
        poi, {"target_group": "friends", "preferences": [], "travel_style": "adventure"},
    )
    assert not should_deny_poi_for_profile(
        poi, {"target_group": "family_kids", "preferences": ["kids_attractions"]},
    )


def test_fix265_mamuta_not_museum_heritage():
    poi = {
        "name": "Park Mamuta",
        "tags": ["dinosaur_theme", "multimedia_exhibition", "museum"],
        "city": "Wrocław",
    }
    assert not poi_covers_preference_report(poi, "museum_heritage")
    assert classify_poi_category(poi) == "playground"


def test_fix265_mamuta_free_tip_hard_override():
    desc, tip = build_fallback_copy(
        {
            "name": "Park Mamuta",
            "city": "Wrocław",
            "ticket_normal": 0,
            "pro_tip": "Kup bilet online z wyprzedzeniem.",
            "description_short": "Muzeum dinozaurów",
        }
    )
    assert "wolny" in desc.lower() or "darm" in (tip or "").lower() or "wolny" in (tip or "").lower()
    assert "bilet" not in (tip or "").lower()
    assert "kup" not in (tip or "").lower()


def test_fix265_mamuta_trip_repeat_key():
    assert poi_trip_repeat_key("Park Mamuta") == "wro_park_mamuta"


def test_fix265_barometre_denied_for_family():
    assert restaurant_hard_denied_for_group(
        {"name": "Le Barometre Bistro & Cocktail Bar", "target_groups": ["friends"]},
        {"target_group": "family_kids"},
    )


def test_fix265_iluzji_wroclaw_coords_forced():
    poi = normalize_poi(
        {
            "name": "Muzeum Świat Iluzji we Wrocławiu",
            "city": "Wrocław",
            "lat": 52.2297,
            "lng": 21.0122,
            "time_min": 60,
            "time_max": 90,
        },
        0,
    )
    assert abs(float(poi["lat"]) - 51.1069) < 0.01
    assert abs(float(poi["lng"]) - 17.0773) < 0.01


def test_fix265_force_iluzji_on_timeline():
    svc = _svc()
    it = SimpleNamespace(
        type=ItemType.ATTRACTION,
        name="Muzeum Świat Iluzji we Wrocławiu",
        lat=52.23,
        lng=21.01,
        model_copy=lambda update: SimpleNamespace(
            type=ItemType.ATTRACTION,
            name="Muzeum Świat Iluzji we Wrocławiu",
            lat=update["lat"],
            lng=update["lng"],
        ),
    )
    out = svc._force_known_good_poi_coords([it], day_num=7)
    assert abs(float(out[0].lat) - 51.1069) < 0.01


def test_fix265_short_walk_not_inflated():
    mins = travel_time_minutes(
        {"lat": 51.1100, "lng": 17.0300},
        {"lat": 51.1105, "lng": 17.0305},  # ~83 m
        {"has_car": True, "transport_modes": ["car"], "requested_city": "Wrocław"},
    )
    assert mins <= 5


def test_fix265_micro_walk_clamped_by_implausible_fix():
    svc = _svc()
    it = TransitItem(
        type=ItemType.TRANSIT,
        mode=TransitMode.WALK,
        from_location="A",
        to_location="B",
        start_time="12:00",
        end_time="12:15",
        duration_min=15,
        distance_km=0.08,
        routing_source="estimated_walk",
    )
    cmap = {
        "A": {"name": "A", "lat": 51.1100, "lng": 17.0300},
        "B": {"name": "B", "lat": 51.1105, "lng": 17.0305},
    }
    out = svc._fix_implausible_transit_duration(
        it, cmap, {"has_car": True, "requested_city": "Wrocław"},
    )
    assert int(out.duration_min) <= 5


def test_fix265_overlap_healed_after_implausible_stretch():
    """Ensure absolute-last overlap heal: transit must not overrun attraction."""
    from app.domain.models.plan import AttractionItem, ParkingInfo, TicketInfo
    from app.domain.planner.time_utils import time_to_minutes

    svc = _svc()
    items = [
        TransitItem(
            type=ItemType.TRANSIT,
            mode=TransitMode.WALK,
            from_location="X",
            to_location="Ogród Japoński",
            start_time="10:00",
            end_time="10:20",
            duration_min=20,
            distance_km=0.5,
            routing_source="estimated_walk",
        ),
        AttractionItem(
            type=ItemType.ATTRACTION,
            poi_id="oj1",
            name="Ogród Japoński",
            start_time="10:16",
            end_time="11:16",
            duration_min=60,
            description_short="Ogród",
            lat=51.11,
            lng=17.08,
            address="Wrocław",
            cost_estimate=0,
            ticket_info=TicketInfo(ticket_normal=0, ticket_reduced=0),
            parking=ParkingInfo(name="street", walk_time_min=0),
        ),
    ]
    out = svc._remove_timeline_overlaps(items, day_num=1)
    tr = next(
        x for x in out
        if str(getattr(getattr(x, "type", None), "value", getattr(x, "type", None)))
        == ItemType.TRANSIT.value
    )
    attr = next(x for x in out if "Japoński" in (getattr(x, "name", "") or ""))
    assert time_to_minutes(tr.end_time) <= time_to_minutes(attr.start_time)
