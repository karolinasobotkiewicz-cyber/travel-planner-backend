"""
Intensity scoring module with hard rules and soft scoring.

Feedback klientki (03.02.2026):
- Hard rules: Wykluczaj POI jeśli intensity konfliktuje z grupą
- Soft scoring: Różne wagi dla różnych grup
"""


def should_exclude_by_intensity(poi: dict, user: dict) -> bool:
    """
    Hard rule: Czy POI powinno być wykluczone z powodu intensity?
    
    Rules:
    1. Seniorzy + high intensity → EXCLUDE
    2. Rodzina z dziećmi (age < 10) + high intensity → EXCLUDE
    
    Args:
        poi: POI dict z polem "intensity" (low/medium/high)
        user: User dict z "target_group" i "children_age"
    
    Returns:
        True jeśli POI powinno być wykluczone, False w przeciwnym razie
    
    Examples:
        >>> poi = {"intensity": "high"}
        >>> user = {"target_group": "seniors"}
        >>> should_exclude_by_intensity(poi, user)
        True
        
        >>> poi = {"intensity": "high"}
        >>> user = {"target_group": "family_kids", "children_age": 7}
        >>> should_exclude_by_intensity(poi, user)
        True
        
        >>> poi = {"intensity": "medium"}
        >>> user = {"target_group": "seniors"}
        >>> should_exclude_by_intensity(poi, user)
        False
    """
    intensity = str(poi.get("intensity", "")).strip().lower()
    target_group = str(user.get("target_group", "")).strip().lower()
    
    # Rule 1: Seniorzy + high intensity
    if target_group == "seniors" and intensity == "high":
        return True
    
    # Rule 2: Rodzina z małymi dziećmi (< 10 lat) + high intensity
    if target_group == "family_kids" and intensity == "high":
        children_age = user.get("children_age")
        if isinstance(children_age, (int, float)) and children_age < 10:
            return True
    
    return False


def calculate_intensity_score(poi: dict, user: dict) -> float:
    """
    Soft scoring - dopasowanie intensity do grupy docelowej.
    
    Wagi zgodnie z feedbackiem klientki (03.02.2026):
    
    Seniorzy:
    - low: +15
    - medium: +5
    - high: -30 (nie powinno wystąpić przez hard rule)
    
    Rodzina z dziećmi:
    - low: +10
    - medium: +15
    - high: -20 (nie powinno wystąpić przez hard rule dla age < 10)
    
    Znajomi (friends):
    - medium: +15
    - high: +10
    - low: 0
    
    Para (couple):
    - medium: +15
    - low: +10
    
    Solo:
    - medium: +15
    - high: +10
    - low: +5
    
    Args:
        poi: POI dict z polem "intensity"
        user: User dict z "target_group"
    
    Returns:
        Score bonus/penalty
    """
    intensity = str(poi.get("intensity", "")).strip().lower()
    target_group = str(user.get("target_group", "")).strip().lower()
    
    if not intensity or not target_group:
        return 0.0
    
    # Seniorzy
    if target_group == "seniors":
        if intensity == "low":
            return 15.0
        elif intensity == "medium":
            return 5.0
        elif intensity == "high":
            return -30.0  # Hard rule powinno to wykluczyć
    
    # Rodzina z dziećmi
    elif target_group == "family_kids":
        if intensity == "low":
            return 10.0
        elif intensity == "medium":
            return 15.0
        elif intensity == "high":
            return -20.0  # Hard rule dla age < 10
    
    # Znajomi
    elif target_group == "friends":
        if intensity == "medium":
            return 15.0
        elif intensity == "high":
            return 10.0
        elif intensity == "low":
            return 0.0
    
    # Para
    elif target_group == "couples":
        if intensity == "medium":
            return 15.0
        elif intensity == "low":
            return 10.0
        else:
            return 0.0
    
    # Solo
    elif target_group == "solo":
        if intensity == "medium":
            return 15.0
        elif intensity == "high":
            return 10.0
        elif intensity == "low":
            return 5.0
    
    return 0.0
