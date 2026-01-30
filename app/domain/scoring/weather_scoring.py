"""
Weather dependency scoring module.

Applies penalties/bonuses based on POI weather dependency and current weather conditions.
"""


def calculate_weather_dependency_score(poi, user, context):
    """
    Calculate score based on weather_dependency field vs current weather.
    
    Args:
        poi: POI dict with 'weather_dependency' ("high"/"medium"/"low"/"none")
        user: User dict (not used currently)
        context: Context dict with 'weather' (precipitation, temperature, etc.)
    
    Returns:
        int: Score adjustment (-15 to +5)
    """
    score = 0
    
    dependency = poi.get("weather_dependency", "").lower()
    weather = context.get("weather", {})
    has_precipitation = weather.get("precip", False)
    temperature = weather.get("temperature", 15)  # Default 15°C
    
    # No weather dependency = always good
    if dependency == "none" or not dependency:
        return 0
    
    # High dependency = heavily affected by bad weather
    if dependency == "high":
        if has_precipitation:
            score -= 15  # Strong penalty
        elif temperature < 5:  # Very cold
            score -= 10
        else:
            score += 5  # Good weather bonus for outdoor activities
    
    # Medium dependency = moderately affected
    elif dependency == "medium":
        if has_precipitation:
            score -= 8
        elif temperature < 5:
            score -= 5
        else:
            score += 3
    
    # Low dependency = slightly affected
    elif dependency == "low":
        if has_precipitation:
            score -= 3
        elif temperature < 0:  # Only extreme cold
            score -= 2
    
    return score
