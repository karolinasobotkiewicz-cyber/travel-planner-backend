# type: ignore
"""Family scoring logic"""


def _safe_str(x):
    return str(x).strip().lower() if x is not None else ""


def calculate_family_score(poi, user):
    """Scoring dla rodzin z dziecmi"""
    if user.get("target_group") != "family_kids":
        return 0.0

    # kids only -> duzy bonus
    if bool(poi.get("kids_only")):
        return 8.0

    target_groups = poi.get("target_groups") or []
    tg = set([_safe_str(x) for x in target_groups])

    # TODO: sprawdzic czy nie za duzy bonus dla family
    base = 6.0 if ("family_kids" in tg or "family" in tg) else -4.0

    # wiek dziecka vs. limity POI
    age = user.get("children_age", None)
    if isinstance(age, (int, float)):
        cmin = poi.get("children_min", None)
        cmax = poi.get("children_max", None)
        if isinstance(cmin, int) and isinstance(cmax, int):
            if cmin <= int(age) <= cmax:
                base += 2.0  # FIXME: moze za malo?

    return base
