# type: ignore
"""Crowd tolerance scoring"""
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


def calculate_crowd_score(poi, user):
    """Crowd level vs user tolerance"""
    tolerance = _safe_int(user.get("crowd_tolerance"), 1)  # 0-3
    poi_crowd = _safe_int(poi.get("crowd_level"), 1)

    delta = poi_crowd - tolerance
    # TODO sprawdzic czy -5 to nie za duzo
    return -5.0 * delta
