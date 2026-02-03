# type: ignore
"""
Target Group Matching - Hard Filter + Scoring.

Feedback klientki (03.02.2026):
- Target group powinno działać jako HARD FILTER, nie tylko soft scoring
- Jeśli user.group NOT IN poi.target_group → EXCLUDE
"""


def _safe_str(x):
    return str(x).strip().lower() if x is not None else ""


def should_exclude_by_target_group(poi: dict, user: dict) -> bool:
    """
    Hard filter: Czy POI powinno być wykluczone z powodu target_group mismatch?
    
    Logic (Feedback klientki - 03.02.2026):
    - Jeśli POI ma target_groups określone, a user.group NIE jest w liście → EXCLUDE
    - Jeśli POI nie ma target_groups → ALLOW (neutralne dla wszystkich)
    
    Przykłady wykluczeń:
    - seniors → brak kids_only attractions
    - friends → brak kids_only attractions
    - couple → brak atrakcji stricte dziecięcych
    - solo → brak kids_only attractions
    
    Args:
        poi: POI dict z "target_groups" (list) i "kids_only" (bool)
        user: User dict z "target_group" (string)
    
    Returns:
        True jeśli POI powinno być wykluczone, False w przeciwnym razie
    
    Examples:
        >>> poi = {"kids_only": True, "target_groups": ["family_kids"]}
        >>> user = {"target_group": "seniors"}
        >>> should_exclude_by_target_group(poi, user)
        True
        
        >>> poi = {"target_groups": ["solo", "couples"]}
        >>> user = {"target_group": "seniors"}
        >>> should_exclude_by_target_group(poi, user)
        True
        
        >>> poi = {"target_groups": ["seniors", "solo", "couples"]}
        >>> user = {"target_group": "seniors"}
        >>> should_exclude_by_target_group(poi, user)
        False
    """
    user_group = _safe_str(user.get("target_group", ""))
    
    # Brak grupy użytkownika → neutralne
    if not user_group:
        return False
    
    # Kids_only = hard exclude dla grup nie-family
    if bool(poi.get("kids_only")) and user_group not in ["family_kids", "family"]:
        return True
    
    # Sprawdź target_groups POI
    target_groups = poi.get("target_groups")
    
    # POI bez target_groups → neutralne, dostępne dla wszystkich
    if not target_groups:
        return False
    
    # Normalizacja do set
    tg = set([_safe_str(x) for x in target_groups])
    
    # Jeśli user_group NIE jest w target_groups POI → EXCLUDE
    if user_group not in tg:
        return True
    
    return False


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
