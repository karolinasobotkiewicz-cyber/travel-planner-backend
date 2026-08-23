"""FIX #274 — Wrocław remaining client: hops, season, kids-only, meals, caps."""
from __future__ import annotations

from app.application.services.plan_service import (
    PlanService,
    _filter_meal_suggestions,
    _is_wojslawice_stop_name,
)
from app.domain.filters.seasonality import filter_by_season
from app.domain.models.plan import RestaurantSuggestion
from app.domain.planner.engine import visit_duration_hard_cap, choose_duration
from app.domain.scoring.profile_poi_rules import (
    poi_trip_repeat_key,
    should_deny_poi_for_profile,
)


def test_fix274_wojslawice_name():
    assert _is_wojslawice_stop_name("Arboretum Wojsławice")


def test_fix274_caps_and_floors():
    assert visit_duration_hard_cap({"name": "Kolejkowo"}, for_scheduling=True) == 60
    assert visit_duration_hard_cap({"name": "Movie Gate"}, for_scheduling=True) == 90
    assert visit_duration_hard_cap({"name": "Park Mamuta"}, for_scheduling=True) == 75
    assert visit_duration_hard_cap(
        {"name": "Panorama Racławicka"}, for_scheduling=True
    ) == 30
    d = choose_duration(
        {"name": "Muzeum Motoryzacji Wena", "time_min": 20, "time_max": 180},
        10 * 60, 18 * 60, True, {"target_group": "solo"},
    )
    assert d >= 90
    d2 = choose_duration(
        {"name": "Laser Tag", "time_min": 30, "time_max": 120},
        10 * 60, 18 * 60, True, {"target_group": "friends"},
    )
    assert d2 >= 60


def test_fix274_winter_wojslawice_and_labirynt_denied():
    user = {
        "target_group": "couples",
        "preferences": ["nature_landscape", "museum_heritage"],
        "travel_style": "balanced",
        "start_date": "2026-02-20",
    }
    # FIX #283: Arboretum is wanted on the Niemcza nature day even in February.
    assert not should_deny_poi_for_profile({"name": "Arboretum Wojsławice"}, user)
    assert should_deny_poi_for_profile({"name": "Grabowy Labirynt"}, user)
    kept = filter_by_season(
        [{"name": "Arboretum Wojsławice"}, {"name": "Grabowy Labirynt"}, {"name": "Rynek"}],
        "2026-02-20",
    )
    names = " ".join(p["name"].lower() for p in kept)
    assert "wojsławice" in names or "wojslawice" in names or "arboretum" in names
    assert "grabowy" not in names


def test_fix274_kids_only_and_seniors():
    couples = {
        "target_group": "couples",
        "preferences": ["nature_landscape", "local_food_experience"],
        "travel_style": "balanced",
    }
    assert should_deny_poi_for_profile({"name": "Bobolandia"}, couples)
    assert should_deny_poi_for_profile({"name": "Kosmopark"}, {
        "target_group": "solo",
        "preferences": ["nature_landscape", "relaxation"],
        "travel_style": "relax",
    })
    seniors = {
        "target_group": "seniors",
        "preferences": ["museum_heritage", "relaxation"],
        "travel_style": "relax",
    }
    assert should_deny_poi_for_profile({"name": "Flyspot"}, seniors)
    assert should_deny_poi_for_profile({"name": "Laser Tag"}, seniors)
    assert should_deny_poi_for_profile({"name": "Kosmopark"}, seniors)


def test_fix274_laser_tag_needs_active_sport():
    assert should_deny_poi_for_profile(
        {"name": "Laser Tag"},
        {
            "target_group": "couples",
            "preferences": ["museum_heritage", "relaxation", "local_food_experience"],
            "travel_style": "cultural",
        },
    )
    assert not should_deny_poi_for_profile(
        {"name": "Laser Tag"},
        {
            "target_group": "friends",
            "preferences": ["active_sport", "history_mystery"],
            "travel_style": "adventure",
        },
    )


def test_fix274_flyspot_over_daily_limit():
    assert should_deny_poi_for_profile(
        {"name": "Flyspot", "ticket_normal": 299},
        {
            "target_group": "solo",
            "preferences": ["nature_landscape", "museum_heritage"],
            "travel_style": "balanced",
            "daily_limit": 250,
        },
    )


def test_fix274_paintball_trip_key():
    assert poi_trip_repeat_key("CityPaintball") == poi_trip_repeat_key(
        "Fort Przygody Paintball"
    )


def test_fix274_meal_slot_and_warzywniak():
    lunch_only = RestaurantSuggestion(
        id="l", name="Lunch Bar", lat=51.1, lng=17.0, meal_type="lunch",
    )
    dinner_only = RestaurantSuggestion(
        id="d", name="Wieczór Grill", lat=51.1, lng=17.0, meal_type="dinner",
    )
    warz = RestaurantSuggestion(
        id="w", name="Warzywniak", lat=51.1, lng=17.0, meal_type="all",
    )
    other = RestaurantSuggestion(
        id="o", name="Taste", lat=51.1, lng=17.0, meal_type="all",
    )
    dinner = _filter_meal_suggestions(
        [lunch_only, dinner_only, warz, other], meal_slot="dinner",
    )
    names = [s.name for s in dinner]
    assert "Lunch Bar" not in names
    assert "Wieczór Grill" in names
    assert names[0] != "Warzywniak"
    lunch = _filter_meal_suggestions(
        [lunch_only, dinner_only, warz, other], meal_slot="lunch",
    )
    lnames = [s.name for s in lunch]
    assert "Wieczór Grill" not in lnames
    assert "Lunch Bar" in lnames


def test_fix274_named_hop_cap():
    from app.domain.models.plan import ItemType, TransitItem, TransitMode

    svc = PlanService.__new__(PlanService)
    it = TransitItem(
        type=ItemType.TRANSIT,
        start_time="09:00",
        end_time="11:45",
        duration_min=165,
        mode=TransitMode.CAR,
        from_location="Wrocław",
        to_location="Arboretum Wojsławice",
        distance_km=65.0,
        routing_source="estimated_road",
    )
    out = svc._fix_implausible_transit_duration(it, {}, {"has_car": True})
    assert int(out.duration_min) <= 60
    short = TransitItem(
        type=ItemType.TRANSIT,
        start_time="09:00",
        end_time="09:25",
        duration_min=25,
        mode=TransitMode.CAR,
        from_location="Wrocław",
        to_location="Arboretum Wojsławice",
        distance_km=66.0,
        routing_source="estimated_road",
    )
    out2 = svc._fix_implausible_transit_duration(short, {}, {"has_car": True})
    assert 50 <= int(out2.duration_min) <= 60


def test_fix274_strip_transit_during_dinner():
    from app.domain.models.plan import (
        DinnerBreakItem,
        ItemType,
        TransitItem,
        TransitMode,
    )

    svc = PlanService.__new__(PlanService)
    items = [
        DinnerBreakItem(
            type=ItemType.DINNER_BREAK,
            start_time="18:00",
            end_time="19:00",
            duration_min=60,
            suggestions=[],
        ),
        TransitItem(
            type=ItemType.TRANSIT,
            start_time="18:09",
            end_time="18:32",
            duration_min=23,
            mode=TransitMode.CAR,
            from_location="Laser Tag",
            to_location="Park Mamuta",
        ),
    ]
    out = svc._strip_legs_inside_meals(items, day_num=3)
    dests = [getattr(it, "to_location", "") for it in out]
    assert "Park Mamuta" not in dests
