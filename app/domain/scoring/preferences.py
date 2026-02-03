"""
Scoring module - preference matching.
Bonus za matching user preferences z POI tags.
"""


def calculate_preference_score(poi: dict, user: dict) -> float:
    """
    Dopasowanie preferencji użytkownika do POI tags.

    Args:
        poi: POI dictionary z polem "tags" (list)
        user: User dictionary z polem "preferences" (list)

    Returns:
        Score bonus za matching tags

    Logic:
        - Za każdy matching tag: +5 punktów
        - Jeśli brak preferences: 0 (neutralne)

    Examples:
        >>> user = {"preferences": ["outdoor", "family"]}
        >>> poi = {"tags": ["outdoor", "mountain", "hiking"]}
        >>> calculate_preference_score(poi, user)
        5.0

        >>> user = {"preferences": ["outdoor", "family"]}
        >>> poi = {"tags": ["museums", "culture"]}
        >>> calculate_preference_score(poi, user)
        0.0
    """
    score = 0.0

    # Get preferences from user
    user_prefs = set(user.get("preferences", []))
    if not user_prefs:
        return 0.0  # Brak preferencji = neutralne

    # Get tags from POI
    poi_tags = set(poi.get("tags", []))
    if not poi_tags:
        return 0.0  # POI bez tagów = neutralne

    # Count matching tags
    matches = user_prefs & poi_tags
    score += len(matches) * 5.0

    return score


def calculate_priority_bonus(poi: dict, user: dict) -> float:
    """
    Bonus za priority_level POI (FIX #6 + Feedback 03.02.2026).

    Args:
        poi: POI dictionary z polem "priority_level" (core/secondary/optional)
        user: User dictionary (nie wykorzystywane, ale zgodne z konwencją)

    Returns:
        Score bonus za priority_level

    Logic (wzmocnione po feedbacku klientki):
        - core: +25 punktów (MUST-SEE atrakcje - Wielka Krokiew, Muzeum Tatrzańskie)
        - secondary: +10 punktów (ważne atrakcje)
        - optional: 0 punktów (wypełniacze, gap filling)
        - brak/unknown: 0 punktów

    Limity dzienne (enforced in engine.py):
        - core: 1-2 per day (core_min, core_max)
        - secondary: 2-4 per day
        - optional: fallback only

    Examples:
        >>> poi = {"priority_level": "core"}
        >>> calculate_priority_bonus(poi, {})
        25.0

        >>> poi = {"priority_level": "secondary"}
        >>> calculate_priority_bonus(poi, {})
        10.0

        >>> poi = {"priority_level": "optional"}
        >>> calculate_priority_bonus(poi, {})
        0.0
    """
    priority = str(poi.get("priority_level", "")).strip().lower()
    
    if priority == "core":
        return 25.0  # Changed from 30 to 25 (klientka)
    elif priority == "secondary":
        return 10.0
    else:
        return 0.0  # optional lub brak
