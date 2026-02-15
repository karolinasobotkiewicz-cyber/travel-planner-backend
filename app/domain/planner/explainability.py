"""
Explainability - explains why POIs were selected (ETAP 2 Day 5).

Converts technical scoring details into natural language explanations
that users can understand.
"""
from typing import List, Dict, Any


def explain_poi_selection(
    poi: Dict[str, Any],
    context: Dict[str, Any],
    user: Dict[str, Any],
    score: float = 0.0
) -> List[str]:
    """
    Explains why a POI was selected using natural language.
    
    Args:
        poi: POI data dict
        context: Context dict (time_of_day, weather, current_time, etc.)
        user: User preferences dict (target_group, budget, preferences)
        score: Total score (optional, for debugging)
        
    Returns:
        Top 3 reasons (max) why this POI was selected
        
    Examples:
    - "Must-see attraction in Zakopane"
    - "Perfect for couples seeking romantic experiences"
    - "Great for hiking and nature lovers"
    - "Family-friendly with activities for kids"
    - "Budget-friendly option for your trip"
    - "Premium experience worth the splurge"
    - "Works well rain or shine"
    - "Most scenic at this time of day"
    """
    reasons = []
    
    # Priority: priority_level (must-see, core)
    priority = int(poi.get("priority_level", 0)) if poi.get("priority_level") else 0
    if priority == 12:
        reasons.append("Must-see attraction in Zakopane")
    elif priority >= 11:
        reasons.append("Highly recommended by locals")
    
    # Target group match
    target_group = user.get("target_group", "").lower()
    poi_groups = str(poi.get("target_groups", "")).lower()
    
    if target_group == "couples" and "couples" in poi_groups:
        reasons.append("Perfect for couples seeking romantic experiences")
    elif target_group == " family_kids" and "family" in poi_groups:
        reasons.append("Family-friendly with activities for kids")
    elif target_group == "friends" and "friends" in poi_groups:
        reasons.append("Great for groups of friends")
    elif target_group == "seniors" and "seniors" in poi_groups:
        reasons.append("Senior-friendly with comfortable pace")
    elif target_group == "solo" and "solo" in poi_groups:
        reasons.append("Perfect for solo travelers")
    
    # Preferences match
    preferences = user.get("preferences", [])
    poi_tags = str(poi.get("tags", "")).lower()
    poi_type = poi.get("type", "").lower()
    
    matched_prefs = []
    for pref in preferences:
        pref_lower = pref.lower()
        if pref_lower in poi_tags or pref_lower in poi_type:
            matched_prefs.append(pref)
    
    if matched_prefs:
        # Take first 2 preferences
        prefs_text = " and ".join(matched_prefs[:2])
        reasons.append(f"Great for {prefs_text} lovers")
    
    # Budget considerations
    budget_level = user.get("budget_level", 2)
    ticket_normal = float(poi.get("cena_bilet_normalny", 0) or 0)
    
    if budget_level == 1 and ticket_normal <= 10:
        reasons.append("Budget-friendly option for your trip")
    elif budget_level == 3 and ticket_normal >= 50:
        reasons.append("Premium experience worth the splurge")
    
    # Weather resistance
    weather_dep = poi.get("zależność_od_pogody", "").lower()
    if weather_dep in ["indoor", "flexible", "wewnatrz", "elastyczna"]:
        reasons.append("Works well rain or shine")
    
    # Time of day match
    time_of_day = context.get("time_of_day", "").lower()
    poi_timing = poi.get("najlepszy_czas_dnia", "").lower()
    if poi_timing and time_of_day in poi_timing:
        if time_of_day == "morning":
            reasons.append("Best visited in the morning")
        elif time_of_day == "afternoon":
            reasons.append("Perfect afternoon activity")
        elif time_of_day == "evening":
            reasons.append("Most scenic at this time of day")
    
    # Special experiences
    poi_name = poi.get("name", "").lower()
    if "kuligi" in poi_name:
        reasons.append("Unique winter experience you can't miss")
    elif "termy" in poi_name or "spa" in poi_name:
        reasons.append("Perfect for relaxation after a day of exploring")
    elif "muzeum" in poi_name:
        reasons.append("Cultural enrichment and local history")
    elif "góry" in poi_name or "morskie oko" in poi_name or "kościeliska" in poi_name:
        reasons.append("Breathtaking mountain views")
    
    # Return top 3 reasons (prioritize by order added)
    return reasons[:3]


def generate_quality_summary(day_badges: List[str], attraction_count: int) -> str:
    """
    Generates human-readable summary of day quality.
    
    Args:
        day_badges: List of day quality badges
        attraction_count: Number of attractions in day
        
    Returns:
        Natural language summary
        
    Examples:
    - "Well-balanced day with must-see attractions"
    - "Great variety of experiences"
    - "Realistic timing with comfortable pace"
    """
    if "has_must_see" in day_badges and "good_variety" in day_badges:
        return "Well-balanced day with must-see attractions and great variety"
    elif "has_must_see" in day_badges:
        return "Includes iconic must-see attractions"
    elif "good_variety" in day_badges:
        return "Great variety of different experiences"
    elif "realistic_timing" in day_badges:
        return "Comfortable pace with realistic timing"
    elif attraction_count >= 5:
        return "Action-packed day with multiple activities"
    else:
        return "Relaxed day with quality experiences"
