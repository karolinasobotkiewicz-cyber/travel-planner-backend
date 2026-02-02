# type: ignore
"""Family scoring logic + Target Group Matching (FIX #8 - 02.02.2026)"""


def _safe_str(x):
    return str(x).strip().lower() if x is not None else ""


def calculate_family_score(poi, user):
    """
    Scoring dla target_group matching - wszystkie grupy (FIX #8).
    
    Logic:
    - family_kids: Poprzednia logika (kids_only +8, matching +6, -4 za brak)
    - Inne grupy (seniors, solo, couples, friends):
        * Perfect match: +20
        * Mismatch/brak: -10
        * Neutral (brak target_groups): 0
    
    Returns:
        Score bonus/penalty za dopasowanie target_group
    """
    user_group = str(user.get("target_group", "")).strip().lower()
    
    # FAMILY_KIDS - LEGACY LOGIC (from old code)
    if user_group == "family_kids":
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
    
    # FIX #8: Scoring dla innych grup (seniors, solo, couples, friends)
    if not user_group:
        return 0.0  # Brak grupy = neutralne
    
    target_groups = poi.get("target_groups") or []
    if not target_groups:
        return 0.0  # POI bez target_groups = neutralne dla wszystkich
    
    # Normalizacja POI target_groups do set
    tg = set([_safe_str(x) for x in target_groups])
    
    # Perfect match: +20
    if user_group in tg:
        return 20.0
    
    # Mismatch: -10 (POI ma inne grupy, nie pasuje)
    return -10.0
