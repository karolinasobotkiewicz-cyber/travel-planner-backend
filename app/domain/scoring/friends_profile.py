"""
FIX #212 — dedicated friends ranking profile.

Consolidates scattered FIX #99 / #206 friends logic into one scoring path
invoked from score_poi() when target_group == friends.
"""
from __future__ import annotations

from typing import Any, Dict


def _tags(poi: dict) -> set[str]:
    return {str(t).lower() for t in (poi.get("tags") or []) if t}


def _name(poi: dict) -> str:
    return str(poi.get("name", "")).lower()


_FRIENDS_FUN_TAGS = frozenset({
    "interactive_game_arena", "group_fun_activity", "digital_floor_games",
    "trampoline_park", "virtual_reality_cinema", "forest_rope_courses",
    "outdoor_adventure", "escape_room", "group_activity", "active_entertainment",
    "team_activity", "kulig", "winter_sports", "paintball", "laser_tag",
    "climbing_challenges", "obstacle_course", "immersive_movie_adventure",
    "adventure_playground", "sports", "active_sport",
})

_FRIENDS_FUN_NAMES = (
    "pixel", "trampolin", "park linowy", "gojump", "goair", "vr", "labirynt",
    "escape", "paintball", "laser", "linowa", "adrena", "bowling", "karting",
)

_WEAK_CULTURE_NAMES = (
    "kościół", "kosciol", "bazylika", "katedra", "parafia", "kaplica",
    "plac ", "pomnik ", "most ", "brama ", "deptak", "rzeźba", "pomnik-",
)

_SOCIAL_TAGS = frozenset({
    "nightlife", "bar", "beach", "pier", "promenade", "brewery", "craft_beer",
    "beer_tasting", "group_activity", "english_pub", "marina",
})

_SOCIAL_NAMES = ("molo", "bulwar", "plaża", "plaza", "browar", "marina", "klub")


def apply_friends_profile_scoring(
    poi: dict,
    user: dict,
    context: dict,
    score: float,
    *,
    poi_matches_preferences: bool,
    is_quick_stop_poi,
    is_museum_heritage_poi,
    is_heritage_culture_site_poi,
) -> float:
    """Apply friends-specific score adjustments. Returns updated score."""
    if str(user.get("target_group", "")).lower() != "friends":
        return score

    prefs = list(user.get("preferences") or [])
    travel_style = str(user.get("travel_style", "")).lower()
    tags = _tags(poi)
    name = _name(poi)
    poi_type = str(poi.get("type", "")).lower()

    wants_active = (
        "active_sport" in prefs
        or "mountain_trails" in prefs
        or "hiking" in prefs
        or travel_style == "adventure"
    )
    wants_culture = "museum_heritage" in prefs or "history_mystery" in prefs
    wants_relax = "relaxation" in prefs or travel_style == "relax"
    culture_led = bool(
        {"museum_heritage", "history_mystery"} & set(prefs[:3])
    )

    # ── 1. Active / adventure friends: group fun + trails, demote micro/churches ──
    if wants_active and not culture_led:
        if _FRIENDS_FUN_TAGS & tags or any(n in name for n in _FRIENDS_FUN_NAMES):
            score += 55.0
        elif poi_type == "trail":
            score += 40.0
        elif is_quick_stop_poi(poi):
            score -= 50.0
        elif any(m in name for m in _WEAK_CULTURE_NAMES):
            if not is_museum_heritage_poi(poi):
                score -= 60.0
        elif is_heritage_culture_site_poi(poi) and not is_museum_heritage_poi(poi):
            score -= 45.0

    # ── 2. Museum/history demotion when friends want action, not culture ──
    if wants_active and not wants_culture:
        if is_museum_heritage_poi(poi) and poi_type != "trail":
            score -= 55.0

    # ── 3. Relax friends: spa/parks over dry museums ──
    if wants_relax and not wants_culture:
        if is_museum_heritage_poi(poi) and not (
            tags & {"spa", "termy", "wellness", "thermal_baths", "relaxation"}
        ):
            score -= 45.0

    # ── 4. Generic social venues (all friends trips) ──
    if _SOCIAL_TAGS & tags or any(k in name for k in _SOCIAL_NAMES):
        score += 25.0

    # ── 5. Religious / weak history without culture pref ──
    if not wants_culture:
        if tags & {"gothic_church_landmark", "religious_site", "religious_museum"}:
            if not is_museum_heritage_poi(poi):
                score -= 45.0

    # ── 6. Cluster urban: extra boost for cross-hub variety (friends explore) ──
    cluster_type = (context or {}).get("signals", {}).get("cluster_type")
    if cluster_type == "urban_organism" and wants_active:
        from app.domain.planner.city_copy import poi_hub_norm, poi_city_norm, normalize_city_name
        req = normalize_city_name((context or {}).get("requested_city", ""))
        hub = poi_hub_norm(poi) or poi_city_norm(poi)
        if hub and hub != req:
            score += 15.0

    return score
