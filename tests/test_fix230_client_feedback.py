"""FIX #230 — client feedback round 3 (Wrocław/Warszawa/Kraków/Katowice/Poznań)."""

from app.application.services.plan_service import _max_merged_free_time_cap
from app.domain.planner.engine import compute_prefs_needed_today
from app.domain.scoring.family_fit import should_exclude_by_target_group
from app.domain.scoring.preference_coverage import preference_coverage_adequate
from app.domain.scoring.profile_poi_rules import (
    is_active_city_poi,
    profile_poi_score_delta,
    should_deny_poi_for_profile,
)


def test_urban_free_time_cap_30_min():
    assert _max_merged_free_time_cap({"region_type": "city"}) == 30


def test_zoo_denied_friends_adventure_underground_history():
    zoo = {"name": "Zoo Wrocław", "tags": ["zoo"], "target_groups": ["family_kids", "friends"]}
    user = {"target_group": "friends", "preferences": ["adventure", "underground", "history_mystery"]}
    assert should_deny_poi_for_profile(zoo, user) is True


def test_podziemia_rynkud_denied_family_young_child():
    poi = {"name": "Podziemia Rynku", "tags": ["underground"]}
    user = {"target_group": "family_kids", "children_age": 5, "preferences": ["history_mystery"]}
    assert should_deny_poi_for_profile(poi, user) is True


def test_kopiec_powstania_denied_family_kids():
    poi = {"name": "Kopiec Powstania Warszawskiego", "target_groups": ["solo", "friends", "family_kids"]}
    assert should_exclude_by_target_group(poi, {"target_group": "family_kids"}) is True


def test_gojump_counts_as_active_for_adventure_warning():
    assert is_active_city_poi({"name": "GoJump Wrocław", "tags": ["trampoline_park"]}) is True
    assert is_active_city_poi({"name": "Hydropolis", "tags": ["museum_heritage"]}) is True


def test_nature_coverage_requires_spread():
    one_park = [{"name": "Park", "tags": ["city_park"]}]
    assert preference_coverage_adequate("nature_landscape", one_park) is False
    two = [
        {"name": "Ogród Botaniczny", "tags": ["botanical_garden"]},
        {"name": "Bulwar", "tags": ["city_park"]},
    ]
    assert preference_coverage_adequate("nature_landscape", two) is True


def test_prefs_needed_spreads_on_later_days():
    user = {"preferences": ["nature_landscape", "relaxation", "museum_heritage"]}
    ctx = {
        "current_day_num": 4,
        "num_days": 7,
        "day_preference_counts": {},
        "trip_pref_days": {"nature_landscape": {1}, "relaxation": {1}},
    }
    needed = compute_prefs_needed_today(user, ctx)
    assert "nature_landscape" in needed
    assert "relaxation" in needed


def test_hala_stulecia_demoted_friends_adventure_sport():
    hala = {"name": "Hala Stulecia", "tags": ["architecture_heritage"], "must_see": 9}
    user = {
        "target_group": "friends",
        "travel_style": "adventure",
        "preferences": ["active_sport", "adventure"],
    }
    delta = profile_poi_score_delta(hala, user, context={"current_day_num": 2, "num_days": 5})
    assert delta < 0
