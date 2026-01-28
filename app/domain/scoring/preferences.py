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
