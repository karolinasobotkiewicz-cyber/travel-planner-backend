"""FIX #255 — client feedback (Kraków/Wrocław/Warszawa/Katowice/Poznań).

Unit guards: indoor maze copy, visit caps, seasonality, denials, meal geo,
LEGO cluster, short-hop walk with context, leading-lunch reorder.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from app.application.services.plan_service import (
    PlanService,
    _reorder_leading_lunch,
)
from app.domain.filters.seasonality import filter_by_season
from app.domain.models.plan import ItemType
from app.domain.planner.engine import (
    get_transport_mode,
    poi_geo_region_key,
    poi_repeat_cluster_key,
    should_skip_poi_candidate,
    visit_duration_hard_cap,
    _meal_restaurant_geo_ok,
)
from app.domain.planner.explainability import explain_poi_selection
from app.domain.planner.poi_copy import build_fallback_copy, classify_poi_category
from app.domain.scoring.profile_poi_rules import (
    poi_trip_repeat_key,
    should_deny_poi_for_profile,
)


def test_lustrzany_labirynt_indoor_copy():
    poi = {"name": "Lustrzany Labirynt", "city": "Kraków", "tags": ["maze"]}
    assert classify_poi_category(poi) == "mirror_maze"
    desc, tip = build_fallback_copy(poi)
    assert "świeżym powietrzu" not in desc.lower()
    assert "budynku" in desc.lower() or "lustrzan" in desc.lower()
    why = " ".join(
        explain_poi_selection(
            poi,
            {"city": "Kraków"},
            {"target_group": "family_kids"},
        )
    )
    assert "świeżym powietrzu" not in why.lower()


def test_park_lotnikow_not_amusement():
    assert classify_poi_category({
        "name": "Park Lotników Polskich",
        "tags": ["amusement", "park"],
    }) == "park"


def test_lego_cluster_shared_key():
    assert poi_trip_repeat_key("Bricks & Figs") == poi_trip_repeat_key("Świat w Budowie")
    assert poi_repeat_cluster_key("Bricks & Figs") == "cluster_lego_bricks"
    assert poi_repeat_cluster_key("Świat w Budowie") == "cluster_lego_bricks"


def test_visit_caps_client_hotspots():
    assert visit_duration_hard_cap({"name": "GoJump Wrocław"}) == 90
    assert visit_duration_hard_cap({"name": "Bastion Sakwowy"}) == 75
    assert visit_duration_hard_cap({"name": "Hala Targowa"}) == 60
    assert visit_duration_hard_cap({"name": "Nikiszowiec"}) == 90
    assert visit_duration_hard_cap({"name": "Galeria Szyb Wilson"}) == 90
    assert visit_duration_hard_cap({"name": "Park Chopina"}) == 60
    assert visit_duration_hard_cap({"name": "Kościół św. Anny"}) == 20
    assert visit_duration_hard_cap({"name": "Rogalowe Muzeum Poznania"}) == 75
    assert visit_duration_hard_cap({"name": "Zamek Ujazdowski"}) == 120
    assert visit_duration_hard_cap({"name": "Muzeum Narodowe"}) == 120
    assert visit_duration_hard_cap({"name": "Muzeum Archeologiczne"}) == 90
    assert visit_duration_hard_cap({"name": "Hala Stulecia"}) == 90
    # Named church cap beats the generic 90 min church floor.
    assert visit_duration_hard_cap({"name": "Kościół Mariacki"}) == 90


def test_sierpc_and_wedel_denials():
    assert should_deny_poi_for_profile(
        {"name": "Muzeum Wsi Mazowieckiej w Sierpcu"},
        {"target_group": "couples", "preferences": ["museum_heritage"], "travel_style": "cultural"},
    )
    assert should_deny_poi_for_profile(
        {"name": "Pijalnia Czekolady E. Wedel"},
        {"target_group": "friends", "preferences": ["adventure", "underground"], "travel_style": "adventure"},
    )
    assert should_deny_poi_for_profile(
        {"name": "House of Air"},
        {"target_group": "couples", "preferences": ["relaxation"], "travel_style": "relax"},
    )
    assert should_deny_poi_for_profile(
        {"name": "House of Spices"},
        {"target_group": "family_kids", "preferences": ["kids_attractions"], "travel_style": "relax"},
    )
    assert should_deny_poi_for_profile(
        {"name": "Centrum Nauki Kopernik"},
        {
            "target_group": "friends",
            "preferences": ["underground", "history_mystery", "museum_heritage"],
            "travel_style": "adventure",
        },
    )


def test_winter_drops_bagry_and_beach():
    pois = [
        {"name": "Zalew Bagry", "season_fit": {"winter": 1, "spring": 1, "summer": 1, "autumn": 1}},
        {"name": "Plaża Puszczykowo", "season_fit": {"winter": 1, "spring": 1, "summer": 1, "autumn": 1}},
        {"name": "Wawel", "season_fit": {"winter": 1, "spring": 1, "summer": 1, "autumn": 1}},
    ]
    out = filter_by_season(pois, date(2026, 2, 10))
    names = {p["name"] for p in out}
    assert "Zalew Bagry" not in names
    assert "Plaża Puszczykowo" not in names
    assert "Wawel" in names


def test_arboretum_blocked_on_short_trips():
    poi = {"name": "Arboretum Wojsławice", "city": "Oława", "lat": 50.9, "lng": 17.3}
    assert should_skip_poi_candidate(poi, {"num_days": 3, "trip_type": "city_tourism"})
    assert not should_skip_poi_candidate(poi, {"num_days": 5, "trip_type": "city_tourism"})


def test_micro_stop_far_from_centroid_blocked():
    poi = {
        "name": "Plaża Puszczykowo",
        "lat": 52.28,
        "lng": 16.75,
        "time_max": 35,
        "time_min": 30,
    }
    ctx = {
        "num_days": 3,
        "trip_type": "city_tourism",
        "city_centroid": (52.406, 16.925),  # Poznań
    }
    assert should_skip_poi_candidate(poi, ctx)
    fort = {
        "name": "Fort Legionów",
        "lat": 52.28,
        "lng": 16.75,
        "time_max": 35,
        "time_min": 30,
    }
    assert not should_skip_poi_candidate(fort, ctx)


def test_kornik_and_zabrze_region_keys():
    assert poi_geo_region_key({"name": "Zamek w Kórniku", "city": "Kórnik"}) == "region_kornik"
    assert poi_geo_region_key({"name": "Skansen", "city": "Zabrze"}) == "region_zabrze"


def test_meal_geo_ojcow_and_wieliczka():
    ojcow_poi = {"name": "Jaskinia Łokietka", "city": "Ojców", "lat": 50.2, "lng": 19.8}
    krak_rest = {"name": "Restauracja Krakowska", "city": "Kraków"}
    assert not _meal_restaurant_geo_ok(
        krak_rest, ojcow_poi, {"day_geo_region": "region_ojcow"}
    )
    wiel_poi = {"name": "Kopalnia Soli Wieliczka", "city": "Wieliczka", "lat": 49.98, "lng": 20.05}
    assert not _meal_restaurant_geo_ok(
        krak_rest, wiel_poi, {"day_geo_region": "region_wieliczka"}
    )
    wiel_rest = {"name": "Karczma Wieliczka", "city": "Wieliczka"}
    assert _meal_restaurant_geo_ok(
        wiel_rest, wiel_poi, {"day_geo_region": "region_wieliczka"}
    )
    # After returning to Kraków — never send lunch back to the salt mine.
    krak_poi = {"name": "Muzeum Obwarzanka", "city": "Kraków", "lat": 50.06, "lng": 19.94}
    salina = {"name": "Restauracja Salina", "city": "Wieliczka"}
    assert not _meal_restaurant_geo_ok(
        salina, krak_poi, {"day_geo_region": "region_wieliczka"}
    )
    assert _meal_restaurant_geo_ok(
        krak_rest, krak_poi, {"day_geo_region": "region_wieliczka"}
    )


def test_short_hop_walk_with_context_in_recompute_path():
    a = {"lat": 50.054, "lng": 19.935}  # Bulwary-ish
    b = {"lat": 50.0545, "lng": 19.9355}  # ~80 m / Wawel-ish
    ctx = {
        "has_car": True,
        "transport_modes": ["car", "walking"],
        "trip_type": "city_tourism",
        "signals": {"cluster_type": "standalone_city"},
        "region_type": "city",
    }
    assert get_transport_mode(a, b, ctx) == "walking"


def test_reorder_leading_lunch():
    from types import SimpleNamespace

    lunch = SimpleNamespace(
        type=ItemType.LUNCH_BREAK,
        start_time="09:30",
        end_time="10:15",
        duration_min=45,
        suggestions=[],
    )
    attr = SimpleNamespace(
        type=ItemType.ATTRACTION,
        name="Wawel",
        start_time="10:30",
        end_time="12:00",
        duration_min=90,
    )
    out = _reorder_leading_lunch([lunch, attr])
    types = [getattr(it, "type", None) for it in out]
    assert types[0] == ItemType.ATTRACTION
    assert types[1] == ItemType.LUNCH_BREAK
    assert getattr(out[1], "start_time", None) == "12:05"


def test_strip_phantom_transit_from_unscheduled():
    from types import SimpleNamespace

    from app.domain.models.plan import TransitItem, TransitMode
    from app.domain.planner.time_utils import time_to_minutes

    def _attr(name, start, end):
        return SimpleNamespace(
            type=ItemType.ATTRACTION,
            name=name,
            start_time=start,
            end_time=end,
            duration_min=time_to_minutes(end) - time_to_minutes(start),
        )

    def _tr(frm, to, start, end):
        return TransitItem(
            type=ItemType.TRANSIT,
            **{
                "from": frm,
                "to": to,
                "start_time": start,
                "end_time": end,
                "duration_min": time_to_minutes(end) - time_to_minutes(start),
                "mode": TransitMode.CAR,
                "distance_km": 5.0,
            },
        )

    svc = PlanService(MagicMock())
    items = [
        _attr("Park Jordana", "15:33", "16:23"),
        _tr("Zamek Pieskowa Skała", "Zamek w Ojcowie", "18:35", "18:55"),
        _attr("Zamek w Ojcowie", "18:55", "19:40"),
    ]
    out = svc._strip_transits_to_unscheduled_destinations(items, day_num=5)
    transits = [i for i in out if getattr(i, "type", None) == ItemType.TRANSIT]
    assert not any(
        "Pieskowa" in (getattr(t, "from_location", "") or "") for t in transits
    )
