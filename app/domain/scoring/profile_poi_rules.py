# type: ignore
"""FIX #230 — profile + preference POI deny/demote rules (client feedback round 3)."""

from __future__ import annotations


def _safe_str(x) -> str:
    return str(x).strip().lower() if x is not None else ""


def _name(poi: dict) -> str:
    return _safe_str(poi.get("name") or poi.get("Name") or "")


def _prefs(user: dict) -> set[str]:
    return {_safe_str(p) for p in (user.get("preferences") or []) if p}


def _has_church_name(name: str) -> bool:
    return any(
        k in name
        for k in (
            "kościół", "kosciol", "bazylika", "katedra", "kaplica",
            "parafia", "taras przy kościele", "taras przy kosciolu",
        )
    )


def _is_zoo(poi: dict) -> bool:
    name = _name(poi)
    tags = {_safe_str(t) for t in (poi.get("tags") or []) if t}
    return "zoo" in name or "zoo" in tags or "mini zoo" in name


def should_deny_poi_for_profile(poi: dict, user: dict) -> bool:
    """Hard exclude POI for specific profile + preference combinations."""
    name = _name(poi)
    tg = _safe_str(user.get("target_group"))
    prefs = _prefs(user)
    style = _safe_str(user.get("travel_style"))
    child_age = user.get("children_age")

    # Wrocław: zoo off friends + adventure + underground + history
    if _is_zoo(poi) and tg == "friends" and {"adventure", "underground", "history_mystery"} <= prefs:
        return True
    # Katowice: zoo off friends + adventure + active_sport
    if _is_zoo(poi) and tg == "friends" and {"adventure", "active_sport"} <= prefs:
        return True

    # Kraków: Podziemia Rynku for family with young child
    if tg == "family_kids" and "podziemia rynku" in name:
        if child_age is None or (isinstance(child_age, (int, float)) and child_age <= 6):
            return True

    # Katowice: Kościół św. Michała for family_kids
    if tg == "family_kids" and ("św. michała" in name or "sw. michala" in name):
        return True

    # Warszawa friends+adventure+underground+history — parks/churches off
    if tg == "friends" and (style == "adventure" or "adventure" in prefs):
        if {"underground", "history_mystery"} <= prefs:
            if any(k in name for k in (
                "ogrody zamku", "ogrod zamku", "łazienki królewskie", "lazienki krolewskie",
                "taras przy kościele", "taras przy kosciolu",
            )):
                return True

    return False


def profile_poi_score_delta(poi: dict, user: dict, *, context: dict | None = None) -> float:
    """Soft scoring adjustments for profile-specific client feedback."""
    name = _name(poi)
    tg = _safe_str(user.get("target_group"))
    prefs = _prefs(user)
    style = _safe_str(user.get("travel_style"))
    delta = 0.0
    ctx = context or {}
    day = int(ctx.get("current_day_num") or 1)
    num_days = int(ctx.get("num_days") or 1)
    trip_names = ctx.get("trip_used_poi_names") or set()

    adv = style == "adventure" or "adventure" in prefs
    nat_relax = {"nature_landscape", "relaxation"} <= prefs
    no_history = not ({"history_mystery", "museum_heritage", "underground"} & prefs)

    # ── Churches / sakral — broad demote when not culture-led ──
    if _has_church_name(name) and must_see_below(poi, 9):
        if tg == "family_kids":
            delta -= 85.0
        elif nat_relax or style == "relax" or "relaxation" in prefs:
            delta -= 70.0
        elif adv and no_history:
            delta -= 90.0
        elif tg == "seniors" and ("relaxation" in prefs or "nature_landscape" in prefs):
            delta -= 75.0

    # ── Wrocław filler / micro ──
    if any(k in name for k in ("hala targowa", "most grunwaldzki", "dworzec świebodzki", "dworzec swiebodzki")):
        delta -= 80.0
        if day == 1:
            delta -= 40.0

    # Hala Stulecia — friends + adventure + active_sport
    if "hala stulecia" in name and tg == "friends" and adv and "active_sport" in prefs:
        delta -= 75.0

    # Katedra Wrocławska / family → boost kids alternatives handled elsewhere; demote church
    if tg == "family_kids" and ("katedra wrocławska" in name or "katedra wroclawska" in name):
        delta -= 90.0

    # Hydropolis / Ogród Japoński boost for families
    if tg == "family_kids" and any(k in name for k in ("hydropolis", "ogród japoński", "ogrod japonski")):
        delta += 65.0

    # Couples + cultural + relaxation — aquapark as relaxation substitute
    if tg == "couples" and style == "cultural" and "relaxation" in prefs:
        if "aquapark" in name or "park wodny" in name:
            delta -= 80.0
        if any(k in name for k in ("ogród", "ogrod", "bulwar", "park ", "wyspa słodowa")):
            delta += 55.0

    # Bastion Sakwowy — couples + relax + water
    if "bastion sakwowy" in name and tg == "couples" and {"relaxation", "water_attractions"} <= prefs:
        delta -= 75.0

    # Browar Stu Mostów — solo + nature + relax
    if "browar stu mostów" in name or "browar stu mostow" in name:
        if tg == "solo" and nat_relax:
            delta -= 85.0

    # ── Warszawa micro ──
    _waw_micro = (
        "taras przy kościele", "taras przy kosciolu", "pomnik syrenki", "syrenki",
        "most świętokrzyski", "most swietokrzyski", "pałac prezydencki", "palac prezydencki",
        "grób nieznanego", "grob nieznanego", "bazylika św. jana", "bazylika sw. jana",
    )
    if any(k in name for k in _waw_micro):
        delta -= 75.0

    if tg == "family_kids" and day == 1 and "kopiec powstania" in name:
        delta -= 100.0

    if tg == "family_kids" and "syrenk" in name:
        delta -= 80.0

    if tg == "friends" and adv:
        if any(k in name for k in ("bulwary wiślane", "bulwary wislane", "ogrody zamku", "ogrod zamku", "łazienki królewskie", "lazienki krolewskie")):
            delta -= 70.0

    if tg == "solo" and nat_relax and "grób nieznanego" in name:
        delta -= 100.0

    if tg == "couples" and {"relaxation", "water_attractions", "local_food_experience"} <= prefs:
        if "muzeum polskiej wódki" in name or "muzeum polskiej wodki" in name:
            delta -= 80.0

    # ── Kraków ──
    if "bazylika mariacka" in name:
        if tg == "family_kids":
            delta -= 85.0
        if tg == "friends" and adv:
            delta -= 70.0

    if "kościół św. wojciecha" in name or "sw. wojciecha" in name:
        if tg == "seniors" and ("relaxation" in prefs or style == "relax"):
            delta -= 80.0

    if tg == "friends" and adv:
        if any(k in name for k in ("kładka bernatka", "kladka bernatka", "park decjusza", "plac bohaterów getta")):
            delta -= 75.0

    if tg == "seniors" and ("relaxation" in prefs or style == "relax"):
        if "wieża ratuszowa" in name or "wieza ratuszowa" in name:
            delta -= 80.0

    if tg == "couples" and {"relaxation", "water_attractions", "local_food_experience"} <= prefs:
        if any(k in name for k in ("fabryka schindlera", "muzeum lotnictwa")):
            delta -= 75.0

    # ── Katowice ──
    if "park kościuszki" in name or "park kosciuszki" in name:
        if name in trip_names:
            delta -= 90.0

    if "górnośląski park etnograficzny" in name or "gornoslaski park etnograficzny" in name:
        if {"water_attractions", "relaxation"} & prefs or "local_food_experience" in prefs:
            delta -= 70.0

    # ── Poznań ──
    if "okrąglak" in name or "okraglak" in name:
        if tg == "friends" and adv and {"underground", "history_mystery"} <= prefs:
            delta -= 80.0

    if "domy kupieckie" in name and {"water_attractions", "relaxation", "local_food_experience"} & prefs:
        delta -= 75.0

    if tg == "solo" and nat_relax and _has_church_name(name):
        delta -= 80.0

    # ── Adventure trip character — demote passive after day 1 ──
    if adv and day >= 2 and no_history:
        if any(k in name for k in ("muzeum", "galeri")) and "kopalnia" not in name:
            delta -= 45.0

    # ── Relax/nature spread — boost when pref not hit today ──
    needed = ctx.get("prefs_needed_today") or set()
    if "relaxation" in needed and any(k in name for k in ("spa", "termy", "bulwar", "ogród", "ogrod", "park ", "palmiarnia")):
        delta += 70.0
    if "nature_landscape" in needed and any(k in name for k in ("ogród", "ogrod", "botaniczny", "rezerwat", "bulwar", "wyspa")):
        delta += 70.0
    if "active_sport" in needed and any(k in name for k in ("gojump", "park linowy", "trampolin", "aquapark", "kopalnia", "bungee", "hydropolis")):
        delta += 65.0

    # Ojców cluster — strong boost when Maczuga already scheduled today
    if ctx.get("ojcow_day_active"):
        if any(k in name for k in ("pieskowa skała", "pieskowa skala", "jaskinia łokietka", "jaskinia lokietka", "zamek w ojcowie", "ojców", "ojcow")):
            delta += 90.0

    # Duplicate POI name penalty (Ogrody Zamku 2x)
    if name and name in trip_names:
        delta -= 100.0

    return delta


def must_see_below(poi: dict, threshold: float) -> bool:
    ms = poi.get("must_see") or poi.get("must_see_score")
    try:
        return ms is None or float(ms) < threshold
    except (TypeError, ValueError):
        return True


def is_active_city_poi(poi: dict) -> bool:
    """POIs that should count as 'active' for adventure profile warnings."""
    name = _name(poi)
    tags = {_safe_str(t) for t in (poi.get("tags") or []) if t}
    if poi.get("type") == "trail":
        return True
    _active_tags = {
        "active_sport", "sports", "outdoor_adventure", "trampoline_park",
        "forest_rope_courses", "climbing", "underground", "industrial_heritage",
        "mining_heritage", "water_activity", "zipline",
    }
    if tags & _active_tags:
        return True
    _active_names = (
        "gojump", "aquapark", "hydropolis", "bungee", "park linowy", "trampolin",
        "kopalnia", "sztolnia", "guido", "carboneum", "spływ", "spluw", "ponton",
        "pixel xl", "escape", "paintball", "linowa",
    )
    return any(n in name for n in _active_names)
