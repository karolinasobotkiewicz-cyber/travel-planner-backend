"""
FIX #212 regression — friends profile + cluster scoring weights.

Run: python test_fix212.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.domain.scoring.friends_profile import apply_friends_profile_scoring
from app.domain.scoring.cluster_scoring import (
    apply_cluster_scoring_weights,
    effective_travel_minutes,
)
from app.domain.planner.engine import (
    is_quick_stop_poi,
    is_museum_heritage_poi,
    is_heritage_culture_site_poi,
    score_poi,
)


def _friends_user(**kw):
    base = {
        "target_group": "friends",
        "preferences": ["active_sport", "adventure"],
        "travel_style": "adventure",
        "group_size": 4,
    }
    base.update(kw)
    return base


def test_friends_boosts_group_fun():
    poi = {
        "name": "Park Linowy GoJump",
        "tags": ["trampoline_park", "group_fun_activity"],
        "type": "poi",
    }
    user = _friends_user()
    s0 = 50.0
    s1 = apply_friends_profile_scoring(
        poi, user, {}, s0,
        poi_matches_preferences=True,
        is_quick_stop_poi=is_quick_stop_poi,
        is_museum_heritage_poi=is_museum_heritage_poi,
        is_heritage_culture_site_poi=is_heritage_culture_site_poi,
    )
    assert s1 > s0 + 40, f"expected group-fun boost, got {s1 - s0}"


def test_friends_demotes_church_without_culture():
    poi = {
        "name": "Kościół św. Katarzyny",
        "tags": ["gothic_church_landmark"],
        "type": "poi",
    }
    user = _friends_user(preferences=["active_sport"], travel_style="adventure")
    s0 = 100.0
    s1 = apply_friends_profile_scoring(
        poi, user, {}, s0,
        poi_matches_preferences=False,
        is_quick_stop_poi=is_quick_stop_poi,
        is_museum_heritage_poi=is_museum_heritage_poi,
        is_heritage_culture_site_poi=is_heritage_culture_site_poi,
    )
    assert s1 < s0 - 30, f"expected church penalty, got {s1 - s0}"


def test_cluster_urban_accessibility_boost():
    poi = {
        "name": "ECS",
        "tags": ["museum_heritage", "accessible"],
        "crowd_level": 2,
        "space": "indoor",
        "City": "Gdańsk",
        "Hub": "Gdańsk",
    }
    ctx = {"signals": {"cluster_type": "urban_organism"}, "requested_city": "Gdańsk"}
    weights = {"urban_accessibility": 1.1, "location_diversity": 1.2, "transit_penalty": 0.8}
    s0 = 80.0
    s1 = apply_cluster_scoring_weights(
        s0, poi, {}, ctx, weights, tag_bonus=30.0, poi_matches_preferences=True,
    )
    assert s1 > s0, f"expected urban boost, got {s1}"


def test_cluster_location_diversity_cross_hub():
    poi = {
        "name": "ORP Błyskawica",
        "tags": ["museum_heritage", "naval_history"],
        "City": "Gdynia",
        "Hub": "Gdynia",
    }
    ctx = {"signals": {"cluster_type": "urban_organism"}, "requested_city": "Gdańsk"}
    weights = {"location_diversity": 1.2, "transit_penalty": 0.8, "urban_accessibility": 1.1}
    s0 = 60.0
    s1 = apply_cluster_scoring_weights(
        s0, poi, {}, ctx, weights, tag_bonus=40.0, poi_matches_preferences=True,
    )
    assert s1 > s0 + 5, f"expected cross-hub boost, got {s1 - s0}"


def test_transit_penalty_reduces_cross_hub_travel():
    ctx = {"scoring_weights": {"transit_penalty": 0.8}}
    a = {"City": "Gdańsk", "Hub": "Gdańsk"}
    b = {"City": "Gdynia", "Hub": "Gdynia"}
    eff = effective_travel_minutes(30, ctx, a, b)
    assert eff == 24, f"expected 24 min, got {eff}"
    same = effective_travel_minutes(30, ctx, a, a)
    assert same == 30


def test_score_poi_friends_beats_church_for_adventure():
    """Integration: friends+adventure — trampoline scores above church."""
    trampoline = {
        "id": "t1", "name": "Trampolina Park", "type": "poi",
        "tags": ["trampoline_park", "group_fun_activity"],
        "must_see": 5, "priority": 5, "time_min": 90,
        "Lat": 50.0, "Lng": 19.0,
    }
    church = {
        "id": "c1", "name": "Kościół Mariacki", "type": "poi",
        "tags": ["gothic_church_landmark"],
        "must_see": 8, "priority": 8, "time_min": 45,
        "Lat": 50.01, "Lng": 19.01,
    }
    user = _friends_user()
    ctx = {"scoring_weights": {}, "signals": {"cluster_type": "urban_organism"}}
    st = score_poi(trampoline, user, 0, set(), 600, 600, ctx, 0, "neutral", False, daily_cost=0)
    sc = score_poi(church, user, 0, set(), 600, 600, ctx, 0, "neutral", False, daily_cost=0)
    assert st > sc, f"trampoline {st} should beat church {sc}"


def main():
    tests = [
        test_friends_boosts_group_fun,
        test_friends_demotes_church_without_culture,
        test_cluster_urban_accessibility_boost,
        test_cluster_location_diversity_cross_hub,
        test_transit_penalty_reduces_cross_hub_travel,
        test_score_poi_friends_beats_church_for_adventure,
    ]
    failed = []
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed.append(t.__name__)
    print("=" * 50)
    if failed:
        print(f"FAILED: {failed}")
        sys.exit(1)
    print("ALL FIX #212 CHECKS PASSED")
    return 0


if __name__ == "__main__":
    main()
