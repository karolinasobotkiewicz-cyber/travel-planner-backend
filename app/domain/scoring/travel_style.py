"""
Scoring module - travel style matching.
Dopasowanie travel_style użytkownika do activity_style POI.
"""


def calculate_travel_style_score(poi: dict, user: dict) -> float:
    """
    Dopasowanie stylu podróży do stylu aktywności POI.

    Args:
        poi: POI dictionary z polem "activity_style"
        user: User dictionary z polem "travel_style"

    Returns:
        Score bonus za matching styles

    Logic:
        - Perfect match: +6 punktów
        - Partial match: +3 punkty
        - Balanced zawsze OK: +3 punkty
        - Mismatch: 0 punktów

    Matching rules:
        adventure → active (perfect)
        relax → relax (perfect)
        cultural → balanced (perfect)
        cultural → active (partial)
        balanced → any (partial)
        any → balanced (partial)

    Examples:
        >>> user = {"travel_style": "adventure"}
        >>> poi = {"activity_style": "active"}
        >>> calculate_travel_style_score(poi, user)
        6.0

        >>> user = {"travel_style": "relax"}
        >>> poi = {"activity_style": "active"}
        >>> calculate_travel_style_score(poi, user)
        0.0
    """
    score = 0.0

    # Get travel_style from user (default: balanced)
    user_style = user.get("travel_style", "balanced")
    if not user_style:
        user_style = "balanced"

    # Get activity_style from POI (default: balanced)
    poi_style = poi.get("activity_style", "balanced")
    if not poi_style:
        poi_style = "balanced"

    # Perfect matches
    if user_style == "adventure" and poi_style == "active":
        return 6.0
    if user_style == "relax" and poi_style == "relax":
        return 6.0
    if user_style == "cultural" and poi_style == "balanced":
        return 6.0

    # Partial matches
    if user_style == "cultural" and poi_style == "active":
        return 3.0
    if user_style == "balanced":
        return 3.0  # Balanced user OK z wszystkim
    if poi_style == "balanced":
        return 3.0  # Balanced POI OK z wszystkim

    # Mismatch
    return 0.0
