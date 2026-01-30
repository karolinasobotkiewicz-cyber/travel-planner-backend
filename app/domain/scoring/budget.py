# type: ignore
"""Budget scoring with perception multipliers"""
import math


def _is_nan(x):
    try:
        return isinstance(x, float) and math.isnan(x)
    except (TypeError, ValueError):
        return False


def _safe_float(x, default=0.0):
    try:
        if x is None:
            return default
        if _is_nan(x):
            return default
        s = str(x).strip()
        if s == "" or s.lower() == "nan":
            return default
        return float(s)
    except (TypeError, ValueError):
        return default


def _safe_int(x, default=0):
    return int(round(_safe_float(x, default)))


# Budget perception multipliers (from client feedback 29.01.2026)
PERCEPTION_MULTIPLIERS = {
    # Based on POI type
    "type": {
        "termy": 1.3,
        "aquapark": 1.3,
        "spa": 1.3,
        "park_rozrywki": 1.4,
        "kolejka": 1.4,
        "extreme": 1.5,
        "zip_line": 1.5,
        "bungee": 1.5
    },
    # Based on activity_style field
    "activity_style": {
        "premium": 1.5,
        "luxury": 1.6,
        "extreme": 1.5
    },
    # Based on budget_type field
    "budget_type": {
        "premium": 1.3,
        "expensive": 1.4,
        "luxury": 1.5
    }
}


def calculate_perceived_cost(poi):
    """
    Calculate perceived cost with multipliers based on POI characteristics.
    
    Args:
        poi: POI dict with 'ticket_price', 'type', 'activity_style', 'budget_type'
    
    Returns:
        float: Perceived cost after applying multipliers
    """
    base_price = _safe_float(poi.get("ticket_price", 0), 0)
    
    if base_price == 0:
        return 0
    
    multiplier = 1.0
    
    # Check type (use highest multiplier found)
    poi_type = str(poi.get("type", "")).lower()
    if poi_type in PERCEPTION_MULTIPLIERS["type"]:
        multiplier = max(multiplier, PERCEPTION_MULTIPLIERS["type"][poi_type])
    
    # Check activity_style
    activity_style = str(poi.get("activity_style", "")).lower()
    if activity_style in PERCEPTION_MULTIPLIERS["activity_style"]:
        multiplier = max(multiplier, PERCEPTION_MULTIPLIERS["activity_style"][activity_style])
    
    # Check budget_type
    budget_type = str(poi.get("budget_type", "")).lower()
    if budget_type in PERCEPTION_MULTIPLIERS["budget_type"]:
        multiplier = max(multiplier, PERCEPTION_MULTIPLIERS["budget_type"][budget_type])
    
    return base_price * multiplier


def calculate_budget_score(poi, user):
    """
    Compare user budget with POI using perceived cost (not raw price).
    
    Args:
        poi: POI dict
        user: User dict with 'budget' (0-4 scale or total_budget)
    
    Returns:
        float: Score adjustment based on budget match
    """
    user_budget = _safe_int(user.get("budget"), 2)  # default medium
    poi_budget = _safe_int(poi.get("budget_level"), 2)

    delta = poi_budget - user_budget

    # Base score from budget level delta
    score = -6.0 * delta
    
    # Additional adjustment based on perceived cost
    # If perceived cost is high (multiplier applied), apply small additional penalty
    perceived_cost = calculate_perceived_cost(poi)
    base_price = _safe_float(poi.get("ticket_price", 0), 0)
    
    if base_price > 0:
        cost_ratio = perceived_cost / base_price
        
        # If cost is perceived as much higher (1.4x+), apply extra penalty for budget-conscious users
        if cost_ratio >= 1.4 and user_budget <= 2:  # Low/medium budget users
            score -= 3
        elif cost_ratio >= 1.3 and user_budget == 1:  # Low budget users
            score -= 2
    
    return score
