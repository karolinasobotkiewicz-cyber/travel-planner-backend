"""
SMART_REPLACE similarity scoring for POI replacement.

Day 9 enhancement: Improved POI matching with:
- Category matching (nature → nature, culture → culture)
- Vibes matching (relaxing → relaxing, adventure → adventure)
- Time of day preferences (morning = light, evening = intense)

Scoring weights:
- Category (30%): type_of_attraction match
- Target group (25%): Similar target_groups
- Intensity (20%): Similar intensity level
- Duration (15%): Similar visit duration
- Vibes (10%): activity_style match
"""

from typing import Dict, Any, List, Set, Optional


def find_similar_poi(
    removed_poi: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    used_poi_ids: Set[str],
    user_preferences: Dict[str, Any],
    target_time: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Find most similar POI for SMART_REPLACE.
    
    Args:
        removed_poi: POI being replaced (dict with Excel field names)
        candidates: All available POIs (list of dicts)
        used_poi_ids: Already used POI IDs (set of strings)
        user_preferences: User dict with 'preferences' list
        target_time: Target time for replacement (e.g., "14:30")
        context: Context dict with season, weather, etc.
        
    Returns:
        Best matching POI dict or None if no suitable match
        
    Scoring:
        - Category (30%): type_of_attraction match
        - Target group (25%): Similar target_groups
        - Intensity (20%): Similar intensity level + time_of_day boost
        - Duration (15%): Similar visit duration
        - Vibes (10%): activity_style match
    """
    # Extract target POI attributes (use capital Excel field names)
    target_category = str(removed_poi.get("Type of attraction", "")).lower()
    target_groups_str = str(removed_poi.get("Target group", "")).lower()
    target_intensity = removed_poi.get("fizyczna_intensywnosc", "").lower()
    target_duration = removed_poi.get("time_min", 60)
    target_vibes = str(removed_poi.get("Activity_style", "")).lower()
    
    # Parse target time for time_of_day preferences
    time_of_day = _get_time_of_day(target_time) if target_time else None
    
    best_poi = None
    best_score = -999
    
    for poi in candidates:
        poi_id = poi.get("ID", "")
        
        # Skip if already used
        if poi_id in used_poi_ids:
            continue
        
        # Skip if same as target
        if poi_id == removed_poi.get("ID"):
            continue
        
        # Calculate similarity score
        score = 0
        
        # 1. CATEGORY MATCH (30%) - Most important for semantic similarity
        poi_category = str(poi.get("Type of attraction", "")).lower()
        if poi_category and target_category:
            category_score = _calculate_category_similarity(
                target_category, poi_category
            )
            score += 30 * category_score
        
        # 2. TARGET GROUP MATCH (25%)
        poi_groups_str = str(poi.get("Target group", "")).lower()
        if poi_groups_str and target_groups_str:
            target_groups = set(target_groups_str.split(","))
            poi_groups = set(poi_groups_str.split(","))
            overlap = len(target_groups & poi_groups)
            if overlap > 0:
                score += 25 * (overlap / max(len(target_groups), 1))
        
        # 3. INTENSITY MATCH (20%) with time_of_day boost
        poi_intensity = poi.get("fizyczna_intensywnosc", "").lower()
        if poi_intensity and target_intensity:
            if poi_intensity == target_intensity:
                intensity_score = 1.0
            elif _intensity_similar(target_intensity, poi_intensity):
                intensity_score = 0.5
            else:
                intensity_score = 0
            
            # Time of day boost: morning = light, afternoon = moderate,
            # evening = intense
            if time_of_day:
                intensity_score *= _time_of_day_intensity_boost(
                    poi_intensity, time_of_day
                )
            
            score += 20 * intensity_score
        
        # 4. DURATION MATCH (15%)
        poi_duration = poi.get("time_min", 60)
        duration_diff = abs(poi_duration - target_duration)
        if duration_diff <= 15:  # Within 15 min
            score += 15
        elif duration_diff <= 30:  # Within 30 min
            score += 10
        elif duration_diff <= 60:  # Within 60 min
            score += 5
        
        # 5. VIBES MATCH (10%) - activity_style
        poi_vibes = str(poi.get("Activity_style", "")).lower()
        if poi_vibes and target_vibes:
            vibes_score = _calculate_vibes_similarity(target_vibes, poi_vibes)
            score += 10 * vibes_score
        
        # Update best match
        if score > best_score:
            best_poi = poi
            best_score = score
    
    return best_poi


def _calculate_category_similarity(
    category1: str, category2: str
) -> float:
    """
    Calculate similarity between two categories.
    
    Args:
        category1: First category (e.g., "nature")
        category2: Second category (e.g., "hiking")
        
    Returns:
        Similarity score 0.0-1.0
    """
    # Exact match
    if category1 == category2:
        return 1.0
    
    # Category groupings (similar categories)
    CATEGORY_GROUPS = {
        "nature": ["hiking", "outdoor", "landscape", "mountain", "lake",
                   "trail", "park"],
        "culture": ["museum", "gallery", "historical", "tradition",
                    "architecture", "heritage"],
        "adventure": ["extreme", "sport", "active", "climbing", "skiing"],
        "wellness": ["spa", "thermal", "relax", "bath", "pool"],
        "family": ["kids", "children", "playground", "zoo", "aquarium"],
        "food": ["restaurant", "traditional", "cuisine", "dining"],
    }
    
    # Check if both categories in same group
    for group_categories in CATEGORY_GROUPS.values():
        if category1 in group_categories and category2 in group_categories:
            return 0.7  # High similarity within group
    
    # Check keywords overlap
    cat1_words = set(category1.split())
    cat2_words = set(category2.split())
    overlap = len(cat1_words & cat2_words)
    if overlap > 0:
        return 0.5
    
    return 0.0


def _calculate_vibes_similarity(vibes1: str, vibes2: str) -> float:
    """
    Calculate similarity between activity styles (vibes).
    
    Args:
        vibes1: First activity style (e.g., "active")
        vibes2: Second activity style (e.g., "relax")
        
    Returns:
        Similarity score 0.0-1.0
    """
    # Exact match
    if vibes1 == vibes2:
        return 1.0
    
    # Vibes compatibility matrix
    VIBES_COMPATIBILITY = {
        "active": {"active": 1.0, "balanced": 0.5, "relax": 0.0,
                   "adventure": 0.8, "sport": 0.9},
        "relax": {"relax": 1.0, "balanced": 0.5, "active": 0.0,
                  "wellness": 0.9, "spa": 0.9},
        "balanced": {"balanced": 1.0, "active": 0.5, "relax": 0.5},
        "adventure": {"adventure": 1.0, "active": 0.8, "extreme": 0.9},
        "wellness": {"wellness": 1.0, "relax": 0.9, "spa": 0.9},
    }
    
    # Check compatibility
    if vibes1 in VIBES_COMPATIBILITY:
        return VIBES_COMPATIBILITY[vibes1].get(vibes2, 0.0)
    
    return 0.0


def _intensity_similar(intensity1: str, intensity2: str) -> bool:
    """
    Check if two intensity levels are similar (adjacent levels).
    
    Args:
        intensity1: First intensity (e.g., "lekka")
        intensity2: Second intensity (e.g., "moderowana")
        
    Returns:
        True if adjacent intensity levels
    """
    INTENSITY_MAP = {
        "light": 1,
        "lekka": 1,
        "moderate": 2,
        "moderowana": 2,
        "umiarkowana": 2,
        "intense": 3,
        "intensywna": 3,
        "wysoka": 3,
    }
    
    level1 = INTENSITY_MAP.get(intensity1, 2)
    level2 = INTENSITY_MAP.get(intensity2, 2)
    
    # Adjacent levels (difference of 1)
    return abs(level1 - level2) == 1


def _get_time_of_day(time_str: str) -> str:
    """
    Get time of day category from time string.
    
    Args:
        time_str: Time in format "HH:MM"
        
    Returns:
        "morning", "afternoon", or "evening"
    """
    try:
        hour = int(time_str.split(":")[0])
        if hour < 12:
            return "morning"
        elif hour < 17:
            return "afternoon"
        else:
            return "evening"
    except (ValueError, IndexError):
        return "afternoon"  # Default


def _time_of_day_intensity_boost(
    intensity: str, time_of_day: str
) -> float:
    """
    Calculate boost/penalty for intensity based on time of day.
    
    Morning → prefer light activities
    Afternoon → neutral
    Evening → prefer intense activities (or light/relax for families)
    
    Args:
        intensity: POI intensity level
        time_of_day: "morning", "afternoon", or "evening"
        
    Returns:
        Multiplier 0.8-1.2
    """
    INTENSITY_LEVELS = {
        "light": 1,
        "lekka": 1,
        "moderate": 2,
        "moderowana": 2,
        "intense": 3,
        "intensywna": 3,
    }
    
    level = INTENSITY_LEVELS.get(intensity, 2)
    
    if time_of_day == "morning":
        # Morning: prefer light (1.2x), penalize intense (0.8x)
        if level == 1:
            return 1.2
        elif level == 3:
            return 0.8
        return 1.0
    
    elif time_of_day == "evening":
        # Evening: prefer moderate/intense (1.1x), neutral on light
        if level >= 2:
            return 1.1
        return 1.0
    
    # Afternoon: neutral for all
    return 1.0
