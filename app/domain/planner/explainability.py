"""
Explainability - explains why POIs were selected (ETAP 2 Day 5).

UAT Problem #7 REFINEMENT (18.02.2026):
- BEFORE: Template-based reasons ("Perfect for couples seeking...")
- AFTER: Scoring signal-based reasons
  ("Matches your museum_heritage preference")
- Client feedback: Generate from SAME scoring signals as engine.py
  (preferences, crowd, budget, style)

Converts technical scoring details into natural language explanations
that users can understand.
"""
from typing import List, Dict, Any, Optional


def _explain_preference_match(
    poi: Dict[str, Any], user: Dict[str, Any]
) -> Optional[str]:
    """
    Generate reason from preference match (scoring signal).
    
    Args:
        poi: POI data dict with tags
        user: User dict with preferences
        
    Returns:
        Reason string if preference matches, else None
        
    Example:
        "Matches your museum_heritage preference"
        "Matches your kids_attractions preference"
    """
    preferences = user.get("preferences", [])
    if not preferences:
        return None
    
    # Get POI tags
    poi_tags_list = poi.get("tags", [])
    
    # Convert tags to list if string
    if isinstance(poi_tags_list, str):
        if poi_tags_list:
            poi_tags_list = [
                t.strip().lower()
                for t in poi_tags_list.split(",")
                if t.strip()
            ]
        else:
            poi_tags_list = []
    
    # Normalize POI tags to lowercase
    poi_tags_normalized = [str(tag).lower() for tag in poi_tags_list]
    
    # Find matched preferences
    matched_prefs = []
    for pref in preferences:
        pref_lower = pref.lower()
        # Check if preference matches any POI tag (exact or substring)
        if any(
            pref_lower in tag or tag in pref_lower
            for tag in poi_tags_normalized
        ):
            matched_prefs.append(pref)
    
    if matched_prefs:
        # Return first matched preference (most relevant)
        pref_text = matched_prefs[0].replace("_", " ")
        return f"Matches your {pref_text} preference"
    
    return None


def _explain_crowd_fit(
    poi: Dict[str, Any], user: Dict[str, Any]
) -> Optional[str]:
    """
    Generate reason from crowd tolerance fit (scoring signal).
    
    Args:
        poi: POI data dict with popularity_score
        user: User dict with crowd_tolerance
        
    Returns:
        Reason string if crowd fit is notable, else None
        
    Example:
        "Low-crowd option (fits your crowd_tolerance: 1)"
    """
    crowd_tolerance = user.get("crowd_tolerance", 2)
    popularity = float(poi.get("popularity_score", 0) or 0)
    
    # Only explain when it's a GOOD fit (low tolerance + low popularity)
    # Low tolerance (0-1) + low popularity (< 5.0) = good match!
    if crowd_tolerance <= 1 and popularity < 5.0:
        return (
            f"Low-crowd option "
            f"(fits your crowd_tolerance: {crowd_tolerance})"
        )
    
    # Medium tolerance (2) + low popularity = also good
    if crowd_tolerance == 2 and popularity < 3.0:
        return "Quiet, peaceful destination"
    
    return None


def _explain_budget_fit(
    poi: Dict[str, Any], user: Dict[str, Any]
) -> Optional[str]:
    """
    Generate reason from budget fit (scoring signal).
    
    Args:
        poi: POI data dict with cena_bilet_normalny
        user: User dict with budget_level
        
    Returns:
        Reason string if budget fit is notable, else None
        
    Example:
        "Budget-friendly (ticket: 15 PLN)"
        "Good value for your budget"
    """
    budget_level = user.get("budget_level", 2)
    ticket_normal = float(poi.get("cena_bilet_normalny", 0) or 0)
    
    # Budget level 1 (tight) + cheap ticket (< 15 PLN)
    if budget_level == 1 and ticket_normal <= 15:
        if ticket_normal == 0:
            return "Free entry (perfect for your budget)"
        return f"Budget-friendly (ticket: {int(ticket_normal)} PLN)"
    
    # Budget level 3 (premium) + premium experience (50+ PLN)
    if budget_level == 3 and ticket_normal >= 50:
        return f"Premium experience (ticket: {int(ticket_normal)} PLN)"
    
    # Medium budget (level 2) + reasonable price (10-30 PLN)
    if budget_level == 2 and 10 <= ticket_normal <= 30:
        return "Good value for your budget"
    
    return None


def _explain_travel_style_match(
    poi: Dict[str, Any], user: Dict[str, Any]
) -> Optional[str]:
    """
    Generate reason from travel style match (scoring signal).
    
    Args:
        poi: POI data dict with type, tags
        user: User dict with travel_style
        
    Returns:
        Reason string if style matches, else None
        
    Example:
        "Cultural experience (matches your style)"
        "Relaxing activity (matches your style)"
    """
    travel_style = user.get("travel_style", "").lower()
    if not travel_style:
        return None
    
    poi_type = poi.get("type", "").lower()
    poi_tags = poi.get("tags", [])
    
    # Convert tags to string for matching
    if isinstance(poi_tags, list):
        tags_str = ",".join([str(t).lower() for t in poi_tags])
    else:
        tags_str = str(poi_tags).lower()
    
    # Cultural style matching
    if travel_style == "cultural":
        cultural_indicators = [
            "museum", "heritage", "history",
            "gallery", "art", "cultural"
        ]
        if any(
            indicator in poi_type or indicator in tags_str
            for indicator in cultural_indicators
        ):
            return "Cultural experience (matches your style)"
    
    # Relax style matching
    if travel_style == "relax":
        relax_indicators = [
            "spa", "termy", "wellness",
            "relax", "peaceful", "scenic_view"
        ]
        if any(
            indicator in poi_type or indicator in tags_str
            for indicator in relax_indicators
        ):
            return "Relaxing activity (matches your style)"
    
    # Active style matching
    if travel_style == "active":
        active_indicators = [
            "trail", "hiking", "adventure",
            "sport", "active", "outdoor"
        ]
        if any(
            indicator in poi_type or indicator in tags_str
            for indicator in active_indicators
        ):
            return "Active adventure (matches your style)"
    
    return None


def explain_poi_selection(
    poi: Dict[str, Any],
    context: Dict[str, Any],
    user: Dict[str, Any],
    score: float = 0.0
) -> List[str]:
    """
    Explains why a POI was selected using natural language.
    
    UAT Problem #7 REFINEMENT (18.02.2026):
    Generate reasons from SCORING SIGNALS, not templates.
    
    Scoring signals (from engine.py):
    1. Priority/Must-see (priority_level)
    2. Preference match (tag overlap)
    3. Crowd tolerance fit (popularity vs tolerance)
    4. Budget fit (price vs budget_level)
    5. Travel style match (POI type vs style)
    
    Args:
        poi: POI data dict
        context: Context dict (time_of_day, weather, current_time, etc.)
        user: User preferences dict (target_group, budget, preferences)
        score: Total score (optional, for debugging)
        
    Returns:
        Top 3 reasons (max) why this POI was selected
        
    Examples (NEW - scoring signal based):
    - "Must-see attraction in Zakopane"
    - "Matches your museum_heritage preference"
    - "Low-crowd option (fits your crowd_tolerance: 1)"
    - "Budget-friendly (ticket: 15 PLN)"
    - "Cultural experience (matches your style)"
    """
    reasons = []
    
    # Priority 1: Must-see / Highly recommended (priority_level)
    priority_val = poi.get("priority_level", 0)
    priority = int(priority_val) if priority_val else 0
    if priority == 12:
        reasons.append("Must-see attraction in Zakopane")
    elif priority >= 11:
        reasons.append("Highly recommended by locals")
    
    # Priority 2: Preference match (scoring signal: tag overlap)
    pref_reason = _explain_preference_match(poi, user)
    if pref_reason:
        reasons.append(pref_reason)
    
    # Priority 3: Crowd tolerance fit (scoring signal: popularity vs tolerance)
    crowd_reason = _explain_crowd_fit(poi, user)
    if crowd_reason:
        reasons.append(crowd_reason)
    
    # Priority 4: Budget fit (scoring signal: price vs budget_level)
    budget_reason = _explain_budget_fit(poi, user)
    if budget_reason:
        reasons.append(budget_reason)
    
    # Priority 5: Travel style match (scoring signal: type/tags vs style)
    style_reason = _explain_travel_style_match(poi, user)
    if style_reason:
        reasons.append(style_reason)
    
    # Return top 3 reasons (most important)
    return reasons[:3]


def generate_quality_summary(
    day_badges: List[str], attraction_count: int
) -> str:
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
