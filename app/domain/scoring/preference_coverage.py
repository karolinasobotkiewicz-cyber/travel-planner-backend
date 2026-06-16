"""
FIX #191 — strict preference coverage for API reports.
FIX #203 (16.06.2026) — redesigned as an explicit allowlist of *strong* semantic
tags per preference. The previous design fell back to the broad scoring
vocabulary (``USER_PREFERENCES_TO_TAGS``) which produced two classes of bugs the
client kept reporting across every city:

  * False positives — urban POI (streets, squares, monuments, bridges, viewpoints,
    fountains, illusion museums) attributed to ``nature_landscape`` /
    ``history_mystery`` / ``kids_attractions`` / ``active_sport``.
  * False negatives — obvious matches missed (parks/spas not in ``relaxation``,
    ship/literary/transport museums not in ``museum_heritage``, fountain shows not
    in ``water_attractions``, vodka museum not in ``local_food_experience``).

For every preference that clients audit we now require an explicit STRONG tag
(or the literal preference tag). No broad fallback for those preferences, so an
attraction is only credited when it semantically represents the preference.
Zakopane's genuine nature/relax/museum/food tags are all included in the strong
sets, so Zakopane coverage is preserved (regression-checked).
"""

from __future__ import annotations

from typing import Any, Dict, Set

# ─────────────────────────────────────────────────────────────────────────────
# STRONG semantic tags per preference (FIX #203).
# A POI covers the preference iff it carries the literal pref tag OR one of these.
# ─────────────────────────────────────────────────────────────────────────────
_STRONG_BY_PREF: Dict[str, frozenset] = {
    # Real nature only. Deliberately EXCLUDES generic urban "viewpoint",
    # "panoramic_view(s)", "observation_deck", "city_viewpoint", "scenic_walk",
    # "photo_spot", "architecture*", bridges and fountains — those are urban.
    # Mountain/coastal viewpoints keep coverage via mountain_views / cliff_views.
    "nature_landscape": frozenset({
        "nature", "nature_landscape", "nature_reserve", "nature_immersion",
        "nature_escape", "nature_trail", "nature_photo_spot", "nature_picnic_spot",
        "national_park", "natural_landscape", "natural_curiosity", "scenic_nature",
        "scenic_landscape", "scenic_valley", "scenic_cliffs", "scenic_hilltop",
        "scenic_viewpoint", "scenic_viewpoints", "scenic_stop", "easy_access_nature",
        "remote_nature", "quiet_nature_walks", "unusual_nature_shapes",
        "protected_landscape", "wetlands", "peat_bog_reserve", "rare_wetland_ecosystem",
        "mountain", "mountains", "mountain_views", "mountain_viewpoint",
        "mountain_valley", "mountain_experience", "mountain_waterfall",
        "panoramic_mountain_views", "tatra_viewpoint", "tatra_mountains",
        "mountain_adventure", "alpine_meadow", "alpine_meadows",
        "valley_landscape", "valley", "peak_summit", "summit_views",
        "scenic_ridge_walk", "panoramic_route", "viewpoint_trail",
        "hill_viewpoint", "viewpoint_hill", "granite_viewpoint", "granite_cliffs",
        "rock_viewpoint", "karkonosze_views", "karkonosze_ecosystem",
        "table_mountains_peak", "table_mountains_trail", "table_mountains_views",
        "table_mountains_nature", "iconic_hiking_destination", "mountain_panorama",
        "forest", "forest_trail", "forest_trails", "forest_landscape", "forest_walk",
        "forest_hike", "forest_hill_walk", "forest_reserve", "forest_setting",
        "family_forest_walk", "woodland",
        "meadow", "meadows_fields",
        "waterfall", "waterfalls", "waterfall_trail", "waterfall_spot", "gorge",
        "canyon", "lake", "lakes_rivers", "river", "riverside", "river_view",
        "colorful_lakes",
        "rock_formations", "sandstone_rock_formations", "dramatic_rock_landscape",
        "balancing_rock", "geological_phenomenon", "stone_geological_trail",
        "sandstone_corridors", "labyrinth_rock_formations", "geology",
        "karst_cave_system", "karst_cave", "underground_nature", "cave",
        "botanical_garden", "arboretum", "botanical_tree_collection",
        "botanical_collection", "greenhouse", "plant_exhibits", "plant_collection",
        "palm_house", "japanese_garden", "city_park",
        "coastal_landscape", "coastal_views", "coastal_walks", "cliff_views",
        "dramatic_cliff_views", "sea_views", "seaside_views", "sea_panorama",
        "dunes", "cliffs",
    }),
    # Museums & heritage institutions. Broadened (FIX #203) to ship/literary/
    # transport/city-history/specialized museums and gothic cathedrals.
    "museum_heritage": frozenset({
        "museum_heritage", "museum", "themed_museum", "multimedia_exhibition",
        "multimedia_storytelling", "regional_heritage", "art_museum", "art_gallery",
        "art_collection", "art_exhibition", "art_exhibits", "history_museum",
        "science_museum", "interactive_museum", "open_air_museum",
        "open_air_ethnographic_museum", "ethnographic_museum",
        "archaeological_exhibits", "historical_museum", "historic_museum",
        "city_history_exhibits", "city_history", "folklore_museum",
        "industrial_heritage_museum", "industrial_heritage", "industrial_history",
        "historical_exhibits", "ancient_artifacts_collection", "national_art_collection",
        "polish_art_history", "schindler_factory", "ww2_history", "early_polish_history",
        "aircraft_collection", "medieval_market_history", "royal_castle_complex",
        "polish_history", "historic_cathedral", "national_heritage",
        "historic_palace_museum", "historic_palace_complex", "palace_interior",
        "renaissance_castle_residence", "modern_museum", "interactive_exhibition",
        "interactive_history", "educational_exhibition", "educational_museum",
        "educational_exhibits", "literary_exhibition", "literary_museum",
        "literary_house", "literary_heritage", "writer_museum", "writer_house",
        "writer_house_museum", "transport_history", "gothic_cathedral",
        "military_heritage", "military_exhibits", "naval_history", "naval_museum",
        "maritime_history", "maritime_museum", "maritime_heritage",
        "composer_artist_house", "mountain_culture", "folk_traditions",
        "folk_culture_experience", "cultural_heritage_site", "cultural_heritage",
        "cultural_history", "cultural_collection", "local_culture_collection",
        "regional_history", "regional_history_exhibits", "modern_polish_history",
        "modern_history", "migration_history", "dark_history", "hidden_history",
        "interactive_history_exhibit", "interactive_exhibit", "interactive_exhibits",
        "temporary_exhibitions", "specialized_museum", "unique_museum_theme",
        "nostalgic_family_museum", "intimate_small_museum", "flagship_museum",
        "enthusiast_museum", "religious_museum", "sports_history_exhibition",
        "gaming_exhibition", "toy_exhibition", "vintage_toys_exhibition",
        "model_exhibition", "lego_exhibition", "mineral_and_gemstone_collection",
        "mineral_collection", "crystal_displays", "gemstones_exhibition",
        "geology_exhibits", "prehistoric_models", "vehicle_collection",
        "console_collection", "matchbox_collection", "classic_cars_collection",
        "automotive_history", "collector_exhibits", "marine_life_exhibits",
        "ossuary_chapel", "baroque_basilica", "marian_sanctuary",
        "historic_gold_mining", "historic_mining_story",
    }),
    # Castles, fortresses, legend/folklore sites, historic islands & quarters.
    # Squares / markets / monuments / statues / old-town layouts are NOT here.
    "history_mystery": frozenset({
        "history_mystery", "historical_site", "castle", "castle_ruins",
        "ruined_castle_tower", "underground", "medieval", "medieval_history",
        "medieval_structure", "medieval_tower", "medieval_defensive_tower",
        "medieval_cellars", "medieval_fortress_ruins", "folklore",
        "ancient_legend_site", "legend_place", "legend_story",
        "literary_legend_trail", "frankenstein_story_route", "regional_heritage",
        "themed_museum", "archaeological_exhibits", "city_history", "fortress",
        "fortress_complex", "mountain_fortress_complex", "mountain_fort_ruins",
        "fortifications", "old_fortifications", "city_fortifications",
        "baroque_fortifications", "baroque_defensive_system", "defensive_architecture",
        "historic_defense_site", "fort", "folklore_museum", "ww2_history",
        "schindler_factory", "polish_history", "modern_polish_history",
        "royal_castle_complex", "medieval_market_history", "early_polish_history",
        "historic_jewish_district", "historic_island", "cathedral_area",
        "gothic_cathedral", "historic_cathedral", "historic_ruins", "ruins_remains",
        "historic_tower", "historic_city_gate", "historic_tunnel_route",
        "knights_history", "aristocratic_history", "regional_history",
        "military_secret", "military_heritage", "naval_history", "maritime_history",
        "dark_history", "hidden_history", "ww2_site", "war_history",
    }),
    # Parks, gardens, spas, thermal & wellness. Broadened heavily (FIX #203)
    # because "relaxation = false despite spa/park plan" was reported everywhere.
    "relaxation": frozenset({
        "relaxation", "relaxation_zone", "spa", "termy", "wellness",
        "wellness_center", "wellness_zone", "wellness_experience", "city_park",
        "green_space", "green_relaxation", "green_fields_leisure", "botanical_garden",
        "peaceful_green_space", "calm_nature_spot", "calm_experience", "arboretum",
        "botanical_collection", "greenhouse", "palm_house", "japanese_garden",
        "thermal_baths", "thermal_pools", "thermal_relaxation", "thermal_relax_focus",
        "thermal_outdoor_pool", "thermal_pool_relax", "quiet_relax_spot",
        "quiet_green_area", "quiet_beach_area", "park", "park_complex", "park_walk",
        "lake_relaxation", "mountain_lake_relaxation", "royal_gardens", "relax_walk",
        "relax_zone", "relax_garden", "relaxing_green_space", "relaxing_walks",
        "water_features", "spa_pools", "spa_town", "spa_park", "spa_park_gardens",
        "spa_promenade", "spa_sauna_complex", "spa_attraction", "spa_experience",
        "spa_tradition", "spa_water_tasting", "spa_resort", "health_resort",
        "health_resort_experience", "health_resort_tradition", "sanatorium",
        "pump_room", "mineral_springs", "mineral_water", "mineral_water_tasting",
        "sauna", "sauna_zone", "jacuzzi", "salt_room", "evening_relax",
        "evening_stroll", "summer_mountain_relax", "garden", "scenic_garden",
        "peaceful_walk", "spa_garden", "resort_park", "landscaped_gardens",
        "landscaped_walks", "oriental_garden", "seaside_relaxation",
        "coastal_relaxation", "peaceful_seaside", "seaside_promenade", "urban_beach",
        "family_relaxation", "short_relax_session", "romantic_walks", "recreation",
        "zdroj", "zdrojowy",
    }),
    "local_food_experience": frozenset({
        "local_food_experience", "regional_cuisine", "local_cuisine", "food_market",
        "culinary_experience", "traditional_food", "restaurant_district",
        "food_hall", "brewery", "culinary_workshop", "vodka_history", "distillery",
        "regional_food", "local_food", "oscypek", "bacowka", "tasting",
        "street_food", "local_products", "gastronomy", "culinary",
        "food_experience", "wine_tasting", "regional_specialties", "market_hall",
        "restaurants_and_cafes", "cafes_and_restaurants", "restaurants_shops",
        "english_pub", "dessert_spot", "scenic_view_dining",
    }),
    "water_attractions": frozenset({
        "water_attractions", "waterfall", "waterfalls", "aquapark", "aqua_park",
        "indoor_aquapark", "water_park", "lake", "river_cruise", "thermal_baths",
        "thermal_pools", "termy", "beach", "marina", "yacht_harbour",
        "multimedia_fountain", "water_show", "fountain_show", "illuminated_fountain_show",
        "water_features", "thermal_outdoor_pool", "thermal_pool_relax", "spa_pools",
        "water_slides", "waterslides", "pools_and_slides", "swimming", "swimming_pool",
        "summer_swimming_spot", "artificial_wave", "lazy_river", "family_swimming_area",
        "family_water_fun", "natural_lake_swimming", "boat_trip", "family_boat_trip",
        "pirate_ship_cruise", "kayak", "kayaking", "rafting", "mountain_river_rafting",
        "sea", "seaside", "sea_adventure", "water_playground", "water_activity",
        "water_reservoir", "underground_waterfall",
    }),
    "underground": frozenset({
        "underground", "cave", "mine", "tunnel", "subterranean", "caves_mines",
        "mining_heritage", "underground_route", "salt_mine", "karst_cave",
        "karst_cave_system", "underground_archaeology", "underground_tourist_route",
        "underground_nature", "underground_corridors", "underground_exploration",
        "underground_history", "underground_project", "underground_waterfall",
        "stalactite_formations", "gold_mine_tunnels", "mining_tunnels",
        "uranium_mine_tunnels", "historic_tunnel_route", "historic_gold_mining",
        "interactive_mining_tour", "medieval_cellars",
    }),
    # Genuine kids attractions. Monuments / interactive-history exhibits / squares
    # are NOT kids attractions (Podziemia Rynku false positive).
    "kids_attractions": frozenset({
        "kids_attractions", "attractions_for_kids", "playground", "theme_park",
        "family_theme_park", "amusement_park", "amusement_area", "family_amusement_area",
        "zoo", "petting_zoo", "mini_zoo", "educational_zoo", "aquarium", "oceanarium",
        "miniature_world", "miniature_landmarks", "fairytale_world", "fairytale_theme",
        "fairytale_trail", "fairy_tale", "storybook_figures", "dinosaur_theme",
        "science_center_kids", "interactive_exhibition_kids", "indoor_playroom",
        "indoor_playground", "indoor_play_zone", "kids_zone", "kids_entertainment",
        "kids_fun", "kids_escape_room", "educational_farm", "farm_animals",
        "animal_interaction", "animal_encounters", "exotic_animals", "bird_park",
        "parrot_house", "lemur_exhibit", "children_animals", "children_activity_zone",
        "feeding_experience", "snow_tubing", "water_slides", "kids_obstacle_course",
        "trampoline_park", "trampoline_arena", "jumping_zone", "indoor_jump_park",
        "rope_park", "adventure_park", "creative_workshops_kids",
        "sensory_experience_kids", "illusion_kids", "family_friendly_animals",
        "family_rides", "family_fun_center", "family_game_zone", "family_attraction",
        "family_friendly_attraction", "family_water_fun", "play_structures",
        "soft_play_area", "soft_play_structures", "dinosaur_park", "fun_park",
        "event_theme_park", "laser_tag_arena", "animals", "aquatic_animals",
        "birds_only", "rabbit_feeding", "close_contact", "water_playground",
    }),
    "attractions_for_kids": frozenset(),  # filled below (alias of kids_attractions)
    "family_favorite": frozenset(),       # filled below (alias of kids_attractions)
    # Genuine active sport / outdoor activity. Zoo / Rynek / museums are NOT sport.
    "active_sport": frozenset({
        "active_sport", "active_tourism", "active_play", "active_seafront",
        "active_recreation", "adventure_park", "forest_adventure_park",
        "forest_adventure", "outdoor_adventure", "group_adventure", "rope_park",
        "rope_courses", "rope_obstacles", "forest_rope_courses", "tree_climbing",
        "zipline", "zip_line", "zipline_challenges", "zipline_routes", "climbing",
        "climbing_wall", "climbing_park", "climbing_spot", "via_ferrata", "bouldering",
        "hiking", "mountain_trails", "trail", "trekking", "cycling", "bike_park",
        "mountain_biking", "kayak", "kayaking", "canoeing", "rafting",
        "mountain_river_rafting", "sup", "surfing", "watersports", "water_sports",
        "sea_adventure", "skiing", "snowboarding", "ski_resort", "mountain_ski_resort",
        "snow_tubing", "sledging", "toboggan", "summer_toboggan", "summer_sled_track",
        "downhill_sledge", "bobsled", "trampoline_park", "quad_atv", "quad_rides",
        "offroad_experience", "paintball", "go_kart", "karting", "obstacle_course",
        "outdoor_challenges", "ninja_park", "adrenaline_experience",
        "adrenaline_attractions", "adrenaline_activity", "adrenaline_fun",
        "outdoor_activity", "sport", "fitness", "fitness_path", "health_trail",
        "golf_course_resort", "horse_riding", "mountain_adventure", "adventure_sport",
    }),
}
_STRONG_BY_PREF["attractions_for_kids"] = _STRONG_BY_PREF["kids_attractions"]
_STRONG_BY_PREF["family_favorite"] = _STRONG_BY_PREF["kids_attractions"]


# Excel/scoring tags that must NOT count toward a preference in trip coverage.
# Retained for the legacy fallback (prefs WITHOUT a strong set) and for
# matched_coverage_tags().
_COVERAGE_DENY: Dict[str, frozenset] = {
    "nature_landscape": frozenset({
        "city_view", "city_views", "panoramic_city_views", "scenic_city_views",
        "riverside_walk", "urban_life", "leisure_space", "modern_bridge",
        "river_crossing", "architecture_feature", "meeting_spot", "tourist_promenade",
        "optical_illusion", "interactive_fun", "fun_photo_spot", "visual_tricks",
        "educational_space",
        "stadium", "sports_venue", "arena", "iconic_architecture", "iconic_landmark",
        "city_symbol", "landmark", "sports_hall", "event_venue",
        "panoramic_view", "panoramic_views", "panoramic_viewpoint",
        "observation_deck", "architecture_icon", "city_landmark",
        "photo_spot", "mermaid_statue", "scenic_photo_spot",
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
        "deptak", "promenade", "historic_old_town_square", "market_square",
        "town_square", "island_park", "riverside_park", "photo_spot",
    }),
    "museum_heritage": frozenset({
        "riverside_walk", "city_views", "urban_life", "leisure_space",
        "optical_illusion", "fun_photo_spot", "visual_tricks",
        "modern_bridge", "river_crossing",
        "memorial", "war_memorial", "tomb", "monument", "statue", "symbol",
        "guard_ceremony", "military_ceremony", "outdoor_memorial",
        "bridge", "historic_bridge", "bastion",
        "historic_old_town_square", "market_square", "town_square", "fountain",
        "neptune_fountain", "gate", "city_gate",
    }),
    "history_mystery": frozenset({
        "city_view", "city_views", "riverside_walk", "urban_life", "leisure_space",
        "botanical_collection", "optical_illusion", "plants", "greenhouse",
        "paintball", "adventure_sport", "extreme_sport", "team_building",
        "adrenaline_attractions", "outdoor_activity", "sports_activity",
        "market_square", "town_square", "main_square", "largest_medieval_square",
        "unesco_city_center", "historic_market_landmark",
    }),
    "relaxation": frozenset({
        "modern_bridge", "river_crossing", "bridge", "historic_bridge",
        "city_views", "city_view", "riverside_walk", "urban_life",
        "architecture_feature", "landmark", "iconic_landmark",
        "historic_old_town_square", "market_square", "town_square", "deptak",
        "fortress", "bastion", "stadium", "sports_venue",
    }),
}


def _norm_tag(t: Any) -> str:
    # FIX #203: many multi-city tags use hyphens (food-hall, local-food,
    # historic-site, water-activity). Normalize to underscores so a single
    # underscore vocabulary matches both spellings.
    return str(t).strip().lower().replace("-", "_")


def excel_tags(poi: Dict[str, Any]) -> Set[str]:
    raw = poi.get("tags_excel")
    if raw:
        return {_norm_tag(t) for t in raw if t and str(t).strip()}
    return {_norm_tag(t) for t in (poi.get("tags") or []) if t and str(t).strip()}


_NATURE_LANDMARK_NAME_DENY = (
    "pałac kultury",
    "pomnik syreny",
    "syrenka warszawska",
    "pkin",
)

_WEAK_HERITAGE_ONLY = frozenset({
    "historic_building", "architecture_heritage",
    "square", "plaza", "church", "cathedral", "basilica", "parish",
})

# Specific named POI denials (belt-and-braces on top of the tag gates).
_COVERAGE_NAME_DENY: Dict[str, tuple] = {
    "museum_heritage": (
        "spodek", "pomnik syreny", "park sensoryczny", "wieża ratuszowa",
        "fontanna neptuna", "dlugi targ", "długi targ",
    ),
    "nature_landscape": (
        "spodek", "rynek", "dlugi targ", "długi targ", "fontanna neptuna",
        "plac zdrojowy", "deptak", "monte cassino", "wieża ratuszowa", "most tumski",
        "ulica", "plac ", "pomnik", "kładka", "most ", "marina", "sky tower",
        "neon side", "fort ", "góra gradowa", "ambersky", "amber sky",
        "stare miasto", "norblin", "wilanów", "taras widokowy",
    ),
    "local_food_experience": (
        "wyspa słodowa", "plac europejski", "deptak", "rynek",
    ),
    "relaxation": (
        "most tumski", "rynek", "fontanna",
    ),
    "history_mystery": (
        "fontanna neptuna", "brama krowia", "pomnik smoka", "kładka",
        "błędne skały", "plac ",
    ),
    "kids_attractions": (
        "podziemia rynku",
    ),
    "active_sport": (
        "zoo", "ogród zoologiczny", "rynek", "muzeum",
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

    # FIX #203: strict allowlist for every audited preference — require a STRONG tag.
    strong = _STRONG_BY_PREF.get(pref)
    if strong is not None:
        if pref == "museum_heritage":
            # A square/church tagged only 'historical_exhibits' + 'historic_building'
            # is not a museum.
            _hit = tags & strong
            if not _hit:
                return False
            if _hit <= {"historical_exhibits"} and (tags & {"historic_building", "architecture_heritage"}):
                return False
            return True
        if pref == "history_mystery":
            if tags & _WEAK_HERITAGE_ONLY and not (tags & strong):
                return False
        return bool(tags & strong)

    # Legacy fallback for any non-audited preference: broad vocabulary minus deny.
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
    strong = _STRONG_BY_PREF.get(pref)
    if strong is not None:
        return sorted(tags & strong)
    from app.domain.scoring.tag_preferences import USER_PREFERENCES_TO_TAGS

    cfg = USER_PREFERENCES_TO_TAGS.get(pref)
    if not cfg:
        return []
    deny = _COVERAGE_DENY.get(pref, frozenset())
    allowed = {str(t).lower() for t in cfg.get("tags", [])} - set(deny)
    return sorted(tags & allowed)
