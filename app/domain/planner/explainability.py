"""
Explainability - explains why POIs were selected (ETAP 2 Day 5).

Converts technical scoring details into natural language explanations
that users can understand.
"""
from typing import List, Dict, Any, Optional


def _generate_style_based_reason(
    travel_style: str,
    poi_type: str,
    target_group: str
) -> Optional[str]:
    """
    Generate dynamic reason based on travel_style + POI type + target group.
    
    UAT Problem #7 fix: Instead of generic "Perfect for couples seeking romantic experiences",
    generate specific reasons like "Cultural museum experience for couples" or
    "Relaxing spa perfect for your group".
    
    Args:
        travel_style: User travel style (cultural, relax, active, balanced)
        poi_type: POI type (museum, termy, trail, restaurant, etc.)
        target_group: User target group (couples, family_kids, friends, etc.)
        
    Returns:
        Dynamic reason string or None if no match
    """
    # Travel style descriptors
    style_map = {
        "cultural": "cultural",
        "relax": "relaxing",
        "active": "adventurous",
        "balanced": "well-rounded"
    }
    
    # POI type descriptors
    type_descriptors = {
        "museum": "museum experience",
        "termy": "spa and wellness",
        "spa": "spa experience",
        "trail": "hiking adventure",
        "restaurant": "dining experience",
        "viewpoint": "scenic experience",
        "winter_experience": "winter activity"
    }
    
    # Target group suffixes
    group_suffix = {
        "couples": "for couples",
        "family_kids": "for families",
        "friends": "for your group",
        "seniors": "at comfortable pace",
        "solo": "for solo exploration"
    }
    
    style_desc = style_map.get(travel_style, "")
    type_desc = None
    
    # Find matching POI type
    for poi_key, desc in type_descriptors.items():
        if poi_key in poi_type:
            type_desc = desc
            break
    
    if not type_desc:
        return None
    
    group_text = group_suffix.get(target_group, "")
    
    # Combine style + type + group
    if style_desc and group_text:
        return f"{style_desc.capitalize()} {type_desc} {group_text}"
    elif style_desc:
        return f"{style_desc.capitalize()} {type_desc}"
    elif group_text:
        return f"{type_desc.capitalize()} {group_text}"
    
    return None


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
    
    # BUGFIX (18.02.2026 - UAT Problem #7):
    # Dynamic why_selected based on preferences + travel_style + POI characteristics
    # BEFORE: Static "Perfect for couples seeking romantic experiences" for all POI
    # AFTER: "Cultural experience matching your museum interests" (dynamic based on actual match)
    
    # Preferences match - validate against actual POI tags
    preferences = user.get("preferences", [])
    poi_tags_list = poi.get("tags", [])
    
    # Convert tags to list if string
    if isinstance(poi_tags_list, str):
        if poi_tags_list:
            poi_tags_list = [t.strip().lower() for t in poi_tags_list.split(",") if t.strip()]
        else:
            poi_tags_list = []
    
    # Normalize POI tags to lowercase
    poi_tags_normalized = [str(tag).lower() for tag in poi_tags_list]
    
    matched_prefs = []
    for pref in preferences:
        pref_lower = pref.lower()
        # Check if preference matches any POI tag (exact or substring)
        if any(pref_lower in tag or tag in pref_lower for tag in poi_tags_normalized):
            matched_prefs.append(pref)
    
    # Get target group and travel style for dynamic messaging
    target_group = user.get("target_group", "").lower()
    travel_style = user.get("travel_style", "").lower()
    poi_type = poi.get("type", "").lower()
    
    # Dynamic target group + preference matching (UAT Problem #7 fix)
    if matched_prefs:
        # Generate dynamic reason based on preference match + target group
        pref_text = matched_prefs[0].replace("_", " ")
        
        # Map preferences to natural language
        pref_mapping = {
            "museum heritage": "museum and heritage",
            "local food experience": "local food",
            "kids attractions": "family activities",
            "nature landscape": "nature and scenery",
            "mountain trails": "mountain hiking"
        }
        pref_text = pref_mapping.get(pref_text, pref_text)
        
        # Add target group context if relevant
        if target_group == "couples":
            reasons.append(f"Matches your {pref_text} interests - perfect for couples")
        elif target_group == "family_kids":
            reasons.append(f"Great {pref_text} experience for families with kids")
        elif target_group == "friends":
            reasons.append(f"Fun {pref_text} activity for your group")
        elif target_group == "seniors":
            reasons.append(f"Comfortable {pref_text} experience at relaxed pace")
        else:
            reasons.append(f"Matches your {pref_text} interests")
    
    # If no preference match, use travel style + POI type
    elif travel_style and target_group:
        style_poi_combo = _generate_style_based_reason(travel_style, poi_type, target_group)
        if style_poi_combo:
            reasons.append(style_poi_combo)
    
    # Fallback to target group match only if no better reason found
    else:
        poi_groups = str(poi.get("target_groups", "")).lower()
        if target_group == "couples" and "couples" in poi_groups:
            reasons.append("Well-suited for couples")
        elif target_group == "family_kids" and "family" in poi_groups:
            reasons.append("Family-friendly experience")
        elif target_group == "friends" and "friends" in poi_groups:
            reasons.append("Great for groups of friends")
        elif target_group == "seniors" and "seniors" in poi_groups:
            reasons.append("Senior-friendly destination")
        elif target_group == "solo" and "solo" in poi_groups:
            reasons.append("Perfect for solo travelers")
    
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
    
    # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #5):
    # Generate special experience reasons ONLY from POI tags, not name substring matching
    # Example: "Dom do góry nogami" has "góry" in name but is NOT a viewpoint
    
    # Special experiences - validate against POI tags
    poi_tags_str = ",".join(poi_tags_normalized) if poi_tags_normalized else ""
    poi_type = poi.get("type", "").lower()
    
    # Winter experiences (kuligi)
    if "winter_experience" in poi_tags_str or "kulig" in poi_type:
        reasons.append("Unique winter experience you can't miss")
    
    # Relaxation (termy/spa)
    elif any(tag in poi_type for tag in ["termy", "spa", "wellness", "thermal"]):
        reasons.append("Perfect for relaxation after a day of exploring")
    
    # Museum/cultural (validate with tags, not just name)
    elif any(tag in poi_tags_str for tag in ["museum", "heritage", "cultural", "historical", "ethnographic"]):
        reasons.append("Cultural enrichment and local history")
    
    # Mountain views (validate with tags: viewpoint/scenic/panorama)
    elif any(tag in poi_tags_str for tag in ["viewpoint", "scenic", "panorama", "mountain_view", "nature_landscape"]):
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
