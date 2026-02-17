"""
Quality Checker - validates day quality and POI quality (ETAP 2 Day 5).

Provides quality badges for days and individual POIs to help users understand
what makes a good plan.
"""
from typing import List, Dict, Any


def validate_day_quality(day_plan: Dict[str, Any], pois_data: List[Dict[str, Any]]) -> List[str]:
    """
    Validates overall day quality and returns quality badges.
    
    Args:
        day_plan: Day plan dict with items
        pois_data: Original POI data for enrichment
        
    Returns:
        List of quality badges for the day
        
    Badges:
    - "has_must_see": Day includes at least one must-see attraction (priority >= 11)
    - "good_variety": Mix of different POI types (culture, nature, adventure)
    - "realistic_timing": Total duration fits comfortably in time window
    - "balanced_intensity": Mix of intense and relaxing activities
    """
    badges = []
    
    # Extract attractions from day_plan
    attractions = [item for item in day_plan.get("items", []) if item.get("type") == "attraction"]
    
    if not attractions:
        return badges
    
    # Create poi_id lookup for enrichment
    poi_lookup = {poi.get("id"): poi for poi in pois_data}
    
    # Badge 1: has_must_see (priority >= 11)
    has_must_see = False
    for attr in attractions:
        poi_id = attr.get("poi_id")
        poi = poi_lookup.get(poi_id, {})
        priority = int(poi.get("priority_level", 0)) if poi.get("priority_level") else 0
        if priority >= 11:
            has_must_see = True
            break
    
    if has_must_see:
        badges.append("has_must_see")
    
    # Badge 2: good_variety (at least 2 different types)
    types_present = set()
    for attr in attractions:
        poi_id = attr.get("poi_id")
        poi = poi_lookup.get(poi_id, {})
        poi_type = poi.get("type", "").lower()
        if poi_type:
            types_present.add(poi_type)
    
    if len(types_present) >= 2:
        badges.append("good_variety")
    
    # Badge 3: realistic_timing (attractions fit within day window with buffer)
    total_duration = sum(attr.get("duration_min", 0) for attr in attractions)
    # Standard day: 09:00-19:00 = 600 minutes
    # Subtract lunch (90 min) + transfers (~90 min for 5-6 attractions) = ~420 min available
    # Realistic = total_duration <= 420 minutes (7 hours of actual activities)
    if total_duration <= 420:
        badges.append("realistic_timing")
    
    # Badge 4: balanced_intensity (mix of light and intense)
    intensities = []
    for attr in attractions:
        poi_id = attr.get("poi_id")
        poi = poi_lookup.get(poi_id, {})
        intensity = poi.get("fizyczna_intensywnosc", "").lower()
        if intensity:
            intensities.append(intensity)
    
    # Balanced = has both "light" and ("moderate" or "intense")
    has_light = any(i in ["light", "lekka"] for i in intensities)
    has_intense = any(i in ["moderate", "intense", "moderowana", "intensywna"] for i in intensities)
    
    if has_light and has_intense and len(intensities) >= 3:
        badges.append("balanced_intensity")
    
    return badges


def check_poi_quality(poi: Dict[str, Any], context: Dict[str, Any], user: Dict[str, Any]) -> List[str]:
    """
    Checks individual POI quality and returns quality badges.
    
    BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #6):
    Badges are now deterministic for the same POI + user profile.
    Removed time-dependent badges (e.g., "perfect_timing") to ensure consistency.
    
    Args:
        poi: POI data dict
        context: Context dict (time_of_day, weather, etc.)
        user: User preferences dict
        
    Returns:
        List of quality badges for the POI
        
    Badges (all deterministic based on POI properties + user profile):
    - "must_see": Priority level >= 11 (iconic attractions)
    - "core_attraction": Priority level == 12 (core POI)
    - "weather_resistant": Works well in any weather (indoor or flexible)
    - "family_favorite": Especially good for families (if target_group = family_kids)
    - "budget_friendly": Low cost for budget level 1
    - "premium_experience": High-end attraction (KULIGI, SPA, etc.)
    """
    badges = []
    
    priority = int(poi.get("priority_level", 0)) if poi.get("priority_level") else 0
    
    # Badge: must_see (priority >= 11)
    if priority >= 11:
        badges.append("must_see")
    
    # Badge: core_attraction (priority == 12)
    if priority == 12:
        badges.append("core_attraction")
    
    # BUGFIX (16.02.2026 - Problem #6): Removed "perfect_timing" badge
    # Reason: It's time-dependent (changes based on time_of_day), causing inconsistency
    # The same POI should have same badges regardless of when it's visited
    
    # Badge: weather_resistant (indoor or flexible)
    weather_dep = poi.get("zależność_od_pogody", "").lower()
    if weather_dep in ["indoor", "flexible", "wewnatrz", "elastyczna"]:
        badges.append("weather_resistant")
    
    # Badge: family_favorite (for family_kids group)
    target_group = user.get("target_group", "").lower()
    poi_groups = str(poi.get("target_groups", "")).lower()
    if target_group == "family_kids" and "family" in poi_groups:
        badges.append("family_favorite")
    
    # Badge: budget_friendly (price <= 10 for budget=1)
    budget_level = user.get("budget_level", 2)
    ticket_normal = float(poi.get("cena_bilet_normalny", 0) or 0)
    if budget_level == 1 and ticket_normal <= 10:
        badges.append("budget_friendly")
    
    # Badge: premium_experience (KULIGI, SPAs, high-end)
    poi_name = poi.get("name", "").lower()
    if "kuligi" in poi_name or "termy" in poi_name or "spa" in poi_name:
        badges.append("premium_experience")
    
    return badges
