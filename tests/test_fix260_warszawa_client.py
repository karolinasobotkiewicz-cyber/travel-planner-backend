"""FIX #260 — Warszawa retest: geometry, durations, copy, prefs, labels."""
from __future__ import annotations

from types import SimpleNamespace

from app.domain.planner.engine import visit_duration_hard_cap, choose_duration
from app.domain.planner.explainability import explain_poi_selection
from app.domain.planner.poi_copy import build_fallback_copy
from app.domain.scoring.profile_poi_rules import (
    poi_trip_repeat_key,
    profile_poi_score_delta,
)
from app.infrastructure.repositories.normalizer import normalize_poi


def test_fix260_zoo_hard_cap_above_park_90():
    assert visit_duration_hard_cap(
        {"name": "Ogród Zoologiczny w Warszawie"}, for_scheduling=True,
    ) == 150


def test_fix260_pkin_hard_cap_120():
    assert visit_duration_hard_cap(
        {"name": "Pałac Kultury i Nauki"}, for_scheduling=True,
    ) == 120


def test_fix260_ujazdowski_cap_90():
    assert visit_duration_hard_cap(
        {"name": "Zamek Ujazdowski"}, for_scheduling=True,
    ) == 90


def test_fix260_zoo_named_min_120():
    now = 10 * 60
    end = 18 * 60
    dur = choose_duration(
        {"name": "Ogród Zoologiczny w Warszawie", "time_min": 60, "time_max": 180},
        now, end, False, user={"target_group": "family_kids"},
    )
    assert dur >= 120


def test_fix260_seniors_lazienki_floor():
    now = 10 * 60
    end = 18 * 60
    dur = choose_duration(
        {"name": "Łazienki Królewskie", "time_min": 45, "time_max": 120},
        now, end, False, user={"target_group": "seniors"},
    )
    assert dur >= 90


def test_fix260_browary_no_koszyki_tip():
    desc, tip = build_fallback_copy({
        "name": "Browary Warszawskie",
        "city": "Warszawa",
        "description_short": "x",
        "pro_tip": "Porównaj z Halą Koszyki.",
    })
    blob = f"{desc} {tip}".lower()
    assert "koszyki" not in blob
    assert "browary" in desc.lower()


def test_fix260_browary_normalizer_no_koszyki():
    poi = normalize_poi({
        "name": "Browary Warszawskie",
        "city": "Warszawa",
        "description_short": "old",
        "pro_tip": "Idź do Hali Koszyki",
        "lat": 52.23,
        "lng": 20.98,
    }, 0)
    blob = f"{poi.get('description_short')} {poi.get('description_long')} {poi.get('pro_tip')}".lower()
    assert "koszyki" not in blob


def test_fix260_kampinos_must_see_label():
    reasons = explain_poi_selection(
        {"name": "Kampinoski Park Narodowy", "priority_level": 12, "city": "Warszawa"},
        {"requested_city": "Warszawa"},
        {"target_group": "couples", "preferences": ["nature_landscape"]},
    )
    joined = " ".join(reasons).lower()
    assert "kampinos" in joined
    assert "warszawie" not in joined or "izabelin" in joined


def test_fix260_garden_repeat_keys():
    assert poi_trip_repeat_key("Ogród Krasińskich") == "waw_ogrod_krasinskich"
    assert poi_trip_repeat_key("Ogród Botaniczny UW") == "waw_ogrod_botaniczny"
    assert poi_trip_repeat_key("Kampinoski Park Narodowy") == "waw_kampinos"


def test_fix260_park_linowy_demoted_for_cultural_relax_food():
    delta = profile_poi_score_delta(
        {"name": "Park Linowy Warszawa"},
        {
            "target_group": "couples",
            "preferences": [
                "cultural", "museum_heritage", "relaxation", "local_food_experience",
            ],
            "travel_style": "cultural",
        },
        context={},
    )
    assert delta <= -150


def test_fix260_kampinos_demoted_for_underground_history():
    delta = profile_poi_score_delta(
        {"name": "Kampinoski Park Narodowy"},
        {
            "target_group": "friends",
            "preferences": ["underground", "history_mystery", "museum_heritage"],
            "travel_style": "cultural",
        },
        context={},
    )
    assert delta <= -150


def test_fix260_geometry_rebuild_on_endpoint_mismatch():
    from pathlib import Path

    from app.application.services.plan_service import PlanService
    from app.domain.models.plan import ItemType, TransitMode
    from app.infrastructure.repositories import POIRepository

    svc = PlanService(POIRepository(str(Path("data") / "multi_city_attractions.xlsx")))
    # Stale geometry starts at Botaniczny coords while from says Bulwary.
    it = SimpleNamespace(
        type=ItemType.TRANSIT,
        mode=TransitMode.WALK,
        from_location="Bulwary Wiślane",
        to_location="Stary Dom",
        routing_source="estimated_walk",
        geometry=[[21.02, 52.24], [21.01, 52.25]],  # wrong start
        geometry_latlng=[[52.24, 21.02], [52.25, 21.01]],
    )
    cmap = {
        "Bulwary Wiślane": {"name": "Bulwary Wiślane", "lat": 52.247, "lng": 21.028},
        "Stary Dom": {"name": "Stary Dom", "lat": 52.250, "lng": 21.012},
    }
    out = svc._normalize_transit_routing_item(it, cmap, {"has_car": False})
    g0 = out.geometry[0]
    assert abs(float(g0[0]) - 21.028) < 0.001
    assert abs(float(g0[1]) - 52.247) < 0.001


def test_fix260_strip_self_transit():
    from pathlib import Path

    from app.application.services.plan_service import PlanService
    from app.domain.models.plan import ItemType, TransitMode
    from app.infrastructure.repositories import POIRepository

    svc = PlanService(POIRepository(str(Path("data") / "multi_city_attractions.xlsx")))
    items = [
        SimpleNamespace(
            type=ItemType.TRANSIT,
            mode=TransitMode.CAR,
            from_location="Kampinoski Park Narodowy",
            to_location="Kampinoski Park Narodowy",
            start_time="12:00",
            end_time="12:56",
            duration_min=56,
        ),
        SimpleNamespace(
            type=ItemType.ATTRACTION,
            name="Park Linowy",
            start_time="13:00",
            end_time="14:00",
        ),
    ]
    out = svc._strip_self_transits(items, day_num=2)
    assert all(getattr(it, "type", None) != ItemType.TRANSIT for it in out)


def test_fix260_meal_placeholder_transit_not_stripped():
    from pathlib import Path

    from app.application.services.plan_service import PlanService
    from app.domain.models.plan import ItemType, TransitMode
    from app.infrastructure.repositories import POIRepository

    svc = PlanService(POIRepository(str(Path("data") / "multi_city_attractions.xlsx")))
    items = [
        SimpleNamespace(
            type=ItemType.ATTRACTION,
            name="Park Linowy",
            start_time="16:00",
            end_time="17:00",
        ),
        SimpleNamespace(
            type=ItemType.TRANSIT,
            mode=TransitMode.CAR,
            from_location="Park Linowy",
            to_location="Restauracja (kolacja)",
            start_time="17:00",
            end_time="17:20",
            duration_min=20,
        ),
        SimpleNamespace(
            type=ItemType.DINNER_BREAK,
            name="Kolacja",
            start_time="17:30",
            end_time="18:30",
            suggestions=[],
        ),
    ]
    out = svc._strip_transits_to_unscheduled_destinations(items, day_num=1)
    assert any(
        getattr(it, "type", None) == ItemType.TRANSIT
        and "kolacja" in (getattr(it, "to_location", "") or "").lower()
        for it in out
    )


def test_fix260_daytrip_travel_floor_kampinos():
    from app.domain.planner.engine import travel_time_minutes

    city = {"name": "Warszawa", "lat": 52.2297, "lng": 21.0122, "city": "Warszawa"}
    kampinos = {
        "name": "Kampinoski Park Narodowy",
        "lat": 52.3167,
        "lng": 20.6167,
        "city": "Izabelin",
    }
    mins = travel_time_minutes(
        city, kampinos, {"has_car": True, "requested_city": "Warszawa"},
    )
    assert mins >= 35


def test_fix260_local_food_boosts_wedel():
    delta = profile_poi_score_delta(
        {"name": "Pijalnia Czekolady E. Wedel"},
        {
            "target_group": "couples",
            "preferences": ["local_food_experience", "relaxation"],
            "travel_style": "relax",
        },
        context={},
    )
    assert delta >= 100
