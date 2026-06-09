"""
FIX #191 — strict preference coverage for API reports.

Scoring uses enriched tags + broad tag_preferences vocabulary.
Coverage reports use Excel tags (tags_excel) with a denylist so POIs are not
attributed to preferences they do not semantically represent
(e.g. Most Świętokrzyski city_view → not nature_landscape).
"""

from __future__ import annotations

from typing import Any, Dict, Set

# Excel/scoring tags that must NOT count toward a preference in trip coverage.
_COVERAGE_DENY: Dict[str, frozenset] = {
    "nature_landscape": frozenset({
        "city_view", "city_views", "panoramic_city_views", "scenic_city_views",
        "riverside_walk", "urban_life", "leisure_space", "modern_bridge",
        "river_crossing", "architecture_feature", "meeting_spot", "tourist_promenade",
        "optical_illusion", "interactive_fun", "fun_photo_spot", "visual_tricks",
        "educational_space",
    }),
    "local_food_experience": frozenset({
        "urban_life", "leisure_space", "riverside_walk", "city_views", "city_view",
        "shopping", "meeting_spot", "tourist_promenade", "leisure_activity",
        "botanical_collection", "plants", "greenhouse", "modern_bridge",
    }),
    "kids_attractions": frozenset({
        "botanical_collection", "plants", "greenhouse", "educational_space",
        "riverside_walk", "city_views", "urban_life", "leisure_space",
        "modern_bridge", "architecture_feature",
        "optical_illusion", "interactive_fun", "fun_photo_spot", "visual_tricks",
    }),
    "museum_heritage": frozenset({
        "riverside_walk", "city_views", "urban_life", "leisure_space",
        "optical_illusion", "fun_photo_spot", "visual_tricks",
        "modern_bridge", "river_crossing",
    }),
    "history_mystery": frozenset({
        "city_view", "city_views", "riverside_walk", "urban_life", "leisure_space",
        "botanical_collection", "optical_illusion", "plants", "greenhouse",
    }),
}


def excel_tags(poi: Dict[str, Any]) -> Set[str]:
    raw = poi.get("tags_excel")
    if raw:
        return {str(t).strip().lower() for t in raw if t and str(t).strip()}
    return {str(t).strip().lower() for t in (poi.get("tags") or []) if t and str(t).strip()}


def poi_covers_preference_report(poi: Dict[str, Any], pref: str) -> bool:
    """True when Excel tags justify reporting this POI under `pref` in coverage API."""
    tags = excel_tags(poi)
    if not tags:
        return False
    if pref in tags:
        return True
    from app.domain.scoring.tag_preferences import USER_PREFERENCES_TO_TAGS

    cfg = USER_PREFERENCES_TO_TAGS.get(pref)
    if not cfg:
        return False
    deny = _COVERAGE_DENY.get(pref, frozenset())
    allowed = {str(t).lower() for t in cfg.get("tags", [])} - set(deny)
    return bool(tags & allowed)


def matched_coverage_tags(poi: Dict[str, Any], pref: str) -> list[str]:
    """Tags that justified coverage (for debugging / API detail)."""
    tags = excel_tags(poi)
    if pref in tags:
        return [pref]
    from app.domain.scoring.tag_preferences import USER_PREFERENCES_TO_TAGS

    cfg = USER_PREFERENCES_TO_TAGS.get(pref)
    if not cfg:
        return []
    deny = _COVERAGE_DENY.get(pref, frozenset())
    allowed = {str(t).lower() for t in cfg.get("tags", [])} - set(deny)
    return sorted(tags & allowed)
