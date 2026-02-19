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

    Logic (BUGFIX 19.02.2026 - UAT Round 2, Issue #5):
        - Top 3 preferences: +15 punktów each (3x boost)
        - Pozostałe preferences: +8 punktów each (1.6x boost)
        - Zwiększone z +5 → pozwala preferencjom konkurować z must-see POI (+25)
        - Jeśli brak preferences: 0 (neutralne)

    Examples:
        >>> user = {"preferences": ["outdoor", "family", "adventure"]}
        >>> poi = {"tags": ["outdoor", "mountain", "hiking"]}
        >>> calculate_preference_score(poi, user)
        15.0  # "outdoor" is in top 3

        >>> user = {"preferences": ["museums", "culture"]}
        >>> poi = {"tags": ["museums", "culture"]}
        >>> calculate_preference_score(poi, user)
        30.0  # Both in top 3: 15 + 15
    """
    score = 0.0

    # Get preferences from user (ordered list)
    user_prefs_list = user.get("preferences", [])
    if not user_prefs_list:
        return 0.0  # Brak preferencji = neutralne

    # Get top 3 preferences
    top_3_prefs = set(user_prefs_list[:3])
    other_prefs = set(user_prefs_list[3:])

    # Get tags from POI
    poi_tags = set(poi.get("tags", []))
    if not poi_tags:
        return 0.0  # POI bez tagów = neutralne

    # BUGFIX (19.02.2026 - UAT Round 2, Issue #5): Weighted preference scoring
    # Top 3 preferences get 3x boost to compete with must-see POI (priority_level=core: +25)
    top_matches = top_3_prefs & poi_tags
    score += len(top_matches) * 15.0  # Was 5.0, now 15.0

    # Other preferences get moderate boost
    other_matches = other_prefs & poi_tags
    score += len(other_matches) * 8.0  # Was 5.0, now 8.0

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
