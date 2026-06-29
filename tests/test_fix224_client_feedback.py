"""FIX #224 (29.06.2026) — client feedback for Warszawa.

Covers:
- Over-ranked micro/filler POIs demoted to quick-stops
  (Kopiec Powstania, Manufaktura Cukierków, Pijalnia Wedla).
- Coverage miscredits removed (Jeziorko Czerniakowskie, Wedel).
- Centrum Nauki Kopernik excluded for solo plans.
- Cultural flagships boosted for cultural / museum / history profiles.
"""

from app.domain.planner.engine import is_quick_stop_poi
from app.domain.scoring.preference_coverage import poi_covers_preference_report
from app.domain.scoring.family_fit import should_exclude_by_target_group


def _poi(name, **kw):
    base = {"name": name, "tags": kw.pop("tags", [])}
    base.update(kw)
    return base


def test_kopiec_powstania_is_quick_stop():
    assert is_quick_stop_poi(_poi("Kopiec Powstania Warszawskiego")) is True


def test_manufaktura_cukierkow_is_quick_stop():
    assert is_quick_stop_poi(_poi("Manufaktura Cukierków")) is True


def test_pijalnia_wedla_is_quick_stop():
    assert is_quick_stop_poi(_poi("Pijalnia Czekolady E. Wedel")) is True


def test_jeziorko_not_active_sport_or_history():
    poi = _poi(
        "Jeziorko Czerniakowskie",
        tags=["urban_lake", "swimming_spot", "nature_escape", "summer_relax"],
    )
    assert poi_covers_preference_report(poi, "active_sport") is False
    assert poi_covers_preference_report(poi, "history_mystery") is False


def test_wedel_not_underground_or_history():
    poi = _poi("Pijalnia Czekolady E. Wedel", tags=["chocolate", "cafe"])
    assert poi_covers_preference_report(poi, "underground") is False
    assert poi_covers_preference_report(poi, "history_mystery") is False


def test_kopernik_excluded_for_solo():
    poi = _poi(
        "Centrum Nauki Kopernik",
        target_groups=["solo", "couples", "friends", "family_kids"],
    )
    assert should_exclude_by_target_group(poi, {"target_group": "solo"}) is True
    # families should still be allowed
    assert should_exclude_by_target_group(poi, {"target_group": "family_kids"}) is False
