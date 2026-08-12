"""FIX #268 — Wrocław client retest: trip dupes, aquapark floor, TOD, addresses."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.application.services.plan_service import PlanService
from app.domain.models.plan import ItemType
from app.domain.planner.engine import (
    is_evening_only_poi,
    is_morning_preferred_poi,
    visit_duration_hard_cap,
    choose_duration,
)
from app.domain.planner.explainability import explain_poi_selection
from app.domain.scoring.profile_poi_rules import (
    poi_trip_repeat_key,
    should_deny_poi_for_profile,
)
from app.infrastructure.repositories import POIRepository


def _svc() -> PlanService:
    return PlanService(POIRepository(str(Path("data") / "multi_city_attractions.xlsx")))


def test_fix268_wro_icon_trip_repeat_keys():
    assert poi_trip_repeat_key("Muzeum Świat Iluzji we Wrocławiu") == "wro_swiat_iluzji"
    assert poi_trip_repeat_key("Aquapark Wrocław") == "wro_aquapark"
    assert poi_trip_repeat_key("Muzeum Motoryzacji i Techniki Zamek Topacz") == "wro_topacz"
    assert poi_trip_repeat_key("Katedra Wrocławska") == "wro_katedra"
    assert poi_trip_repeat_key("Panorama Racławicka") == "wro_panorama"


def test_fix268_cross_day_iluzja_stripped():
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
            items=[_attr("Muzeum Świat Iluzji we Wrocławiu")],
        ),
        SimpleNamespace(
            day=2, quality_badges=None, date=None, weekday=None,
            items=[
                _attr("Muzeum Świat Iluzji we Wrocławiu"),
                _attr("Hydropolis"),
            ],
        ),
    ]
    out = _svc()._strip_cross_day_trip_repeats(days)
    d2 = [getattr(it, "name", "") for it in (out[1].items or [])]
    assert not any("iluzji" in n.lower() for n in d2)
    assert any("Hydropolis" in n for n in d2)


def test_fix268_aquapark_floor_and_cap():
    assert choose_duration(
        {"name": "Aquapark Wrocław", "time_min": 45, "time_max": 180},
        10 * 60, 20 * 60, True, {},
    ) >= 120
    assert visit_duration_hard_cap({"name": "Aquapark Wrocław"}) == 180


def test_fix268_hala_morning_zatoka_evening():
    assert is_morning_preferred_poi({"name": "Hala Targowa"})
    assert is_evening_only_poi({"name": "Zatoka Gondoli"})


def test_fix268_iluzja_denied_for_seniors():
    assert should_deny_poi_for_profile(
        {"name": "Muzeum Świat Iluzji we Wrocławiu", "tags": []},
        {
            "target_group": "seniors",
            "preferences": ["museum_heritage", "nature_landscape", "relaxation"],
            "travel_style": "relax",
        },
    )


def test_fix268_pixel_xl_not_kids_why():
    reasons = explain_poi_selection(
        {"name": "Pixel XL Wrocław", "tags": ["family", "entertainment"], "type": "attraction"},
        {"requested_city": "Wrocław"},
        {
            "target_group": "family_kids",
            "preferences": ["kids_attractions"],
            "travel_style": "balanced",
        },
    )
    blob = " ".join(reasons or []).lower()
    assert "rodzin" not in blob
    assert "najmłod" not in blob


def test_fix268_bastion_cap_short():
    assert visit_duration_hard_cap({"name": "Bastion Sakwowy"}) == 45


def test_fix268_absurd_road_km_without_coords():
    from app.domain.models.plan import TransitItem, TransitMode

    svc = _svc()
    it = TransitItem(
        type=ItemType.TRANSIT,
        mode=TransitMode.CAR,
        from_location="Wrocław",
        to_location="Muzeum Motoryzacji Wena",
        start_time="09:30",
        end_time="09:40",
        duration_min=10,
        distance_km=39.941,
        routing_source="estimated_road",
    )
    out = svc._fix_implausible_transit_duration(it, {}, {"has_car": True})
    assert int(out.duration_min) >= 90
