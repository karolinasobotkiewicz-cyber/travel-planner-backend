"""FIX #261 — Wrocław retest: day-1 ban, coverage, caps, GoJump copy, self-transit."""
from __future__ import annotations

from types import SimpleNamespace

from app.domain.planner.engine import choose_duration, visit_duration_hard_cap
from app.domain.planner.poi_copy import build_fallback_copy
from app.domain.scoring.preference_coverage import (
    poi_covers_preference_report,
    preference_coverage_adequate,
)
from app.infrastructure.repositories.normalizer import normalize_poi


def test_fix261_most_grunwaldzki_cap_25():
    assert visit_duration_hard_cap(
        {"name": "Most Grunwaldzki"}, for_scheduling=True,
    ) == 25


def test_fix261_dworzec_cap_60():
    assert visit_duration_hard_cap(
        {"name": "Dworzec Świebodzki"}, for_scheduling=True,
    ) == 60


def test_fix261_sky_tower_named_min_45():
    dur = choose_duration(
        {"name": "Sky Tower", "time_min": 20, "time_max": 60},
        10 * 60, 18 * 60, False,
        user={"target_group": "couples"},
    )
    assert dur >= 45


def test_fix261_pergola_covers_nature_and_relax():
    poi = {"name": "Pergola przy Hali Stulecia", "city": "Wrocław", "tags": []}
    assert poi_covers_preference_report(poi, "nature_landscape")
    assert poi_covers_preference_report(poi, "relaxation")
    assert preference_coverage_adequate("nature_landscape", [poi])
    assert preference_coverage_adequate("relaxation", [poi])


def test_fix261_gojump_copy_not_krakow_for_wroclaw():
    desc, tip = build_fallback_copy({
        "name": "GoJump Wrocław",
        "city": "Wrocław",
        "description_short": "park trampolin w Krakowie",
        "pro_tip": "Idź do GoJump w Krakowie.",
    })
    blob = f"{desc} {tip}".lower()
    assert "krakowie" not in blob
    assert "wrocław" in blob or "wroclaw" in blob


def test_fix261_normalizer_relocates_krakow_mention():
    poi = normalize_poi({
        "name": "GoJump",
        "city": "Wrocław",
        "description_short": "Park trampolin w Krakowie dla całej rodziny.",
        "pro_tip": "Kup bilet w Krakowie.",
        "lat": 51.1,
        "lng": 17.0,
    }, 0)
    blob = f"{poi.get('description_short')} {poi.get('pro_tip')}".lower()
    assert "krakowie" not in blob
    assert "wrocławiu" in blob


def test_fix261_strip_rynek_alias_self_transit():
    from pathlib import Path

    from app.application.services.plan_service import PlanService
    from app.domain.models.plan import ItemType, TransitMode
    from app.infrastructure.repositories import POIRepository

    svc = PlanService(POIRepository(str(Path("data") / "multi_city_attractions.xlsx")))
    items = [
        SimpleNamespace(
            type=ItemType.TRANSIT,
            mode=TransitMode.WALK,
            from_location="Rynek",
            to_location="Rynek we Wrocławiu",
            start_time="12:00",
            end_time="12:10",
            duration_min=10,
        ),
        SimpleNamespace(
            type=ItemType.ATTRACTION,
            name="Hydropolis",
            start_time="12:20",
            end_time="13:20",
        ),
    ]
    out = svc._strip_self_transits(items, day_num=3)
    assert all(getattr(it, "type", None) != ItemType.TRANSIT for it in out)


def test_fix261_strip_keeps_distinct_most_legs():
    from pathlib import Path

    from app.application.services.plan_service import PlanService
    from app.domain.models.plan import ItemType, TransitMode
    from app.infrastructure.repositories import POIRepository

    svc = PlanService(POIRepository(str(Path("data") / "multi_city_attractions.xlsx")))
    items = [
        SimpleNamespace(
            type=ItemType.TRANSIT,
            mode=TransitMode.WALK,
            from_location="Most Tumski",
            to_location="Most Grunwaldzki",
            start_time="12:00",
            end_time="12:15",
            duration_min=15,
        ),
    ]
    out = svc._strip_self_transits(items, day_num=1)
    assert len(out) == 1
