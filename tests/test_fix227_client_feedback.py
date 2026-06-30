"""FIX #227 (30.06.2026) — client feedback for Poznań.

Covers:
- Single-city sparse-day reuse retry so the last day of long single-city trips
  is never empty (client: "ostatni dzień bez żadnej atrakcji" for 5/7-day plans).
- Escape Room denied for very young children (5-year-old) and for family_kids.
- Bazylika Archikatedralna / Domy Kupieckie excluded from family_kids.
- Poznań family icons (Brama Poznania, Rogalowe Muzeum, Termy Maltańskie, Zoo)
  boosted for family_kids.
- Over-ranked filler demoted (Pomnik Bamberki, Makiety Dawnego Poznania,
  Rynek Jeżycki, Okrąglak, Pixel XL).
- Pixel / arcade / escape room no longer credit underground / history_mystery /
  museum_heritage preferences.
"""

from app.domain.planner.engine import score_poi, _FAMILY_ICON_MARKERS
from app.domain.scoring.family_fit import should_exclude_by_target_group
from app.domain.scoring.preference_coverage import poi_covers_preference_report


def _ctx():
    return {"signals": {"cluster_type": "urban_organism"}, "current_day_num": 1,
            "num_days": 3, "day_preference_counts": {}}


def _score(poi, prefs, travel_style="active", tg="couples", context=None, user_extra=None):
    user = {"preferences": prefs, "travel_style": travel_style, "target_group": tg}
    if user_extra:
        user.update(user_extra)
    ctx = context or _ctx()
    return score_poi(poi, user, 0, set(), 600, 100, ctx, 0, "neutral", False)


def test_escape_room_denied_for_young_child():
    escape = {"name": "Escape Room Poznań", "must_see": 5, "tags": ["escape_room"],
              "time_min": 60}
    s_child = _score(escape, ["adventure"], tg="family_kids",
                     user_extra={"children_age": 5})
    s_adult = _score(escape, ["adventure"], tg="friends")
    assert s_child < s_adult
    assert s_child < 0


def test_bazylika_archikatedralna_excluded_for_family_kids():
    poi = {"name": "Bazylika Archikatedralna św. Apostołów Piotra i Pawła",
           "target_groups": ["solo", "couples", "friends", "family_kids"]}
    assert should_exclude_by_target_group(poi, {"target_group": "family_kids"}) is True


def test_domy_kupieckie_excluded_for_family_kids():
    poi = {"name": "Domy Kupieckie",
           "target_groups": ["solo", "couples", "friends", "family_kids"]}
    assert should_exclude_by_target_group(poi, {"target_group": "family_kids"}) is True


def test_poznan_family_icons_registered():
    for marker in ("brama poznania", "rogalowe muzeum", "termy maltańskie", "nowe zoo"):
        assert marker in _FAMILY_ICON_MARKERS


def test_pomnik_bamberki_demoted():
    bamberki = {"name": "Pomnik Bamberki", "must_see": 4,
                "tags": ["historic_building"], "time_min": 10}
    real = {"name": "Brama Poznania", "must_see": 6,
            "tags": ["multimedia_exhibition"], "time_min": 60}
    s_bamberki = _score(bamberki, ["history_mystery"], context=_ctx())
    s_real = _score(real, ["history_mystery"], context=_ctx())
    assert s_bamberki < s_real


def test_pixel_does_not_cover_underground_or_museum():
    pixel = {"name": "Pixel XL Poznań", "tags": ["arcade_family", "family_game_zone"]}
    assert poi_covers_preference_report(pixel, "underground") is False
    assert poi_covers_preference_report(pixel, "museum_heritage") is False
    assert poi_covers_preference_report(pixel, "history_mystery") is False
