# type: ignore
"""Body state transitions - zimno/cieplo/neutral"""


def _safe_str(x):
    return str(x).strip().lower() if x is not None else ""


def _is_relax(poi):
    """Check if POI is relax type (spa, termy, etc)"""
    name = _safe_str(poi.get("name"))
    poi_type = _safe_str(poi.get("type"))
    tags = set([_safe_str(x) for x in (poi.get("tags") or [])])

    return (
        any(k in name for k in ["termy", "spa", "basen", "sauna"])
        or ("relax" in tags)
        or ("water" in tags)
        or ("spa" in poi_type)
    )


def _is_cold_exp(poi):
    """Outdoor zimne experience (kulig, outdoor high intensity)"""
    name = _safe_str(poi.get("name"))
    tags = set([_safe_str(x) for x in (poi.get("tags") or [])])

    if "kulig" in name or "kulig" in tags:
        return True

    return poi.get("space") == "outdoor" and poi.get("intensity") in (
        "medium",
        "high",
    )


def calculate_body_transition_score(poi, current_state):
    """
    Scoring based on body state transitions
    warm -> cold = bad (-10)
    cold -> relax = good (+8)
    """
    if current_state == "warm" and _is_cold_exp(poi):
        return -10.0

    if current_state == "cold" and _is_relax(poi):
        return +8.0

    return 0.0


def get_next_body_state(poi, current_state):
    """Determine next body state after visiting POI"""
    if _is_relax(poi):
        return "warm"
    if _is_cold_exp(poi):
        return "cold"
    return "neutral"  # default
