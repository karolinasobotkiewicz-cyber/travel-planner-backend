# type: ignore
"""Budget scoring"""
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


def calculate_budget_score(poi, user):
    """
    Porownuje budget usera z POI
    -6 punktow za kazdy level powyzej
    """
    user_budget = _safe_int(user.get("budget"), 2)  # default medium
    poi_budget = _safe_int(poi.get("budget_level"), 2)

    delta = poi_budget - user_budget

    # prosty wzor - moze pozniej zmienic na bardziej zaawansowany
    return -6.0 * delta
