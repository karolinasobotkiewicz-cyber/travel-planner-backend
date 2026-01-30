"""
Type matching scoring module.

Matches POI type with group type and travel style to provide contextual bonuses/penalties.
"""

# Bonus/penalty matrix for group_type + POI type combinations
TYPE_MATCHING_MATRIX = {
    "family_kids": {
        "park_rozrywki": 10,
        "zoo": 10,
        "aquapark": 8,
        "interactive_museum": 8,
        "outdoor_playground": 10,
        "family_attraction": 8,
        # Penalties
        "nightclub": -20,
        "bar": -15,
        "romantic": -10,
        "extreme_sport": -8
    },
    "seniors": {
        "cultural": 8,
        "museum": 8,
        "historical": 8,
        "spa": 10,
        "scenic_viewpoint": 8,
        # Penalties
        "park_rozrywki": -8,
        "extreme_sport": -15,
        "nightclub": -15,
        "intensive_hiking": -10
    },
    "couples": {
        "romantic": 10,
        "spa": 8,
        "fine_dining": 8,
        "cultural": 5,
        "scenic_viewpoint": 8,
        "wine_tasting": 8
    },
    "friends": {
        "adventure": 8,
        "nightlife": 8,
        "sports": 8,
        "bar": 5,
        "party": 8
    },
    "solo": {
        "cultural": 5,
        "museum": 5,
        "cafe": 5,
        "hiking": 5
    }
}

# Travel style bonuses
TRAVEL_STYLE_TYPE_MATRIX = {
    "adventure": {
        "adventure": 10,
        "extreme_sport": 8,
        "hiking": 8,
        "water_sports": 8,
        "zip_line": 10,
        "rock_climbing": 10
    },
    "cultural": {
        "museum": 10,
        "historical": 10,
        "cultural": 10,
        "art_gallery": 8,
        "theater": 8,
        "monument": 8
    },
    "relax": {
        "spa": 10,
        "beach": 8,
        "scenic_viewpoint": 8,
        "park": 5,
        "cafe": 5,
        # Penalties
        "extreme_sport": -10,
        "intensive": -8
    },
    "balanced": {
        # No strong bonuses/penalties, allows variety
    }
}


def calculate_type_matching_score(poi, user, context):
    """
    Calculate score based on POI type vs user group type and travel style.
    
    Args:
        poi: POI dict with 'type' field
        user: User dict with 'target_group' and 'travel_style'
        context: Context dict (not used currently)
    
    Returns:
        int: Score adjustment (-20 to +20)
    """
    score = 0
    
    poi_type = poi.get("type", "").lower()
    group_type = user.get("target_group", "").lower()
    travel_style_raw = user.get("travel_style")
    travel_style = travel_style_raw.lower() if travel_style_raw else ""
    
    # Apply group type matching
    if group_type in TYPE_MATCHING_MATRIX:
        type_bonuses = TYPE_MATCHING_MATRIX[group_type]
        score += type_bonuses.get(poi_type, 0)
    
    # Apply travel style matching
    if travel_style in TRAVEL_STYLE_TYPE_MATRIX:
        style_bonuses = TRAVEL_STYLE_TYPE_MATRIX[travel_style]
        score += style_bonuses.get(poi_type, 0)
    
    return score
