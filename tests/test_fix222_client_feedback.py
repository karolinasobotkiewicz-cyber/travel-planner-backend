"""FIX #222 — client feedback (Jun 2026): spread prefs, FT, coverage, family, budget."""

from datetime import date

from app.application.services.plan_service import _strip_leading_free_time
from app.domain.filters.seasonality import filter_by_season
from app.domain.models.plan import ItemType
from app.domain.planner.engine import choose_duration, compute_prefs_needed_today
from app.domain.scoring.family_fit import should_exclude_by_target_group
from app.domain.scoring.preference_coverage import poi_covers_preference_report


def test_compute_prefs_needed_spreads_after_day1():
    user = {"preferences": ["museum_heritage", "nature_landscape", "active_sport"]}
    ctx = {
        "current_day_num": 3,
        "num_days": 5,
        "day_preference_counts": {},
        "trip_pref_days": {"museum_heritage": {1, 2}, "nature_landscape": {2}},
    }
    needed = compute_prefs_needed_today(user, ctx)
    assert "active_sport" in needed
    assert "museum_heritage" in needed


def test_wedel_not_museum_heritage():
    poi = {"name": "Pijalnia Czekolady E. Wedel", "tags": ["museum_heritage", "local_food"]}
    assert not poi_covers_preference_report(poi, "museum_heritage")
    assert not poi_covers_preference_report(poi, "nature_landscape")


def test_geologiczne_not_nature():
    poi = {"name": "Muzeum Geologiczne", "tags": ["nature_landscape", "museum_heritage"]}
    assert not poi_covers_preference_report(poi, "nature_landscape")


def test_family_kids_denies_neon_side():
    poi = {"name": "Galeria Neon Side", "target_groups": ["couples", "friends"]}
    user = {"target_group": "family_kids"}
    assert should_exclude_by_target_group(poi, user)


def test_winter_denies_pontoon_zlotniki():
    poi = {"name": "Spływy pontonowe Przystań Złotniki", "season_fit": {"winter": 1, "spring": 1}}
    out = filter_by_season([poi], date(2026, 2, 15))
    assert out == []


def test_choose_duration_min_park():
    poi = {"name": "Park Kościuszki", "time_min": 13, "time_max": 20, "type": "park"}
    dur = choose_duration(poi, 540, 1140, lunch_done=True)
    assert dur >= 40


def test_strip_leading_free_time():
    class _Item:
        def __init__(self, typ, name):
            self.type = typ
            self.name = name

    items = [
        _Item(ItemType.FREE_TIME, "Czas wolny"),
        _Item(ItemType.ATTRACTION, "Rynek"),
    ]
    out = _strip_leading_free_time(items)
    assert len(out) == 1
    assert out[0].type == ItemType.ATTRACTION
