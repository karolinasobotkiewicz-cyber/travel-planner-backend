"""
Time of day scoring module.

Rewards POI that are visited at their recommended time of day.
"""

def time_to_period(time_str):
    """
    Convert time string to period of day.
    
    Args:
        time_str: Time in "HH:MM" format or minutes as int
    
    Returns:
        str: "morning", "midday", "afternoon", or "evening"
    """
    # Convert to minutes
    if isinstance(time_str, str):
        h, m = map(int, time_str.split(":"))
        minutes = h * 60 + m
    else:
        minutes = time_str
    
    # Map to periods
    if 600 <= minutes < 720:  # 10:00-12:00
        return "morning"
    elif 720 <= minutes < 900:  # 12:00-15:00
        return "midday"
    elif 900 <= minutes < 1080:  # 15:00-18:00
        return "afternoon"
    elif minutes >= 1080:  # 18:00+
        return "evening"
    else:  # before 10:00
        return "early_morning"


def calculate_time_of_day_score(poi, user, context, current_time_minutes):
    """
    Calculate score based on recommended_time_of_day vs current time.
    
    BUGFIX (31.01.2026 - Problem #6): Increased penalties for time mismatches
    - Afternoon POI should NOT be scheduled in midday (14:26 vs 15:00+)
    - Stronger enforcement of recommended_time_of_day
    
    Args:
        poi: POI dict with 'recommended_time_of_day' field
        user: User dict (not used currently)
        context: Context dict (not used currently)
        current_time_minutes: Current time in minutes from midnight
    
    Returns:
        int: Score bonus (0-15) or penalty (-50)
    """
    score = 0
    
    recommended = poi.get("recommended_time_of_day", "").lower()
    
    if not recommended:
        return 0  # No preference
    
    current_period = time_to_period(current_time_minutes)
    
    # Exact match = strong bonus (increased from +10 to +15)
    if recommended == current_period:
        score += 15
    
    # Compatible periods = small bonus
    # Morning/early_morning are compatible
    elif (recommended == "morning" and current_period == "early_morning") or \
         (recommended == "early_morning" and current_period == "morning"):
        score += 5
    
    # BUGFIX (31.01.2026 - Problem #6): Midday/afternoon NO LONGER compatible
    # Termy (afternoon) should NOT be scheduled at 14:26 (midday)
    # Changed from +3 bonus to -15 penalty
    elif (recommended == "midday" and current_period == "afternoon") or \
         (recommended == "afternoon" and current_period == "midday"):
        score -= 15  # CHANGED: was +3, now -15 penalty
    
    # Strong mismatch = severe penalty (e.g., evening attraction in morning)
    # Increased from -45 to -50 to enforce time_of_day recommendations even more strongly
    elif (recommended == "evening" and current_period in ["morning", "early_morning"]) or \
         (recommended in ["morning", "early_morning"] and current_period == "evening"):
        score -= 50
    
    # Moderate mismatch = moderate penalty (increased from -25 to -30)
    elif (recommended == "afternoon" and current_period in ["morning", "early_morning"]) or \
         (recommended == "morning" and current_period in ["afternoon", "evening"]):
        score -= 30
    
    return score
