"""FIX #229 (01.07.2026) — client feedback Wrocław/Poznań/Katowice/Kraków/Warszawa."""

from app.application.services.plan_service import (
    _strip_leading_free_time,
    _strip_trailing_free_time,
    _trim_gap_after_day_start,
)
from app.domain.models.plan import ItemType
from app.domain.planner.city_copy import evening_relax_label
from app.domain.planner.engine import LUNCH_EARLIEST, LUNCH_LATEST, LUNCH_TARGET, score_poi
from app.domain.scoring.family_fit import (
    restaurant_matches_target_group,
    should_exclude_by_target_group,
)
from app.domain.scoring.preference_coverage import (
    is_strong_relaxation_coverage_poi,
    preference_coverage_adequate,
)
from app.domain.scoring.travel_style import calculate_travel_style_score


def _ctx(**kw):
    base = {
        "signals": {"cluster_type": "urban_organism"},
        "current_day_num": 2,
        "num_days": 5,
        "day_preference_counts": {},
    }
    base.update(kw)
    return base


def _score(poi, prefs, travel_style="balanced", tg="friends", context=None, **user_extra):
    user = {"preferences": prefs, "travel_style": travel_style, "target_group": tg}
    user.update(user_extra)
    ctx = context or _ctx()
    return score_poi(poi, user, 0, set(), 600, 100, ctx, 0, "neutral", False)


def test_lunch_window_1230_1400():
    assert LUNCH_TARGET == "12:30"
    assert LUNCH_EARLIEST == "12:30"
    assert LUNCH_LATEST == "14:00"


def test_evening_relax_label_not_at_midday():
    label_1130 = evening_relax_label(False, 11 * 60)
    label_1230 = evening_relax_label(False, 12 * 60 + 30)
    label_1800 = evening_relax_label(False, 18 * 60, long_block=True)
    assert "Wieczorny relaks" not in label_1130
    assert "Wieczorny relaks" not in label_1230
    assert "Wieczorny relaks" in label_1800


def test_bungee_denied_for_family_kids():
    poi = {"name": "Bungee Wrocław", "target_groups": ["friends", "solo", "family_kids"]}
    assert should_exclude_by_target_group(poi, {"target_group": "family_kids"}) is True


def test_secret_room_denied_for_family_kids():
    poi = {"name": "The Secret Room", "target_groups": ["friends", "couples", "family_kids"]}
    assert should_exclude_by_target_group(poi, {"target_group": "family_kids"}) is True


def test_restaurant_target_group_filter():
    rest = {"name": "Romantyczna", "target_groups": ["couples"]}
    assert restaurant_matches_target_group(rest, {"target_group": "couples"}) is True
    assert restaurant_matches_target_group(rest, {"target_group": "family_kids"}) is False
    assert restaurant_matches_target_group({"name": "Uniwersalna"}, {"target_group": "solo"}) is True


def test_adventure_travel_style_stronger():
    active_poi = {"activity_style": "active"}
    relax_poi = {"activity_style": "relax"}
    user = {"travel_style": "adventure"}
    assert calculate_travel_style_score(active_poi, user) == 18.0
    assert calculate_travel_style_score(relax_poi, user) == -8.0


def test_adventure_prefers_mine_over_museum():
    mine = {"name": "Kopalnia Guido", "tags": ["underground", "mining_heritage"], "must_see": 7}
    museum = {"name": "Muzeum Historii", "tags": ["museum_heritage", "local_history"], "must_see": 7}
    prefs = ["friends", "adventure", "history_mystery"]
    s_mine = _score(mine, prefs, travel_style="adventure")
    s_museum = _score(museum, prefs, travel_style="adventure")
    assert s_mine > s_museum


def test_palmiarnia_counts_as_relaxation_coverage():
    palmiarnia = {"name": "Palmiarnia Poznań", "tags": ["city_park", "relaxation"]}
    assert is_strong_relaxation_coverage_poi(palmiarnia) is True
    assert preference_coverage_adequate("relaxation", [palmiarnia]) is True


def _mock_item(item_type, **kwargs):
    class _Item:
        pass

    it = _Item()
    it.type = item_type
    for k, v in kwargs.items():
        setattr(it, k, v)
    return it


def test_strip_leading_free_time_before_first_attraction():
    items = [
        _mock_item(ItemType.DAY_START, time="09:00"),
        _mock_item(ItemType.FREE_TIME, start_time="09:00", end_time="09:30", duration_min=30, label="Czas wolny"),
        _mock_item(ItemType.ATTRACTION, poi_id="1", name="Muzeum", start_time="09:30", end_time="11:00", duration_min=90),
    ]
    out = _strip_leading_free_time(items)
    assert all(getattr(it, "type", None) != ItemType.FREE_TIME for it in out)
    assert any(getattr(it, "type", None) == ItemType.ATTRACTION for it in out)


def test_strip_trailing_long_free_time():
    items = [
        _mock_item(ItemType.ATTRACTION, poi_id="1", name="Park", start_time="15:00", end_time="16:00", duration_min=60),
        _mock_item(ItemType.FREE_TIME, start_time="16:00", end_time="18:00", duration_min=120, label="Czas wolny"),
    ]
    out = _strip_trailing_free_time(items, max_min=45)
    assert not any(getattr(it, "type", None) == ItemType.FREE_TIME for it in out)


def test_trim_gap_after_day_start():
    items = [
        _mock_item(ItemType.DAY_START, time="09:00"),
        _mock_item(ItemType.FREE_TIME, start_time="09:00", end_time="10:00", duration_min=60, label="Czas wolny"),
        _mock_item(ItemType.ATTRACTION, poi_id="1", name="Rynek", start_time="10:00", end_time="11:00", duration_min=60),
    ]
    out = _trim_gap_after_day_start(items, max_gap_min=20)
    assert not any(getattr(it, "type", None) == ItemType.FREE_TIME for it in out)
