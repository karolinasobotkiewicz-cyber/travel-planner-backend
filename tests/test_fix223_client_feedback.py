"""FIX #223 — client feedback round 2 (Wrocław): quick-stop ranking, coverage,
budget dominance, dinner duration, season."""

from datetime import date

from app.domain.filters.seasonality import filter_by_season
from app.domain.planner.engine import is_quick_stop_poi
from app.domain.scoring.preference_coverage import poi_covers_preference_report


def test_browar_stu_mostow_is_quick_stop():
    poi = {"name": "Browar Stu Mostów", "must_see_score": 8}
    assert is_quick_stop_poi(poi)


def test_hala_stulecia_not_quick_stop():
    # must=9 UNESCO flagship + Szczytnicki cluster anchor — must NOT be demoted.
    poi = {"name": "Hala Stulecia", "must_see_score": 9}
    assert not is_quick_stop_poi(poi)


def test_bridges_are_quick_stops():
    for name in ("Most Tumski", "Most Grunwaldzki", "Most Pokoju"):
        assert is_quick_stop_poi({"name": name, "must_see_score": 6})


def test_katedra_not_relaxation_or_food():
    poi = {"name": "Katedra św. Jana Chrzciciela", "tags": ["relaxation", "local_food_experience"]}
    assert not poi_covers_preference_report(poi, "relaxation")
    assert not poi_covers_preference_report(poi, "local_food_experience")


def test_zlotniki_pontoon_winter_excluded():
    poi = {
        "name": "Spływy pontonowe Przystań Złotniki",
        "season_fit": {"winter": 1, "spring": 1, "summer": 1, "autumn": 0},
    }
    assert filter_by_season([poi], date(2026, 2, 15)) == []
