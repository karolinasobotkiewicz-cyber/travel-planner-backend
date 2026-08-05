"""FIX #254 — client feedback (Wrocław/Kraków/Warszawa/Katowice/Poznań).

Unit guards for cross-cutting bugs: ratings /5, Must-see locative, short-hop
walk, car+estimated_walk consistency, visit caps, seasonality, copy overrides.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from app.application.services.plan_service import PlanService
from app.domain.filters.seasonality import filter_by_season
from app.domain.models.plan import ItemType, TransitMode
from app.domain.planner.city_copy import city_locative_pl
from app.domain.planner.engine import get_transport_mode, visit_duration_hard_cap
from app.domain.planner.explainability import explain_poi_selection
from app.domain.planner.poi_copy import build_fallback_copy, classify_poi_category
from app.domain.scoring.profile_poi_rules import should_deny_poi_for_profile
from app.infrastructure.repositories.normalizer import normalize_poi


def test_city_locative_pl_major_cities():
    assert city_locative_pl("Wrocław") == "we Wrocławiu"
    assert city_locative_pl("Kraków") == "w Krakowie"
    assert city_locative_pl("Warszawa") == "w Warszawie"
    assert city_locative_pl("Katowice") == "w Katowicach"
    assert city_locative_pl("Poznań") == "w Poznaniu"


def test_must_see_uses_locative_not_nominative():
    poi = {
        "name": "Hala Stulecia",
        "city": "Wrocław",
        "priority_level": 12,
        "must_see": 12,
        "popularity_score": 9.0,
        "tags": ["museum_heritage"],
    }
    why = " ".join(
        explain_poi_selection(poi, {"city": "Wrocław"}, {"target_group": "couples"})
    )
    assert "Must-see we Wrocławiu" in why
    assert "Must-see w Wrocław" not in why


def test_rating_never_exceeds_5_stars():
    poi = {
        "name": "Test POI",
        "city": "Kraków",
        "priority_level": 8,
        "must_see": 8,
        "popularity_score": 9.0,
        "tags": [],
    }
    why = " ".join(
        explain_poi_selection(poi, {"city": "Kraków"}, {"target_group": "couples"})
    )
    assert "9.0/5" not in why
    assert "8.0/5" not in why
    assert "10.0/5" not in why
    if "/5" in why:
        import re
        for m in re.findall(r"(\d+\.\d+)/5", why):
            assert float(m) <= 5.0


def test_city_tourism_short_hop_is_walk():
    a = {"lat": 50.061, "lng": 19.937}
    b = {"lat": 50.062, "lng": 19.938}  # ~150 m
    ctx = {
        "has_car": True,
        "transport_modes": ["car", "walking"],
        "trip_type": "city_tourism",
        "signals": {"cluster_type": "standalone_city"},
        "region_type": "city",
        "requested_city": "Kraków",
    }
    assert get_transport_mode(a, b, ctx) == "walking"


def test_visit_caps_sky_tower_and_cathedral():
    assert visit_duration_hard_cap({"name": "Punkt widokowy Sky Tower"}) == 60
    assert visit_duration_hard_cap({"name": "Katedra Wrocławska"}) == 90
    assert visit_duration_hard_cap({"name": "Park Wilsona"}) == 60
    assert visit_duration_hard_cap({"name": "Laser Tag Wrocław"}) == 120


def test_city_golf_always_denied():
    assert should_deny_poi_for_profile(
        {"name": "City Golf Wrocław"},
        {"target_group": "couples", "preferences": ["relaxation"], "travel_style": "relax"},
    )


def test_adventure_denies_wyspa_pergola():
    user = {
        "target_group": "friends",
        "preferences": ["adventure"],
        "travel_style": "adventure",
    }
    assert should_deny_poi_for_profile({"name": "Wyspa Słodowa"}, user)
    assert should_deny_poi_for_profile({"name": "Pergola"}, user)


def test_winter_seasonality_drops_wyspa_keeps_park_and_pergola():
    pois = [
        {
            "name": "Wyspa Słodowa",
            "season_fit": {"winter": 0, "spring": 1, "summer": 1, "autumn": 1},
        },
        {
            "name": "Pergola",
            "season_fit": {"winter": 0, "spring": 1, "summer": 1, "autumn": 1},
        },
        {
            "name": "Park Szczytnicki",
            "season_fit": {"winter": 0, "spring": 1, "summer": 1, "autumn": 1},
        },
    ]
    out = filter_by_season(pois, date(2026, 2, 10))
    names = {p["name"] for p in out}
    assert "Wyspa Słodowa" not in names
    assert "Pergola" in names
    assert "Park Szczytnicki" in names


def test_obwarzanka_not_bagels():
    desc, tip = build_fallback_copy({
        "name": "Muzeum Obwarzanka",
        "city": "Kraków",
        "description_short": "Historia bajgli w Krakowie",
        "pro_tip": "Spróbuj bajgla",
    })
    assert "bajgl" not in desc.lower()
    assert "obwarzank" in desc.lower()


def test_skalki_not_climbing_category():
    assert classify_poi_category({
        "name": "Skałki Twardowskiego",
        "tags_excel": "climbing rope park",
        "type_of_attraction": "park",
    }) == "park"


def test_plac_not_playground_category():
    assert classify_poi_category({
        "name": "Plac Bohaterów Getta",
        "tags": ["plac", "kids"],
    }) != "playground"


def test_wedel_katowice_copy_not_warsaw():
    poi = normalize_poi({
        "Name": "Pijalnia Czekolady E. Wedel",
        "City": "Katowice",
        "Description_short": "stary opis",
        "Must see score": 5,
        "priority_level": "secondary",
    }, 0)
    blob = f"{poi.get('description_short', '')} {poi.get('description_long', '')}"
    assert "Warszawie" not in blob
    assert "Katowic" in blob


def test_transport_consistency_keeps_short_walk_and_fixes_source():
    from app.domain.models.plan import TransitItem
    from app.domain.planner.time_utils import time_to_minutes

    def _tr(frm, to, start, end, mode, dist, src):
        return TransitItem(
            type=ItemType.TRANSIT,
            from_location=frm,
            to_location=to,
            start_time=start,
            end_time=end,
            duration_min=time_to_minutes(end) - time_to_minutes(start),
            mode=mode,
            distance_km=dist,
            routing_source=src,
        )

    svc = PlanService(MagicMock())
    items = [
        _tr("A", "B", "10:00", "10:20", TransitMode.CAR, 5.0, "estimated_road"),
        _tr("B", "C", "11:00", "11:08", TransitMode.WALK, 0.35, "estimated_walk"),
        _tr("C", "D", "12:00", "12:15", TransitMode.WALK, 2.2, "estimated_walk"),
    ]
    out = svc._enforce_day_transport_consistency(
        items, {"transport_modes": ["car"]}, {"has_car": True, "trip_type": "city_tourism"},
        day_num=1,
    )
    short = next(i for i in out if getattr(i, "to_location", None) == "C")
    long = next(i for i in out if getattr(i, "to_location", None) == "D")
    assert short.mode == TransitMode.WALK
    assert long.mode == TransitMode.CAR
    assert getattr(long, "routing_source", None) == "estimated_road"


def test_playground_why_not_for_couples():
    poi = {
        "name": "Park Jordana",
        "city": "Kraków",
        "priority_level": 8,
        "must_see": 7,
        "popularity_score": 8.0,
        "tags_excel": "park playground kids",
        "type_of_attraction": "park",
    }
    why = " ".join(
        explain_poi_selection(
            poi,
            {"city": "Kraków"},
            {"target_group": "couples", "travel_style": "cultural"},
        )
    )
    assert "Bezpieczna strefa zabaw" not in why
