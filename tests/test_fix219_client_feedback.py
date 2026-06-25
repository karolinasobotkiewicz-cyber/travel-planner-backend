"""FIX #219 — client feedback for Poznań, Kraków, Katowice, Wrocław, Warszawa."""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.domain.filters.seasonality import filter_by_season
from app.domain.planner.engine import is_underground_poi
from app.domain.scoring.family_fit import should_exclude_by_target_group
from app.domain.scoring.preference_coverage import (
    is_strong_nature_coverage_poi,
    poi_covers_preference_report,
    preference_coverage_adequate,
)


def test_underground_podziemia_rynk():
    poi = {"name": "Podziemia Rynku", "tags": ["underground", "museum_heritage"]}
    assert is_underground_poi(poi)
    assert poi_covers_preference_report(poi, "underground")


def test_wilanow_counts_as_nature():
    poi = {"name": "Pałac w Wilanowie", "tags": ["museum_heritage", "garden"]}
    assert is_strong_nature_coverage_poi(poi)
    assert poi_covers_preference_report(poi, "nature_landscape")


def test_cmentarz_not_nature_or_relaxation():
    poi = {"name": "Cmentarz Powązkowski", "tags": ["nature_landscape", "relaxation"]}
    assert not poi_covers_preference_report(poi, "nature_landscape")
    assert not poi_covers_preference_report(poi, "relaxation")


def test_krzysztofory_not_history_mystery():
    poi = {"name": "Pałac Krzysztofory", "tags": ["museum_heritage", "history_mystery"]}
    assert poi_covers_preference_report(poi, "museum_heritage")
    assert not poi_covers_preference_report(poi, "history_mystery")


def test_nature_adequate_with_single_kopiec():
    pois = [{"name": "Kopiec Kościuszki", "tags": ["viewpoint", "nature_landscape"]}]
    assert preference_coverage_adequate("nature_landscape", pois)


def test_relaxation_adequate_with_lazienki():
    pois = [{"name": "Łazienki Królewskie", "tags": ["park", "garden"]}]
    assert preference_coverage_adequate("relaxation", pois)


def test_family_kids_denies_palace_and_nowa_huta():
    for name in (
        "Pałac Prezydencki",
        "Nowa Huta",
        "Centrum Historii Zajezdnia",
        "Kościół św. Anny",
    ):
        poi = {"name": name, "target_groups": ["friends", "family_kids"]}
        assert should_exclude_by_target_group(poi, {"target_group": "family_kids"}), name


def test_friends_denies_guliwer():
    poi = {"name": "Centrum Rozrywki Guliwer", "target_groups": ["friends", "family_kids"]}
    assert should_exclude_by_target_group(poi, {"target_group": "friends"})


def test_fountain_park_excluded_in_winter():
    poi = {"name": "Multimedialny Park Fontann", "season_fit": {"winter": 0, "spring": 1, "summer": 1, "autumn": 1}}
    out = filter_by_season([poi], datetime(2026, 2, 15))
    assert out == []


def test_kayak_excluded_in_winter_by_name():
    poi = {"name": "Kajaki na Warcie", "season_fit": {"winter": 1, "spring": 1, "summer": 1, "autumn": 1}}
    out = filter_by_season([poi], datetime(2026, 2, 15))
    assert out == []
