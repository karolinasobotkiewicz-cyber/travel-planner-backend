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
        # FIX #197: arenas / landmarks mis-tagged as nature (Spodek, Syrenka views…)
        "stadium", "sports_venue", "arena", "iconic_architecture", "iconic_landmark",
        "city_symbol", "landmark", "sports_hall", "event_venue",
        # FIX #198: urban observation decks / city icons (PKiN, Syrenka…)
        "panoramic_view", "panoramic_views", "panoramic_viewpoint",
        "observation_deck", "architecture_icon", "city_landmark",
        "photo_spot", "mermaid_statue", "scenic_photo_spot",
        # FIX #200: urban squares / markets / towers ≠ nature
        "historic_old_town_square", "medieval_old_town", "market_square", "town_square",
        "main_square", "old_town", "old_town_square", "european_square", "city_square",
        "deptak", "promenade", "tourist_street", "fortress", "bastion", "fortification",
        "stadium", "sports_venue", "science_center", "interactive_science",
    }),
    "local_food_experience": frozenset({
        "urban_life", "leisure_space", "riverside_walk", "city_views", "city_view",
        "shopping", "meeting_spot", "tourist_promenade", "leisure_activity",
        "botanical_collection", "plants", "greenhouse", "modern_bridge",
        "square", "plaza", "european_square", "city_square", "memorial",
        # FIX #200
        "deptak", "promenade", "historic_old_town_square", "market_square",
        "town_square", "island_park", "riverside_park", "photo_spot",
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
        # FIX #197: monuments / guard ceremonies / bridges — not museums
        "memorial", "war_memorial", "tomb", "monument", "statue", "symbol",
        "national_heritage", "guard_ceremony", "military_ceremony", "outdoor_memorial",
        "bridge", "historic_bridge", "bastion", "fortification",
        # FIX #200
        "historic_old_town_square", "market_square", "town_square", "fountain",
        "neptune_fountain", "gate", "city_gate", "fortress",
    }),
    "history_mystery": frozenset({
        "city_view", "city_views", "riverside_walk", "urban_life", "leisure_space",
        "botanical_collection", "optical_illusion", "plants", "greenhouse",
        # FIX #197: paintball / extreme sports ≠ history
        "paintball", "adventure_sport", "extreme_sport", "team_building",
        "adrenaline_attractions", "outdoor_activity", "sports_activity",
    }),
    "relaxation": frozenset({
        "modern_bridge", "river_crossing", "bridge", "historic_bridge",
        "city_views", "city_view", "riverside_walk", "urban_life",
        "architecture_feature", "landmark", "iconic_landmark",
        # FIX #200
        "historic_old_town_square", "market_square", "town_square", "deptak",
        "fortress", "bastion", "stadium", "sports_venue",
    }),
}


def excel_tags(poi: Dict[str, Any]) -> Set[str]:
    raw = poi.get("tags_excel")
    if raw:
        return {str(t).strip().lower() for t in raw if t and str(t).strip()}
    return {str(t).strip().lower() for t in (poi.get("tags") or []) if t and str(t).strip()}


_NATURE_LANDMARK_NAME_DENY = (
    "pałac kultury",
    "pomnik syreny",
    "syrenka warszawska",
    "pkin",
)

# FIX #199: squares/churches tagged historic_building must not count as museums.
_MUSEUM_STRONG_TAGS = frozenset({
    "museum_heritage", "themed_museum", "multimedia_exhibition", "regional_heritage",
    "art_museum", "history_museum", "science_museum", "interactive_museum",
    "open_air_museum", "ethnographic_museum", "archaeological_exhibits",
    "art_collection", "art_exhibition", "historical_museum", "city_history_exhibits",
    "folklore_museum", "industrial_heritage_museum", "museum", "historic_museum",
    "historical_exhibits", "ancient_artifacts_collection", "national_art_collection",
    "polish_art_history", "schindler_factory", "ww2_history", "early_polish_history",
    "aircraft_collection", "medieval_market_history", "royal_castle_complex",
    "polish_history", "historic_cathedral", "national_heritage", "historic_palace_museum",
})

_HISTORY_STRONG_TAGS = frozenset({
    "history_mystery", "historical_site", "castle", "underground", "medieval",
    "folklore", "ancient_legend_site", "regional_heritage", "themed_museum",
    "archaeological_exhibits", "city_history", "fortress", "folklore_museum",
    "ww2_history", "schindler_factory", "polish_history", "royal_castle_complex",
    "medieval_market_history", "early_polish_history", "historic_jewish_district",
})

_WEAK_HERITAGE_ONLY = frozenset({
    "historic_building", "architecture_heritage", "historical_exhibits",
    "square", "plaza", "church", "cathedral", "basilica", "parish",
})

_RELAXATION_STRONG_TAGS = frozenset({
    "relaxation", "spa", "termy", "wellness", "city_park", "green_space",
    "botanical_garden", "peaceful_green_space", "calm_nature_spot", "arboretum",
    "thermal_baths", "quiet_relax_spot", "park", "lake_relaxation",
})

_LOCAL_FOOD_STRONG_TAGS = frozenset({
    "local_food_experience", "regional_cuisine", "local_cuisine", "food_market",
    "culinary_experience", "traditional_food", "restaurant_district",
    "food_hall", "brewery", "culinary_workshop",
})

_WATER_STRONG_TAGS = frozenset({
    "water_attractions", "waterfall", "waterfalls", "aquapark", "water_park",
    "lake", "river_cruise", "thermal_baths", "termy", "beach", "marina",
})

_UNDERGROUND_STRONG_TAGS = frozenset({
    "underground", "cave", "mine", "tunnel", "subterranean", "caves_mines",
    "mining_heritage", "underground_route", "salt_mine",
})

_COVERAGE_NAME_DENY: Dict[str, tuple] = {
    "museum_heritage": (
        "spodek", "pomnik syreny", "park sensoryczny", "wieża ratuszowa",
        "fontanna neptuna", "dlugi targ",
    ),
    "nature_landscape": (
        "spodek", "rynek", "dlugi targ", "fontanna neptuna", "plac zdrojowy",
        "deptak", "monte cassino", "wieża ratuszowa", "most tumski",
    ),
    "local_food_experience": (
        "wyspa słodowa", "plac europejski", "deptak", "rynek",
    ),
    "relaxation": (
        "most tumski", "rynek", "fontanna",
    ),
    "history_mystery": (
        "fontanna neptuna", "brama krowia",
    ),
}


def _name_denied(poi: Dict[str, Any], pref: str) -> bool:
    name = (poi.get("name") or poi.get("Name") or "").lower()
    for frag in _COVERAGE_NAME_DENY.get(pref, ()):
        if frag in name:
            return True
    return False


def poi_covers_preference_report(poi: Dict[str, Any], pref: str) -> bool:
    """True when Excel tags justify reporting this POI under `pref` in coverage API."""
    if _name_denied(poi, pref):
        return False
    if pref == "nature_landscape":
        _name = (poi.get("name") or poi.get("Name") or "").lower()
        if any(_frag in _name for _frag in _NATURE_LANDMARK_NAME_DENY):
            return False
    tags = excel_tags(poi)
    if not tags:
        return False
    if pref in tags:
        return True
    # FIX #199/#200: strict gates — weak urban POI must not inflate coverage.
    if pref == "museum_heritage":
        _strong = tags & _MUSEUM_STRONG_TAGS
        if not _strong:
            return False
        if (
            _strong <= {"historical_exhibits"}
            and tags & {"historic_building", "architecture_heritage"}
        ):
            return False
    if pref == "history_mystery":
        if tags & _WEAK_HERITAGE_ONLY and not (tags & _HISTORY_STRONG_TAGS):
            return False
    if pref == "relaxation" and not (tags & _RELAXATION_STRONG_TAGS):
        return False
    if pref == "local_food_experience" and not (tags & _LOCAL_FOOD_STRONG_TAGS):
        return False
    if pref == "water_attractions" and not (tags & _WATER_STRONG_TAGS):
        from app.domain.planner.engine import is_water_attraction_poi
        return is_water_attraction_poi(poi)
    if pref == "underground" and not (tags & _UNDERGROUND_STRONG_TAGS):
        from app.domain.planner.engine import is_underground_poi
        return is_underground_poi(poi)
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
