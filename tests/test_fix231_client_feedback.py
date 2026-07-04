"""FIX #231 — client feedback round 4 (Wrocław/Warszawa/Kraków/Katowice/Poznań)."""

from app.application.services.plan_service import (
    _cap_total_day_free_time,
    _fix_late_lunch,
    _max_merged_free_time_cap,
)
from app.domain.models.plan import DayEndItem, FreeTimeItem, LunchBreakItem
from app.domain.planner.engine import MEAL_RESTAURANT_MAX_DIST_KM, compute_prefs_needed_today
from app.domain.scoring.profile_poi_rules import (
    profile_poi_score_delta,
    should_deny_poi_for_profile,
)


def test_urban_free_time_cap_20_min():
    assert _max_merged_free_time_cap({"region_type": "city"}) == 20


def test_meal_restaurant_max_dist_1km():
    assert MEAL_RESTAURANT_MAX_DIST_KM == 1.0


def test_family_kids_denies_bazylika_mariacka():
    poi = {"name": "Bazylika Mariacka", "tags": ["church"]}
    user = {"target_group": "family_kids", "preferences": ["kids_attractions"]}
    assert should_deny_poi_for_profile(poi, user) is True


def test_cultural_denies_lustrzany_labirynt():
    poi = {"name": "Lustrzany Labirynt", "tags": ["interactive_fun"]}
    user = {"target_group": "solo", "travel_style": "cultural", "preferences": ["museum_heritage"]}
    assert should_deny_poi_for_profile(poi, user) is True


def test_wroclaw_seniors_relax_boosts_park_szczytnicki():
    poi = {"name": "Park Szczytnicki", "tags": ["city_park", "relaxation"]}
    user = {"target_group": "seniors", "travel_style": "relax", "preferences": ["relaxation"]}
    delta = profile_poi_score_delta(poi, user, context={"current_day_num": 2, "num_days": 5})
    assert delta > 0


def test_most_grunwaldzki_demoted():
    poi = {"name": "Most Grunwaldzki", "tags": ["bridge"], "must_see": 7}
    user = {"target_group": "couples", "travel_style": "balanced", "preferences": ["nature_landscape"]}
    delta = profile_poi_score_delta(poi, user, context={"current_day_num": 1, "num_days": 7})
    assert delta < -100


def test_active_sport_spread_needed_day4():
    user = {"preferences": ["active_sport", "adventure", "friends"]}
    ctx = {
        "current_day_num": 4,
        "num_days": 5,
        "day_preference_counts": {},
        "trip_pref_days": {"active_sport": {1}},
    }
    needed = compute_prefs_needed_today(user, ctx)
    assert "active_sport" in needed


def test_cap_total_day_free_time():
    items = [
        FreeTimeItem(start_time="10:00", end_time="10:30", duration_min=30, label="a"),
        FreeTimeItem(start_time="11:00", end_time="12:00", duration_min=60, label="b"),
        FreeTimeItem(start_time="14:00", end_time="14:30", duration_min=30, label="c"),
    ]
    capped = _cap_total_day_free_time(items, max_total=45)
    total = sum(getattr(it, "duration_min", 0) for it in capped)
    assert total <= 45


def test_fix_late_lunch_moves_to_1230():
    lunch = LunchBreakItem(start_time="15:30", end_time="16:10", duration_min=40, suggestions=[])
    fixed = _fix_late_lunch([lunch])
    assert fixed[0].start_time == "12:30"
