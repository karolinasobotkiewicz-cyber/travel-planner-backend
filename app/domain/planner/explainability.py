"""
Explainability - explains why POIs were selected (ETAP 2 Day 5).

FIX #251: all why_selected strings are Polish (client: English reasons rejected).
"""
from typing import List, Dict, Any, Optional


_PREF_PL = {
    "museum_heritage": "muzea i dziedzictwo",
    "history_mystery": "historię i tajemnice",
    "kids_attractions": "atrakcje dla dzieci",
    "nature_landscape": "naturę i krajobraz",
    "relaxation": "relaks",
    "active_sport": "aktywny wypoczynek",
    "local_cuisine": "lokalną kuchnię",
    "nightlife": "życie nocne",
    "shopping": "zakupy",
    "art_culture": "sztukę i kulturę",
    "panoramic_views": "widoki panoramy",
    "family_fun": "zabawę rodzinną",
}


def _pref_label_pl(pref: str) -> str:
    return _PREF_PL.get(pref, pref.replace("_", " "))


def _explain_preference_match(
    poi: Dict[str, Any], user: Dict[str, Any]
) -> Optional[str]:
    preferences = user.get("preferences", [])
    if not preferences:
        return None

    from app.domain.scoring.preference_coverage import poi_covers_preference_report

    for pref in preferences:
        if poi_covers_preference_report(poi, pref):
            return f"Pasuje do Twojej preferencji: {_pref_label_pl(pref)}"

    return None


def _explain_crowd_fit(
    poi: Dict[str, Any], user: Dict[str, Any]
) -> Optional[str]:
    crowd_tolerance = user.get("crowd_tolerance", 2)
    target_group = user.get("target_group", "").lower()
    travel_style = user.get("travel_style", "").lower()

    crowd_level_str = str(poi.get("crowd_level", "")).strip()
    try:
        crowd_level = int(crowd_level_str) if crowd_level_str else 0
    except (ValueError, TypeError):
        crowd_level = 0

    try:
        _popularity = float(str(poi.get("popularity_score", 0) or 0))
    except (ValueError, TypeError):
        _popularity = 0.0
    _is_very_popular = _popularity >= 4.0

    if crowd_tolerance <= 1 and crowd_level == 1:
        if _is_very_popular:
            return None
        return "Spokojne miejsce (pasuje do Twojej tolerancji tłoku)"

    if crowd_tolerance == 2 and crowd_level == 1:
        if _is_very_popular:
            return None
        if target_group == "friends" or travel_style == "adventure":
            return None

        poi_tags_str = str(poi.get("tags", "")).lower()
        poi_name = str(poi.get("name", "")).lower()
        winter_indicators = ["kulig", "sleigh", "horse_riding", "seasonal_activity"]
        if target_group == "couples" and any(
            ind in poi_name or ind in poi_tags_str for ind in winter_indicators
        ):
            return None

        if target_group in ["seniors", "couples"] or travel_style == "relax":
            return "Spokojna atmosfera"

    if crowd_tolerance >= 3 and crowd_level == 3:
        return "Popularna atrakcja (pasuje do Twojej tolerancji tłoku)"

    return None


def _explain_budget_fit(
    poi: Dict[str, Any], user: Dict[str, Any]
) -> Optional[str]:
    budget_level = user.get("budget_level", 2)
    ticket_normal = float(poi.get("cena_bilet_normalny", 0) or 0)

    if budget_level == 1 and ticket_normal <= 15:
        if ticket_normal == 0:
            return "Wstęp wolny (idealnie pod Twój budżet)"
        return f"Przyjazne budżetowi (bilet: {int(ticket_normal)} PLN)"

    if budget_level == 3 and ticket_normal >= 50:
        return f"Premium doświadczenie (bilet: {int(ticket_normal)} PLN)"

    if budget_level == 2 and 10 <= ticket_normal <= 30:
        return "Dobry stosunek jakości do ceny"

    return None


def _explain_travel_style_match(
    poi: Dict[str, Any], user: Dict[str, Any]
) -> Optional[str]:
    travel_style = user.get("travel_style", "").lower()
    if not travel_style:
        return None

    preferences = [str(p).lower() for p in (user.get("preferences") or [])]

    from app.domain.scoring.preference_coverage import poi_covers_preference_report

    poi_tags = poi.get("tags", [])

    if isinstance(poi_tags, list):
        tags_str = ",".join([str(t).lower() for t in poi_tags])
    else:
        tags_str = str(poi_tags).lower()

    if travel_style == "cultural":
        poi_name = str(poi.get("name", "")).lower()
        local_tradition_indicators = [
            "kulig", "sleigh", "horse_riding", "seasonal_activity",
            "local_tradition", "folklore", "highland",
        ]
        if any(
            indicator in poi_name or indicator in tags_str
            for indicator in local_tradition_indicators
        ):
            return "Lokalna tradycja (doświadczenie kulturowe)"

        if (
            poi_covers_preference_report(poi, "museum_heritage")
            or poi_covers_preference_report(poi, "history_mystery")
        ):
            return "Doświadczenie kulturowe (pasuje do Twojego stylu)"

    if (
        travel_style == "relax"
        and "relaxation" in preferences
        and poi_covers_preference_report(poi, "relaxation")
    ):
        return "Relaksująca atrakcja (pasuje do Twojego stylu)"

    if travel_style in ("active", "adventure") and poi_covers_preference_report(
        poi, "active_sport"
    ):
        return "Aktywna przygoda (pasuje do Twojego stylu)"

    return None


def _explain_profile_match(
    poi: Dict[str, Any], user: Dict[str, Any]
) -> Optional[str]:
    target_group = user.get("target_group", "").lower()
    travel_style = user.get("travel_style", "").lower()
    poi_tags_str = str(poi.get("tags", "")).lower()
    poi_name = str(poi.get("name", "")).lower()

    if target_group == "couples":
        winter_indicators = ["kulig", "sleigh", "horse_riding", "seasonal_activity"]
        if any(ind in poi_name or ind in poi_tags_str for ind in winter_indicators):
            return "Romantyczne zimowe doświadczenie"

        romantic_indicators = ["romantic", "cultural", "heritage", "scenic", "termy", "spa"]
        if any(ind in poi_tags_str for ind in romantic_indicators):
            return "Idealne dla par"

    if target_group == "friends" and travel_style == "adventure":
        adventure_indicators = [
            "adventure", "active", "sport", "group", "escape", "laser", "park",
        ]
        if any(ind in poi_tags_str or ind in poi_name for ind in adventure_indicators):
            return "Świetne na grupowe przygody"

    if target_group == "family_kids":
        kids_indicators = ["kids", "family", "playground", "zoo", "children"]
        if any(ind in poi_tags_str or ind in poi_name for ind in kids_indicators):
            return "Idealne dla rodzin z dziećmi"

    if target_group == "seniors":
        calm_indicators = ["scenic", "museum", "heritage", "park", "relax", "spa"]
        if any(ind in poi_tags_str for ind in calm_indicators):
            return "Idealne na spokojną podróż seniorów"

    return None


def _explain_seasonal_experience(
    poi: Dict[str, Any], context: Dict[str, Any]
) -> Optional[str]:
    poi_name = str(poi.get("name", "")).lower()
    poi_tags_str = str(poi.get("tags", "")).lower()
    season = str(context.get("season", "") or "").lower()

    winter_indicators = ["kulig", "sleigh", "snow", "winter", "ski"]
    if any(ind in poi_name or ind in poi_tags_str for ind in winter_indicators):
        return "Zimowe doświadczenie"

    local_indicators = ["local_tradition", "folklore", "highland", "regional"]
    if any(ind in poi_tags_str for ind in local_indicators):
        return "Lokalne doświadczenie"

    if season == "winter" and "seasonal" in poi_tags_str:
        return "Zimowe doświadczenie"

    return None


def explain_poi_selection(
    poi: Dict[str, Any],
    context: Dict[str, Any],
    user: Dict[str, Any],
    score: float = 0.0
) -> List[str]:
    """Top 3 Polish reasons why this POI was selected (FIX #251)."""
    reasons = []

    priority_val = poi.get("priority_level", 0)
    if isinstance(priority_val, str):
        _pl_map = {"core": 12, "secondary": 6, "optional": 0}
        priority = _pl_map.get(priority_val.strip().lower(), 0)
    else:
        priority = int(priority_val) if priority_val else 0
    if priority == 12:
        _poi_city = poi.get("city") or poi.get("City") or context.get("city") or "Twojej destynacji"
        reasons.append(f"Must-see w {_poi_city}")
    elif priority >= 11:
        reasons.append("Wysoko polecane przez lokalnych")

    seasonal_reason = _explain_seasonal_experience(poi, context)
    if seasonal_reason:
        reasons.append(seasonal_reason)

    profile_reason = _explain_profile_match(poi, user)
    if profile_reason:
        reasons.append(profile_reason)

    pref_reason = _explain_preference_match(poi, user)
    if pref_reason:
        reasons.append(pref_reason)

    crowd_reason = _explain_crowd_fit(poi, user)
    if crowd_reason:
        reasons.append(crowd_reason)

    budget_reason = _explain_budget_fit(poi, user)
    if budget_reason:
        reasons.append(budget_reason)

    style_reason = _explain_travel_style_match(poi, user)
    if style_reason:
        reasons.append(style_reason)

    if not reasons:
        reasons.append("Pasuje do czasu i lokalizacji w Twoim planie")

    return reasons[:3]


def generate_quality_summary(
    day_badges: List[str], attraction_count: int
) -> str:
    if "has_must_see" in day_badges and "good_variety" in day_badges:
        return "Zrównoważony dzień z atrakcjami must-see i dużą różnorodnością"
    elif "has_must_see" in day_badges:
        return "Zawiera ikoniczne atrakcje must-see"
    elif "good_variety" in day_badges:
        return "Duża różnorodność doświadczeń"
    elif "realistic_timing" in day_badges:
        return "Komfortowe tempo z realistycznym czasem"
    elif attraction_count >= 5:
        return "Intensywny dzień z wieloma atrakcjami"
    else:
        return "Spokojny dzień z jakościowymi doświadczeniami"
