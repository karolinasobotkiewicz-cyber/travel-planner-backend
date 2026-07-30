"""FIX #251 — client quality: transit realism, copy PL, budget, closed POIs."""
from __future__ import annotations

from app.application.services.plan_service import PlanService
from app.domain.planner.explainability import explain_poi_selection
from app.domain.models.plan import ItemType, TransitItem, TransitMode
from app.domain.planner.engine import haversine_distance


def test_why_selected_is_polish():
    reasons = explain_poi_selection(
        {
            "name": "Muzeum Test",
            "city": "Kraków",
            "priority_level": "core",
            "tags": ["museum_heritage"],
            "crowd_level": 1,
            "cena_bilet_normalny": 20,
        },
        {"city": "Kraków", "season": "summer"},
        {
            "preferences": ["museum_heritage"],
            "target_group": "couples",
            "travel_style": "cultural",
            "crowd_tolerance": 2,
            "budget_level": 2,
        },
    )
    assert reasons
    blob = " ".join(reasons).lower()
    assert "matches your" not in blob
    assert any(
        tok in blob
        for tok in ("pasuje", "must-see", "polecane", "doświadczenie", "idealne", "preferencji")
    )


def test_fallback_attraction_copy_not_empty():
    svc = PlanService.__new__(PlanService)
    desc, tip = svc._fallback_attraction_copy(
        {"name": "Park Testowy", "city": "Wrocław", "tags": ["park", "nature"], "description_short": ""}
    )
    assert desc
    assert tip
    assert "Park Testowy" in desc


def test_fix_implausible_transit_6km_5min():
    svc = PlanService.__new__(PlanService)
    lat1, lng1 = 51.1, 17.0
    lat2, lng2 = 51.14, 17.05
    dist = haversine_distance(lat1, lng1, lat2, lng2)
    assert dist >= 4.0
    coord_map = {
        "A": {"name": "A", "lat": lat1, "lng": lng1},
        "B": {"name": "B", "lat": lat2, "lng": lng2},
    }
    it = TransitItem(
        type=ItemType.TRANSIT,
        start_time="10:00",
        end_time="10:05",
        duration_min=5,
        mode=TransitMode.CAR,
        from_location="A",
        to_location="B",
    )
    fixed = svc._fix_implausible_transit_duration(it, coord_map, {"has_car": True})
    assert int(fixed.duration_min) >= 12, (
        f"expected realistic duration, got {fixed.duration_min} for {dist:.1f}km"
    )
