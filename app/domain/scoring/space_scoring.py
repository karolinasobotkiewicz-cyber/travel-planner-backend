"""
Space (indoor/outdoor) scoring module.

Rewards POI that match weather conditions and user preferences:
- Bad weather + indoor POI = bonus
- Good weather + outdoor preference + outdoor POI = bonus
"""


def calculate_space_score(poi, user, context):
    """
    Calculate score based on space (indoor/outdoor) vs weather and preferences.
    
    Args:
        poi: POI dict with 'space' field ("indoor"/"outdoor"/"both")
        user: User dict with 'preferences' list
        context: Context dict with 'weather' (precipitation, etc.)
    
    Returns:
        int: Score bonus (0-15)
    """
    score = 0
    
    poi_space = poi.get("space", "").lower()
    user_prefs = user.get("preferences", [])
    weather = context.get("weather", {})
    has_precipitation = weather.get("precip", False)
    
    # Bad weather + indoor = strong bonus
    if has_precipitation and poi_space == "indoor":
        score += 10
    
    # Good weather + outdoor preference + outdoor POI = bonus
    if not has_precipitation and "outdoor" in user_prefs and poi_space == "outdoor":
        score += 8
    
    # Outdoor preference with "both" POI = small bonus
    if "outdoor" in user_prefs and poi_space == "both":
        score += 3
    
    # Bad weather + outdoor = penalty
    if has_precipitation and poi_space == "outdoor":
        score -= 5
    
    return score
