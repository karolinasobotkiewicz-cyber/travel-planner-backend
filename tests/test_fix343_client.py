"""FIX #343 — Browar Stu Mostów off family plans; Aula Leopoldina is Muzeum Uniwersytetu."""
from __future__ import annotations

from app.domain.scoring.family_fit import (
    restaurant_hard_denied_for_group,
    should_exclude_by_target_group,
)
from app.domain.scoring.profile_poi_rules import (
    poi_trip_repeat_key,
    should_deny_poi_for_profile,
)


def test_browar_stu_mostow_is_off_family_kids():
    poi = {
        "name": "Browar Stu Mostów",
        "target_groups": ["friends", "couples", "solo", "seniors"],
        "type_of_attraction": "local_food_experience",
    }
    user = {"target_group": "family_kids", "preferences": ["kids_attractions"]}
    assert should_exclude_by_target_group(poi, user)
    assert should_deny_poi_for_profile(poi, user)


def test_browar_still_ok_for_friends():
    poi = {
        "name": "Browar Stu Mostów",
        "target_groups": ["friends", "couples", "solo", "seniors"],
    }
    assert not should_exclude_by_target_group(
        poi, {"target_group": "friends"},
    )


def test_aula_leopoldina_is_never_scheduled():
    poi = {"name": "Aula Leopoldina", "target_groups": ["solo", "couples"]}
    for tg in ("family_kids", "couples", "solo", "friends", "seniors"):
        assert should_exclude_by_target_group(poi, {"target_group": tg}), tg
    assert should_deny_poi_for_profile(poi, {"target_group": "couples"})


def test_aula_shares_trip_slot_with_muzeum_uniwersytetu():
    assert (
        poi_trip_repeat_key("Aula Leopoldina")
        == poi_trip_repeat_key("Muzeum Uniwesytetu Wrocławskiego")
        == "wro_muzeum_uniwersytetu"
    )


def test_browar_is_not_a_family_restaurant():
    assert restaurant_hard_denied_for_group(
        {"name": "Browar Stu Mostów"},
        {"target_group": "family_kids"},
    )
