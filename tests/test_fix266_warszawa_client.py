"""FIX #266 — Warszawa client retest: foreign POI, underground, caps, densify."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.application.services.plan_service import PlanService
from app.domain.models.plan import ItemType, TransitItem, TransitMode
from app.domain.planner.engine import visit_duration_hard_cap
from app.domain.planner.time_utils import minutes_to_time
from app.domain.scoring.preference_coverage import poi_covers_preference_report
from app.domain.scoring.profile_poi_rules import (
    poi_trip_repeat_key,
    should_deny_poi_for_profile,
)
from app.infrastructure.repositories import POIRepository


def _svc() -> PlanService:
    return PlanService(POIRepository(str(Path("data") / "multi_city_attractions.xlsx")))


def test_fix266_minutes_to_time_clamps_past_midnight():
    assert minutes_to_time(24 * 60 + 7) == "23:59"
    assert minutes_to_time(-5) == "00:00"


def test_fix266_powstania_not_underground_coverage():
    assert not poi_covers_preference_report(
        {"name": "Muzeum Powstania Warszawskiego", "tags": ["ww2_history"]},
        "underground",
    )
    assert not poi_covers_preference_report(
        {"name": "Kopiec Powstania Warszawskiego", "tags": ["viewpoint"]},
        "underground",
    )


def test_fix266_cytadela_still_underground():
    assert poi_covers_preference_report(
        {"name": "Cytadela Warszawska", "tags": ["fortress"]},
        "underground",
    )


def test_fix266_zamek_krolewski_is_museum_heritage():
    assert poi_covers_preference_report(
        {"name": "Zamek Królewski", "tags": ["historic_building"]},
        "museum_heritage",
    )


def test_fix266_norblin_not_local_food():
    assert not poi_covers_preference_report(
        {"name": "Muzeum Fabryki Norblina", "tags": ["museum", "local_food"]},
        "local_food_experience",
    )


def test_fix266_powazki_cap_120():
    assert visit_duration_hard_cap(
        {"name": "Cmentarz Powązkowski"}, for_scheduling=True,
    ) == 120


def test_fix266_bazylika_cap_45():
    assert visit_duration_hard_cap(
        {"name": "Bazylika Archikatedralna św. Jana Chrzciciela"},
        for_scheduling=True,
    ) == 45


def test_fix266_warszawianka_denied_for_relax_solo():
    poi = {"name": "Park Wodny Warszawianka", "tags": ["aquapark"]}
    assert should_deny_poi_for_profile(
        poi,
        {
            "target_group": "solo",
            "preferences": ["nature_landscape", "relaxation"],
            "travel_style": "relax",
        },
    )
    assert poi_trip_repeat_key("Park Wodny Warszawianka") == "waw_warszawianka"


def test_fix266_strip_foreign_transit_and_poi():
    svc = _svc()
    items = [
        SimpleNamespace(
            type=ItemType.ATTRACTION,
            name="Muzeum Świat Iluzji we Wrocławiu",
            start_time="10:00",
            end_time="11:00",
            duration_min=60,
        ),
        TransitItem(
            type=ItemType.TRANSIT,
            start_time="11:00",
            end_time="11:20",
            duration_min=20,
            mode=TransitMode.CAR,
            from_location="Muzeum Świat Iluzji we Wrocławiu",
            to_location="Zamek Królewski",
        ),
        SimpleNamespace(
            type=ItemType.ATTRACTION,
            name="Zamek Królewski",
            start_time="11:20",
            end_time="12:20",
            duration_min=60,
        ),
    ]
    out = svc._strip_wrong_city_attractions(
        items, {"requested_city": "Warszawa"}, day_num=1,
    )
    names = [getattr(it, "name", None) or getattr(it, "to_location", None) for it in out]
    assert not any(n and "wrocław" in n.lower() for n in names if isinstance(n, str))
    assert any(getattr(it, "name", "") == "Zamek Królewski" for it in out)


def test_fix266_clamp_absurd_overnight_transit():
    svc = _svc()
    it = TransitItem(
        type=ItemType.TRANSIT,
        start_time="00:00",
        end_time="09:15",
        duration_min=555,
        mode=TransitMode.CAR,
        from_location="Bar Mleczny Lindleya",
        to_location="Park Linowy Warszawa",
        distance_km=1.2,
    )
    coord_map = {
        "Bar Mleczny Lindleya": {"lat": 52.22, "lng": 21.00, "name": "Bar Mleczny Lindleya"},
        "Park Linowy Warszawa": {"lat": 52.23, "lng": 21.01, "name": "Park Linowy Warszawa"},
    }
    out = svc._clamp_absurd_transit_durations(
        [it],
        coord_map,
        {"requested_city": "Warszawa", "day_start": "09:00", "has_car": True},
        day_num=1,
    )
    assert out == [] or (
        out
        and int(getattr(out[0], "duration_min", 0) or 0) <= 120
        and str(getattr(out[0], "start_time", "")) >= "09:00"
    )
