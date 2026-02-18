"""
Tag Preference Scoring Module (CLIENT DATA UPDATE 05.02.2026)

Maps 9 frontend user preferences to POI tags and calculates bonus scores.
Based on client documentation (Preferencje z frontu-tagi.docx).

Scoring:
- Type match: +20-25 points
- Tag match: +15 points per matching tag
- No penalty for missing preferences (backward compatible)
"""

from typing import List, Dict, Any

# CLIENT DATA UPDATE (05.02.2026): Frontend preferences → POI tags mapping
USER_PREFERENCES_TO_TAGS = {
    "attractions_for_kids": {
        "type_match": ["kids_attractions", "theme_park", "zoo_other"],
        "type_bonus": 30,
        "tags": [
            "playground",
            "interactive_exhibition_kids",
            "petting_zoo",
            "farm_animals",
            "feeding_experience",
            "miniature_world",
            "fairytale_world",
            "illusion_kids",
            "aquatic_playground",
            "adventure_playground",
            "trampoline_park",
            "family_entertainment",
        ],
        "tag_bonus": 25,
    },
    "theme_parks": {
        "type_match": ["theme_park", "amusement_park"],
        "type_bonus": 35,
        "tags": [
            "dinosaur_park",
            "adventure_park",
            "water_park",
            "trampoline_park",
            "rope_park",
            "family_entertainment",
            "interactive_exhibits",
            "amusement_rides",
        ],
        "tag_bonus": 25,
    },
    "active_sport": {
        "type_match": ["active_sport", "adventure_sport"],
        "type_bonus": 30,
        "tags": [
            "skiing",
            "snowboarding",
            "cross_country_skiing",
            "sledding",
            "ice_skating",
            "tubing",
            "rope_park",
            "climbing",
            "via_ferrata",
            "hiking",
            "mountain_trails",
            "alpine_activities",
            "zipline",
            "off_road",
        ],
        "tag_bonus": 25,
    },
    "museums_heritage": {
        "type_match": ["museum", "heritage_site", "cultural_attraction"],
        "type_bonus": 30,
        "tags": [
            "local_history",
            "mountain_culture",
            "regional_heritage",
            "traditional_architecture",
            "ethnographic_museum",
            "themed_museum",
            "historical_mansion",
            "art_gallery",
            "interactive_museum",
            "educational_exhibition",
        ],
        "tag_bonus": 25,
    },
    # ALIAS for frontend compatibility (18.02.2026 UAT fix)
    "museum_heritage": {
        "type_match": ["museum", "heritage_site", "cultural_attraction"],
        "type_bonus": 30,
        "tags": [
            "local_history",
            "mountain_culture",
            "regional_heritage",
            "traditional_architecture",
            "ethnographic_museum",
            "themed_museum",
            "historical_mansion",
            "art_gallery",
            "interactive_museum",
            "educational_exhibition",
        ],
        "tag_bonus": 25,
    },
    "nature_landscapes": {
        "type_match": ["nature_outdoor", "scenic_viewpoint"],
        "type_bonus": 30,
        "tags": [
            "mountain_viewpoint",
            "scenic_panorama",
            "hiking",
            "mountain_trails",
            "natural_landscape",
            "waterfall",
            "alpine_valley",
            "mountain_lake",
            "botanical_garden",
            "nature_reserve",
            "gorge",
            "forest_trail",
        ],
        "tag_bonus": 25,
    },
    "water_attractions": {
        "type_match": ["water_wellness", "aquapark"],
        "type_bonus": 30,
        "tags": [
            "thermal_baths",
            "hot_springs",
            "aquapark_slides",
            "geothermal_pools",
            "spa_wellness",
            "relaxation_pools",
            "waterfall_pools",
            "aquatic_playground",
            "year_round",
        ],
        "tag_bonus": 25,
    },
    "castles_palaces": {
        "type_match": ["castle", "palace", "heritage_site"],
        "type_bonus": 35,
        "tags": [
            "medieval_castle",
            "castle_ruins",
            "fortification",
            "historical_mansion",
            "renaissance_architecture",
            "gothic_architecture",
            "royal_residence",
        ],
        "tag_bonus": 25,
    },
    "caves_mines": {
        "type_match": ["cave", "mine", "underground_attraction"],
        "type_bonus": 35,
        "tags": [
            "limestone_cave",
            "underground_tour",
            "salt_mine",
            "mining_heritage",
            "geological_formation",
            "spelunking",
            "underground_chapel",
            "crystal_formations",
        ],
        "tag_bonus": 25,
    },
    "relax_wellness": {
        "type_match": ["water_wellness", "spa"],
        "type_bonus": 30,
        "tags": [
            "thermal_baths",
            "hot_springs",
            "spa_wellness",
            "relaxation_pools",
            "geothermal_pools",
            "year_round",
            "massage",
            "sauna",
            "jacuzzi",
        ],
        "tag_bonus": 25,
    },
    "must_see_only": {
        "type_match": [],  # No specific type - applies to all POI
        "type_bonus": 0,
        "tags": [
            "must_see",  # Must-see attractions marked in POI data
        ],
        "tag_bonus": 25,  # Higher bonus for must-see filtering
    },
    # UAT FIX (18.02.2026): Missing preferences from Test 02, 04
    "local_food_experience": {
        "type_match": ["restaurant", "food_experience", "cultural_attraction"],
        "type_bonus": 30,
        "tags": [
            "local_cuisine",
            "regional_food",
            "traditional_restaurant",
            "bacówka",
            "highlander_cuisine",
            "food_tasting",
            "local_specialties",
            "mountain_food",
            "oscypek",
            "regional_dishes",
        ],
        "tag_bonus": 25,
    },
    "history_mystery": {
        "type_match": [
            "museum",
            "heritage_site",
            "cultural_attraction",
            "underground_attraction",
        ],
        "type_bonus": 35,  # Higher bonus for niche preference
        "tags": [
            "local_history",
            "regional_heritage",
            "historical_mansion",
            "legends",
            "folklore",
            "mystery",
            "underground_tour",
            "hidden_gem",
            "secret_history",
            "unexplored",
            "discovery",
        ],
        "tag_bonus": 25,
    },
}


def calculate_tag_preference_score(
    poi: Dict[str, Any], user_preferences: List[str]
) -> int:
    """
    Calculate bonus score based on matching user preferences to POI tags.
    
    Args:
        poi: Normalized POI dict with 'tags' and 'type' fields
        user_preferences: List of preference strings
            (e.g., ["attractions_for_kids", "water_attractions"])
    
    Returns:
        Total bonus score (0 if no preferences or no matches)
    
    CLIENT DATA UPDATE (05.02.2026): No penalty for missing preferences.
    Backward compatible - returns 0 if user has no preferences.
    """
    if not user_preferences:
        return 0
    
    total_bonus = 0
    poi_tags = poi.get("tags", [])
    poi_type = poi.get("type", "").lower()
    
    for pref in user_preferences:
        if pref not in USER_PREFERENCES_TO_TAGS:
            continue
        
        pref_config = USER_PREFERENCES_TO_TAGS[pref]
        
        # Type match bonus
        if poi_type in pref_config["type_match"]:
            total_bonus += pref_config["type_bonus"]
        
        # Tag match bonus (can stack multiple tags)
        matching_tags = set(poi_tags) & set(pref_config["tags"])
        total_bonus += len(matching_tags) * pref_config["tag_bonus"]
    
    return total_bonus


def get_preference_details(preference: str) -> Dict[str, Any]:
    """
    Get detailed configuration for a specific preference.
    
    Args:
        preference: Preference key (e.g., "attractions_for_kids")
    
    Returns:
        Preference config dict or None if not found
    """
    return USER_PREFERENCES_TO_TAGS.get(preference)


def get_all_preferences() -> List[str]:
    """
    Get list of all supported preference keys.
    
    Returns:
        List of preference strings
    """
    return list(USER_PREFERENCES_TO_TAGS.keys())
