"""FIX #221 — client feedback: free time, pref balance, micro-POI, Overpass trigger."""
from __future__ import annotations

import pytest

from app.domain.planner.engine import (
    is_quick_stop_poi,
    poi_repeat_cluster_key,
    _NICHE_MUSEUM_NAME_MARKERS,
)
from app.domain.scoring.family_fit import should_exclude_by_target_group
from app.domain.scoring.preference_coverage import poi_covers_preference_report
from app.infrastructure.routing.poi_supplement import should_supplement


class TestOverpassSupplementTrigger:
    def test_no_proactive_sparse_day(self):
        assert should_supplement(1, 0, day_num=6, num_days=7) is False
        assert should_supplement(2, 60, day_num=6, num_days=7) is False

    def test_triggers_on_large_free_time(self):
        assert should_supplement(3, 150, day_num=3, num_days=7) is True
        assert should_supplement(2, 200, day_num=3, num_days=7) is True

    def test_triggers_empty_day_with_free_time(self):
        assert should_supplement(0, 120, day_num=1, num_days=7) is True

    def test_duplication_gap_flag(self):
        assert should_supplement(5, 0, duplication_gap=True) is True


class TestMicroPoiAndClusters:
    def test_okraglak_quick_stop(self):
        assert is_quick_stop_poi({"name": "Okrąglak", "must_see": 5})

    def test_domy_kupieckie_quick_stop(self):
        assert is_quick_stop_poi({"name": "Domy Kupieckie", "must_see": 4})

    def test_katowice_church_quick_stop(self):
        assert is_quick_stop_poi({"name": "Parafia Rzymskokatolicka pw. św. Anny"})

    def test_niche_museum_markers_nonempty(self):
        assert "muzeum geologiczne" in _NICHE_MUSEUM_NAME_MARKERS

    def test_warsaw_pkin_cluster(self):
        assert poi_repeat_cluster_key("Pałac Kultury i Nauki") == "cluster_warsaw_pkin"

    def test_warsaw_wilanow_cluster(self):
        assert poi_repeat_cluster_key("Pałac w Wilanowie") == "cluster_warsaw_wilanow"


class TestFamilyKidsDeny:
    def test_parafia_sw_anny_denied(self):
        poi = {"name": "Parafia Rzymskokatolicka pw. św. Anny", "target_groups": ["seniors", "solo"]}
        user = {"target_group": "family_kids"}
        assert should_exclude_by_target_group(poi, user) is True

    def test_sw_michal_denied(self):
        poi = {"name": "Kościół św. Michała Archanioła", "target_groups": ["couples"]}
        user = {"target_group": "family_kids"}
        assert should_exclude_by_target_group(poi, user) is True


class TestRogalinRelaxationDeny:
    def test_rogalin_not_relaxation_coverage(self):
        poi = {
            "name": "Muzeum Pałac w Rogalinie",
            "tags": ["museum_heritage", "regional_heritage", "palace_interior"],
        }
        assert poi_covers_preference_report(poi, "relaxation") is False

    def test_spa_still_relaxation(self):
        poi = {"name": "Termy", "tags": ["relaxation", "spa", "thermal_baths"]}
        assert poi_covers_preference_report(poi, "relaxation") is True


class TestRelaxStyleBuildDay:
    def test_build_day_relax_no_name_error(self):
        from app.domain.planner.engine import build_day
        user = {
            "target_group": "couples",
            "travel_style": "relax",
            "preferences": ["relaxation", "museum_heritage"],
        }
        ctx = {
            "num_days": 3,
            "current_day_num": 1,
            "trip_type": "city_tourism",
            "region_type": "city",
            "multi_city_density_mode": True,
            "city_pool_size": 80,
        }
        pois = [{
            "id": "p1", "name": "Test Museum", "lat": 52.4, "lng": 16.9,
            "tags": ["museum_heritage", "themed_museum"],
            "type": "museum", "time_min": 60, "must_see": 8,
            "target_groups": ["couples", "seniors", "solo"],
        }]
        plan = build_day(pois, user, ctx, global_used=set())
        assert isinstance(plan, list)


class TestMergedFreeTimeCap:
    def test_urban_cap_90(self):
        # FIX #222/#229: urban merged free-time cap tightened 90 → 60 → 45 min.
        from app.application.services.plan_service import _max_merged_free_time_cap
        assert _max_merged_free_time_cap({"region_type": "city"}) == 45

    def test_zakopane_cap_300(self):
        from app.application.services.plan_service import _max_merged_free_time_cap
        assert _max_merged_free_time_cap({"is_zakopane_trip": True}) == 300
