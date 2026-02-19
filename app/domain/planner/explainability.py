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
    
    BUGFIX (19.02.2026 - UAT Round 2, Issue #6):
    - Changed from popularity_score to crowd_level (actual crowding)
    - Don't say "Low-crowd" for POI with crowd_level >= 2
    - Examples: Morskie Oko (high crowd), Krokiew (high crowd) should NOT get "Low-crowd option"
    
    Args:
        poi: POI data dict with crowd_level (1=low, 2=medium, 3=high)
        user: User dict with crowd_tolerance (0-5)
        
    Returns:
        Reason string if crowd fit is notable, else None
        
    Example:
        "Low-crowd option (fits your comfort level)" - only for crowd_level=1
        "Popular attraction (fits your crowd comfort)" - for crowd_tolerance>=3 + crowd_level=3
    """
    crowd_tolerance = user.get("crowd_tolerance", 2)
    target_group = user.get("target_group", "").lower()
    travel_style = user.get("travel_style", "").lower()
    
    # BUGFIX (19.02.2026 - Issue #6): Use crowd_level instead of popularity_score
    crowd_level_str = str(poi.get("crowd_level", "")).strip()
    try:
        crowd_level = int(crowd_level_str) if crowd_level_str else 0
    except (ValueError, TypeError):
        crowd_level = 0
    
    # Only explain when it's a GOOD fit
    # Low tolerance (0-1) + ACTUALLY low crowd (crowd_level=1) = good match!
    if crowd_tolerance <= 1 and crowd_level == 1:
        return "Low-crowd option (fits your comfort level)"
    
    # Medium tolerance (2): be more subtle about crowd fit
    # Only mention if it's actually relevant to their profile AND truly low-crowd
    if crowd_tolerance == 2 and crowd_level == 1:
        # Don't say "quiet" for friends/adventure profiles
        if target_group == "friends" or travel_style == "adventure":
            return None  # Skip crowd reason for social/active profiles
        # For seniors/couples/relax profiles, mention peaceful aspect
        if target_group in ["seniors", "couples"] or travel_style == "relax":
            return "Peaceful atmosphere"
    
    # High tolerance (3-5) + high crowd (crowd_level=3) = good match
    if crowd_tolerance >= 3 and crowd_level == 3:
        return "Popular attraction (fits your crowd comfort)"
    
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


def _explain_profile_match(
    poi: Dict[str, Any], user: Dict[str, Any]
) -> Optional[str]:
    """
    Generate reason from profile/group fit.
    
    BUGFIX (19.02.2026 - UAT Round 2, Issue #4):
    Add profile-based reasons as per client feedback.
    
    Args:
        poi: POI data dict
        user: User dict with target_group, travel_style
        
    Returns:
        Reason string if profile match is notable, else None
        
    Example:
        "Great for group adventures" (friends + adventure)
        "Perfect for families with kids" (family + kids_attractions match)
    """
    target_group = user.get("target_group", "").lower()
    travel_style = user.get("travel_style", "").lower()
    
    # Friends + Adventure profile
    if target_group == "friends" and travel_style == "adventure":
        poi_tags_str = str(poi.get("tags", "")).lower()
        poi_type = str(poi.get("type", "")).lower()
        
        # Check for group-friendly / adventure indicators
        adventure_indicators = ["trail", "hiking", "adventure", "active", "sport"]
        if any(ind in poi_tags_str or ind in poi_type for ind in adventure_indicators):
            return "Great for group adventures"
    
    # Family + Kids profile
    if target_group == "family":
        poi_tags_str = str(poi.get("tags", "")).lower()
        kids_indicators = ["kids", "children", "family", "playground", "interactive"]
        if any(ind in poi_tags_str for ind in kids_indicators):
            return "Perfect for families with kids"
    
    # Seniors + Relax
    if target_group == "seniors" and travel_style == "relax":
        poi_tags_str = str(poi.get("tags", "")).lower()
        relax_indicators = ["spa", "termy", "wellness", "peaceful", "scenic"]
        if any(ind in poi_tags_str for ind in relax_indicators):
            return "Ideal for relaxed senior travel"
    
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
    
    BUGFIX (19.02.2026 - UAT Round 2, Issue #4):
    - Remove "Quiet, peaceful destination" spam
    - Add profile-based reasons (friends+adventure, family+kids, etc.)
    - Add fallback for empty reasons
    - Ensure no POI has empty why_selected
    
    Scoring signals (from engine.py):
    1. Priority/Must-see (priority_level)
    2. Preference match (tag overlap)
    3. Crowd tolerance fit (popularity vs tolerance)
    4. Budget fit (price vs budget_level)
    5. Travel style match (POI type vs style)
    6. Profile match (target_group + travel_style)
    
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
    - "Low-crowd option (fits your comfort level)"
    - "Budget-friendly (ticket: 15 PLN)"
    - "Cultural experience (matches your style)"
    - "Great for group adventures" (NEW)
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
    
    # Priority 3: Profile match (NEW - target_group + travel_style)
    # BUGFIX (19.02.2026): Add profile-based reasons
    profile_reason = _explain_profile_match(poi, user)
    if profile_reason:
        reasons.append(profile_reason)
    
    # Priority 4: Crowd tolerance fit (scoring signal: popularity vs tolerance)
    crowd_reason = _explain_crowd_fit(poi, user)
    if crowd_reason:
        reasons.append(crowd_reason)
    
    # Priority 5: Budget fit (scoring signal: price vs budget_level)
    budget_reason = _explain_budget_fit(poi, user)
    if budget_reason:
        reasons.append(budget_reason)
    
    # Priority 6: Travel style match (scoring signal: type/tags vs style)
    style_reason = _explain_travel_style_match(poi, user)
    if style_reason:
        reasons.append(style_reason)
    
    # BUGFIX (19.02.2026 - UAT Round 2, Issue #4): Fallback for empty reasons
    # Client requirement: "Każdy POI MUSI mieć ≥1 reason"
    if not reasons:
        reasons.append("Fits your travel plan timing and location")
    
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
