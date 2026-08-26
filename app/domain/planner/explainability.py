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
    poi: Dict[str, Any],
    user: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    target_group = user.get("target_group", "").lower()
    travel_style = user.get("travel_style", "").lower()
    poi_tags_str = str(poi.get("tags", "")).lower()
    poi_name = str(poi.get("name", "")).lower()
    season = str((context or {}).get("season", "") or "").lower()

    if target_group == "couples":
        # FIX #253: only call it "zimowe" on an actual winter trip.
        winter_indicators = ["kulig", "sleigh", "horse_riding", "seasonal_activity"]
        if season == "winter" and any(
            ind in poi_name or ind in poi_tags_str for ind in winter_indicators
        ):
            return "Romantyczne zimowe doświadczenie"

        romantic_indicators = ["romantic", "cultural", "heritage", "scenic", "termy", "spa"]
        if any(ind in poi_tags_str for ind in romantic_indicators):
            return "Idealne dla par"

    if target_group == "friends" and travel_style == "adventure":
        if not any(k in poi_name for k in ("muzeum", "katedra", "kościół", "kosciol")):
            adventure_indicators = [
                "laser", "escape", "paintball", "gojump", "quad", "park linowy",
            ]
            if any(ind in poi_tags_str or ind in poi_name for ind in adventure_indicators):
                return "Świetne na grupowe przygody"

    if "aula leopoldina" in poi_name:
        return "Barokowa aula Uniwersytetu Wrocławskiego — krótki, treściwy przystanek."
    if target_group == "family_kids":
        # FIX #268: Pixel XL copy says youth/adults — never claim "dla najmłodszych".
        if "pixel" in poi_name:
            return None
        if "smart kids" in poi_name:
            return "Idealne dla rodzin z dziećmi"
        kids_indicators = [
            "kids", "family", "playground", "zoo", "children",
            "smart kids", "planet", "sala zabaw", "miniciti", "kolejkowo",
        ]
        if any(ind in poi_tags_str or ind in poi_name for ind in kids_indicators):
            return "Idealne dla rodzin z dziećmi"

    if target_group == "seniors":
        calm_indicators = ["scenic", "museum", "heritage", "park", "relax", "spa"]
        if any(ind in poi_tags_str for ind in calm_indicators):
            return "Idealne na spokojną podróż seniorów"

    return None


_SEASON_LABEL_PL = {
    "winter": "zimowa",
    "spring": "wiosenna",
    "summer": "letnia",
    "autumn": "jesienna",
    "fall": "jesienna",
}

_WINTER_TOKENS = {"kulig", "sleigh", "snow", "winter", "ski", "narty", "narciarski",
                  "snowboard", "lodowisko", "sanki", "saneczkowy", "zima", "zimowy"}
_LOCAL_TOKENS = {"local_tradition", "folklore", "highland", "regional", "tradycja",
                 "folklor", "regionalny"}


def _explain_seasonal_experience(
    poi: Dict[str, Any], context: Dict[str, Any]
) -> Optional[str]:
    """FIX #253: seasonal reasons must match the actual travel season.

    The old version substring-matched "ski" against the POI name, so
    "Ostrów Tum-ski" and "Ogród Botaniczny Uniwersytetu Wrocław-ski-ego" were
    labelled "Zimowe doświadczenie" in July. Matching is now token-based and
    winter copy is only produced for winter trips.
    """
    from app.domain.planner.poi_copy import poi_name_tokens, poi_token_set

    season = str(context.get("season", "") or "").lower()
    toks = poi_token_set(poi) | poi_name_tokens(poi)

    if toks & _WINTER_TOKENS:
        # Genuinely winter-only activity outside winter → not a selling point.
        return "Zimowe doświadczenie" if season == "winter" else None

    if toks & _LOCAL_TOKENS:
        return "Lokalne doświadczenie"

    if "seasonal" in toks and season in _SEASON_LABEL_PL:
        return f"Sezonowa atrakcja ({_SEASON_LABEL_PL[season]})"

    return None


_CATEGORY_HIGHLIGHT_PL = {
    "aquapark": "Strefa wodna na relaks i zabawę",
    "spa": "Chwila wytchnienia w strefie spa",
    "trampoline": "Porcja ruchu i adrenaliny w hali trampolin",
    "climbing": "Wyzwanie na trasach w koronach drzew",
    "motorsport": "Sportowa dawka adrenaliny na torze",
    "shooting": "Rywalizacja w grupie na arenie",
    "escape_room": "Zagadki do rozwiązania zespołowo",
    "maze": "Zabawa na orientację na świeżym powietrzu",
    "mirror_maze": "Zabawa na orientację w lustrzanym labiryncie",
    "amusement": "Rozrywka w klimacie parku tematycznego",
    "playground": "Bezpieczna strefa zabaw dla najmłodszych",
    "zoo": "Spotkanie ze zwierzętami z bliska",
    "science": "Interaktywne eksponaty do samodzielnego testowania",
    "museum": "Ekspozycja warta dłuższej wizyty",
    "heritage": "Zabytek z bogatą historią",
    "old_town": "Klimat historycznego centrum",
    "viewpoint": "Panorama miasta z góry",
    "garden": "Kolekcje roślin i spokojne alejki",
    "park": "Zieleń i przestrzeń na oddech",
    "water_nature": "Nadwodne widoki i spokojniejsze tempo",
    "hiking": "Kontakt z przyrodą na trasie spacerowej",
    "cruise": "Miasto oglądane od strony wody",
    "winter_sport": "Aktywność typowa dla sezonu zimowego",
    "sport": "Aktywne spędzenie czasu",
    "nightlife": "Dobre miejsce na wieczór",
    "shopping": "Zakupy i przerwa przy kawie",
    "entertainment": "Wieczór z kulturą na żywo",
}


def _explain_category_highlight(
    poi: Dict[str, Any], user: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """FIX #253/#254: category reason — skip kids/playground copy for non-family."""
    from app.domain.planner.poi_copy import classify_poi_category

    cat = classify_poi_category(poi)
    tg = (user or {}).get("target_group") or ""
    poi_name = str(poi.get("name") or "").lower()
    # FIX #271: caves are not theme parks; city gates are not long museum visits.
    if "jaskinia" in poi_name:
        return "Podziemna trasa w naturalnej jaskini"
    if "genius loci" in poi_name:
        return "Rezerwat archeologiczny i podziemna ekspozycja"
    if any(k in poi_name for k in ("wystawa pająków", "wystawa pajakow", "pająk", "pajak")):
        return "Nietypowa wystawa — ciekawostka, nie klasyczne muzeum"
    if "movie gate" in poi_name:
        return "Park rozrywki z atrakcjami filmowymi"
    if "pana tadeusza" in poi_name:
        return "Muzeum literackie poświęcone Panu Tadeuszowi"
    if "nikiszowiec" in poi_name:
        return "Historyczne osiedle robotnicze z ceglaną zabudową"
    if any(k in poi_name for k in (
        "brama floriańska", "brama florian", "barbakan",
    )):
        return "Zabytek przy historycznym ciągu Starego Miasta"
    # FIX #295: a modern river bridge is not "Zabytek z bogatą historią".
    if any(k in poi_name for k in ("most świętokrzyski", "most swietokrzyski")):
        return "Panorama miasta z góry"
    # FIX #296: a brewery at lunch is not "Dobre miejsce na wieczór".
    if "browar" in poi_name:
        return "Przerwa na lokalny browar i jedzenie"
    # FIX #268: Pixel XL is adult entertainment, not a kids playground reason.
    if "pixel" in poi_name and cat in ("playground", "amusement", "entertainment"):
        return "Interaktywna rozrywka w dużym formacie"
    # Client: "Bezpieczna strefa zabaw…" on Park Jordana / Wedel / Plac for couples.
    if cat == "playground" and tg not in ("family_kids", "family"):
        return None
    if cat in ("amusement", "escape_room", "maze") and tg in (
        "seniors", "couples",
    ):
        # Soften: still allow for couples adventure, but not cultural strolls.
        style = (user or {}).get("travel_style") or ""
        if style in ("cultural", "relax", "balanced") and cat != "maze":
            return None
    return _CATEGORY_HIGHLIGHT_PL.get(cat)


def _explain_rating(poi: Dict[str, Any]) -> Optional[str]:
    """FIX #254: popularity_score is 0–10 in Excel — never print it as /5 raw."""
    try:
        raw = float(str(poi.get("popularity_score") or poi.get("popularity") or 0))
    except (TypeError, ValueError):
        return None
    # Normalize 0–10 → 0–5; leave values already on a 0–5 scale alone.
    stars = raw / 2.0 if raw > 5.0 else raw
    if stars < 0.1:
        return None
    stars = min(5.0, max(0.0, stars))
    if stars >= 4.6:
        return f"Bardzo wysoko oceniana ({stars:.1f}/5)"
    if stars >= 4.3:
        return f"Wysoko oceniana przez odwiedzających ({stars:.1f}/5)"
    return None


def _explain_duration_fit(poi: Dict[str, Any]) -> Optional[str]:
    """FIX #253: short stops are a real reason to slot a POI in."""
    try:
        tmin = int(float(poi.get("time_min") or poi.get("duration_min") or 0))
    except (TypeError, ValueError):
        return None
    if 0 < tmin <= 30:
        return "Krótki przystanek, który dobrze wpasowuje się w dzień"
    if tmin >= 150:
        return "Atrakcja na dłużej — warto zarezerwować pół dnia"
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
        from app.domain.planner.city_copy import city_locative_pl

        _poi_city = (
            poi.get("city") or poi.get("City")
            or context.get("city") or context.get("requested_city")
            or "Twojej destynacji"
        )
        _nm_ms = str(poi.get("name") or "").lower()
        # FIX #260: Kampinos is not "Must-see w Warszawie".
        if "kampinos" in _nm_ms:
            reasons.append("Must-see w Kampinosie (Izabelin / okolice Warszawy)")
        elif any(k in _nm_ms for k in ("gliwice", "rynek w gliwic")):
            reasons.append("Must-see w Gliwicach")
        elif any(k in _nm_ms for k in ("zabrze", "guido", "królowa luiza", "krolowa luiza")):
            reasons.append("Must-see w Zabrzu")
        elif any(k in _nm_ms for k in ("chorzów", "chorzow", "park śląski", "park slaski")):
            reasons.append("Must-see w Chorzowie")
        else:
            # FIX #254: "Must-see we Wrocławiu", not "Must-see w Wrocław".
            reasons.append(f"Must-see {city_locative_pl(str(_poi_city))}")
    elif priority >= 11:
        reasons.append("Wysoko polecane przez lokalnych")

    seasonal_reason = _explain_seasonal_experience(poi, context)
    if seasonal_reason:
        reasons.append(seasonal_reason)

    profile_reason = _explain_profile_match(poi, user, context)
    if profile_reason:
        reasons.append(profile_reason)

    pref_reason = _explain_preference_match(poi, user)
    if pref_reason:
        reasons.append(pref_reason)

    # FIX #253: category highlight before the generic crowd/budget lines so the
    # client stops seeing only "Must-see / Pasuje do preferencji".
    category_reason = _explain_category_highlight(poi, user)
    if category_reason:
        reasons.append(category_reason)

    rating_reason = _explain_rating(poi)
    if rating_reason:
        reasons.append(rating_reason)

    crowd_reason = _explain_crowd_fit(poi, user)
    if crowd_reason:
        reasons.append(crowd_reason)

    budget_reason = _explain_budget_fit(poi, user)
    if budget_reason:
        reasons.append(budget_reason)

    style_reason = _explain_travel_style_match(poi, user)
    if style_reason:
        reasons.append(style_reason)

    duration_reason = _explain_duration_fit(poi)
    if duration_reason:
        # FIX #271: don't pair "dłuższa wizyta" with "krótki przystanek".
        if not any(
            "dłuższej wizyty" in r or "dłuższa wizyta" in r for r in reasons
        ):
            reasons.append(duration_reason)

    if not reasons:
        reasons.append("Pasuje do czasu i lokalizacji w Twoim planie")

    # De-duplicate while preserving order (several explainers can overlap).
    seen: set = set()
    unique: List[str] = []
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            unique.append(reason)

    return unique[:3]


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
