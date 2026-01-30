# type: ignore
"""Crowd tolerance scoring with peak_hours penalty"""
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


def _time_in_range(current_minutes, peak_hours_str):
    """
    Check if current time is within peak hours range.
    
    Args:
        current_minutes: Current time in minutes from midnight
        peak_hours_str: String like "10:00-12:00, 14:00-16:00"
    
    Returns:
        bool: True if current time is in peak hours
    """
    if not peak_hours_str or not isinstance(peak_hours_str, str):
        return False
    
    # Parse peak hours ranges
    ranges = peak_hours_str.split(",")
    
    for range_str in ranges:
        range_str = range_str.strip()
        if "-" not in range_str:
            continue
        
        try:
            start_str, end_str = range_str.split("-")
            start_h, start_m = map(int, start_str.strip().split(":"))
            end_h, end_m = map(int, end_str.strip().split(":"))
            
            start_minutes = start_h * 60 + start_m
            end_minutes = end_h * 60 + end_m
            
            if start_minutes <= current_minutes < end_minutes:
                return True
        except (ValueError, IndexError):
            continue
    
    return False


def calculate_crowd_score(poi, user, current_time_minutes=None):
    """
    Crowd level vs user tolerance + peak_hours penalty.
    
    Args:
        poi: POI dict with 'crowd_level' and 'peak_hours'
        user: User dict with 'crowd_tolerance' (0-3)
        current_time_minutes: Optional current time in minutes for peak_hours check
    
    Returns:
        float: Score adjustment
    """
    tolerance = _safe_int(user.get("crowd_tolerance"), 1)  # 0-3
    poi_crowd = _safe_int(poi.get("crowd_level"), 1)

    delta = poi_crowd - tolerance
    score = -5.0 * delta
    
    # Peak hours penalty (if current time provided)
    if current_time_minutes is not None:
        peak_hours = poi.get("peak_hours", "")
        
        if _time_in_range(current_time_minutes, peak_hours):
            # Apply additional penalty during peak hours based on tolerance
            # Low tolerance = higher penalty
            if tolerance == 0:  # Very low tolerance
                score -= 8
            elif tolerance == 1:  # Low tolerance
                score -= 5
            elif tolerance == 2:  # Medium tolerance
                score -= 3
            # High tolerance (3) = minimal penalty
            else:
                score -= 1
    
    return score
