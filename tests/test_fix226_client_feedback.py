"""FIX #226 (29.06.2026) — client feedback for Katowice.

Covers:
- GZM (Górny Śląsk) urban cluster so Katowice trips have a real POI pool
  (Katowice+Gliwice+Zabrze+Chorzów+Tychy) instead of just 21 POIs → empty days.
- Churches demoted for non-culture profiles; museums demoted when museum_heritage
  is not a preference; Spodek/Planetarium/Pixel demoted.
"""

from app.domain.config import DestinationClusters
from app.domain.planner.engine import score_poi


def test_katowice_expands_to_gzm_cluster():
    assert DestinationClusters.is_cluster_city("Katowice") is True
    cluster = DestinationClusters.get_cluster("Katowice")
    assert cluster is not None
    assert cluster["id"] == "gzm"
    assert cluster["type"].value == "urban_organism"
    for city in ("Katowice", "Gliwice", "Zabrze", "Chorzów"):
        assert city in cluster["cities"]


def test_gzm_neighbours_map_to_same_cluster():
    for city in ("Gliwice", "Zabrze", "Chorzów", "Tychy"):
        assert DestinationClusters.is_cluster_city(city) is True
        assert DestinationClusters.get_cluster(city)["id"] == "gzm"


def _ctx():
    return {"signals": {"cluster_type": "urban_organism"}, "current_day_num": 1,
            "num_days": 3, "day_preference_counts": {}}


def _score(poi, prefs, travel_style="active", tg="couples", context=None):
    user = {"preferences": prefs, "travel_style": travel_style, "target_group": tg}
    ctx = context or _ctx()
    # score_poi(p, user, fatigue, used, now, energy_left, context,
    #           culture_streak, body_state, finale_done)
    return score_poi(poi, user, 0, set(), 600, 100, ctx, 0, "neutral", False)


def test_church_demoted_for_non_culture_profile():
    church = {"name": "Kościół Świętego Michała Archanioła", "must_see": 8,
              "tags": ["historic_building"], "time_min": 30}
    sport_prefs = ["active_sport"]
    culture_prefs = ["museum_heritage", "history_mystery"]
    s_sport = _score(church, sport_prefs, travel_style="active", context=_ctx())
    s_culture = _score(church, culture_prefs, travel_style="cultural", context=_ctx())
    assert s_sport < s_culture


def test_spodek_demoted():
    spodek = {"name": "Spodek w Katowicach", "must_see": 6, "tags": ["landmark"],
              "time_min": 15}
    plain = {"name": "Dolina Trzech Stawów", "must_see": 7,
             "tags": ["lakes_rivers", "scenic_walk"], "time_min": 60}
    s_spodek = _score(spodek, ["nature_landscape"], context=_ctx())
    s_plain = _score(plain, ["nature_landscape"], context=_ctx())
    assert s_spodek < s_plain
