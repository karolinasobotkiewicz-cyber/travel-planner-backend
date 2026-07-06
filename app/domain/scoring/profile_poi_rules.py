# type: ignore
"""FIX #230/#231/#233 — profile + preference POI deny/demote rules (client feedback)."""

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
    adv = style == "adventure" or "adventure" in prefs

    # Wrocław: zoo off friends + adventure + underground + history
    if _is_zoo(poi) and tg == "friends" and {"adventure", "underground", "history_mystery"} <= prefs:
        return True
    # Katowice: zoo off friends + adventure + active_sport
    if _is_zoo(poi) and tg == "friends" and {"adventure", "active_sport"} <= prefs:
        return True
    # FIX #233 Katowice: zoo off friends+adventure (any combo) and couples+cultural
    if _is_zoo(poi) and tg == "friends" and adv:
        return True
    if _is_zoo(poi) and tg == "couples" and style == "cultural":
        return True

    # FIX #233 Warszawa family_kids — Cmentarz Powązkowski
    if tg == "family_kids" and any(k in name for k in (
        "cmentarz powązkowski", "cmentarz powazkowski", "powązk", "powazk",
    )):
        return True

    # FIX #233 Kraków family_kids — Fabryka Schindlera / Stare Miasto core
    if tg == "family_kids":
        if any(k in name for k in (
            "fabryka schindlera", "schindlera",
            "rynek główny", "rynek glowny", "sukiennice",
        )):
            return True

    # FIX #233 solo + relax — block dry museums when no museum pref
    if tg == "solo" and (style == "relax" or "relaxation" in prefs):
        if "muzeum" in name and not ({"museum_heritage", "history_mystery"} & prefs):
            if not any(k in name for k in ("hydropolis", "kopernik", "nauki")):
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

    # FIX #231 — Kraków family_kids
    if tg == "family_kids":
        if any(k in name for k in (
            "kościół św. wojciecha", "sw. wojciecha", "bazylika mariacka",
            "park decjusza", "kopiec krakusa",
        )):
            return True
        if "aula leopoldina" in name:
            return True

    # FIX #231 — cultural: Lustrzany Labirynt off
    if style == "cultural" and "lustrzany labirynt" in name:
        return True

    # FIX #233 couples+cultural — misfit attractions
    if tg == "couples" and style == "cultural":
        if any(k in name for k in (
            "pixel xl", "pixel", "gojump", "trampolin", "paintball", "laser tag",
            "city golf", "bungee", "escape room",
        )):
            return True

    # FIX #231 — Katowice family: Kościół św. Anny
    if tg == "family_kids" and ("św. anny" in name or "sw. anny" in name):
        if "kościół" in name or "kosciol" in name or "parafia" in name:
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
    if any(k in name for k in (
        "hala targowa", "most grunwaldzki", "dworzec świebodzki", "dworzec swiebodzki",
        "bastion sakwowy",
    )):
        delta -= 95.0
        if day == 1:
            delta -= 50.0

    # FIX #231 Wrocław — City Golf couples+cultural
    if "city golf" in name and tg == "couples" and style == "cultural":
        delta -= 80.0

    # FIX #231 Wrocław — seniors+relax green spots
    if tg == "seniors" and ("relaxation" in prefs or style == "relax"):
        if any(k in name for k in (
            "park szczytnicki", "pergola", "wyspa słodowa", "wyspa slodowa",
            "ogród japoński", "ogrod japonski",
        )):
            delta += 85.0

    # FIX #231 Wrocław — adventure boosts
    if adv and any(k in name for k in (
        "centrum historii zajezdnia", "zajezdnia", "hydropolis", "pixel xl", "pixel",
    )):
        delta += 75.0

    # FIX #231 Wrocław — nature+relax green
    if nat_relax and any(k in name for k in (
        "park szczytnicki", "pergola", "wyspa słodowa", "wyspa slodowa",
        "ogród japoński", "ogrod japonski", "zatoka gondoli", "rejs", "odra",
    )):
        delta += 80.0

    # FIX #231 Wrocław — family_kids boosts
    if tg == "family_kids" and any(k in name for k in ("kolejkowo", "hydropolis")):
        delta += 90.0

    # FIX #231 — cultural style should not erase relaxation
    if style == "cultural" and "relaxation" in prefs:
        if any(k in name for k in ("ogród", "ogrod", "park ", "bulwar", "wyspa", "spa", "termy")):
            delta += 70.0
        if "muzeum" in name and "hydropolis" not in name:
            delta -= 35.0

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
        "plac europejski",
    )
    if any(k in name for k in _waw_micro):
        delta -= 85.0

    # FIX #231 Warszawa — friends+adventure demote relax parks
    if tg == "friends" and adv:
        if any(k in name for k in (
            "ogrody zamku", "ogrod zamku", "łazienki królewskie", "lazienki krolewskie",
            "jeziorko czerniakowskie", "bulwary wiślane", "bulwary wislane",
        )):
            delta -= 80.0
        if "muzeum fabryki norblina" in name or "norblin" in name:
            delta -= 75.0

    # FIX #231 Warszawa — nature landscape boosts
    if "nature_landscape" in prefs and any(k in name for k in (
        "ogród botaniczny uw", "ogrod botaniczny uw", "bulwary wiślane", "bulwary wislane",
    )):
        delta += 80.0

    # FIX #231 Warszawa — museum_heritage flagship boosts
    if "museum_heritage" in prefs and any(k in name for k in (
        "zamek królewski", "zamek krolewski", "muzeum narodowe", "muzeum wojska polskiego",
    )):
        delta += 70.0

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
    if any(k in name for k in (
        "kościół św. wojciecha", "sw. wojciecha", "plac bohaterów getta",
        "kładka bernatka", "kladka bernatka", "be happy museum",
    )):
        delta -= 80.0

    if "bazylika mariacka" in name:
        if tg == "family_kids":
            delta -= 95.0
        if tg == "friends" and adv:
            delta -= 85.0

    if tg == "friends" and adv:
        if any(k in name for k in ("park decjusza", "kopiec wandy")):
            delta -= 80.0
        if day >= int(ctx.get("num_days") or 1) and "kopiec wandy" in name:
            delta -= 100.0

    if "alvernia planet" in name and tg == "solo" and {"nature_landscape", "museum_heritage", "history_mystery"} <= prefs:
        delta -= 85.0

    if tg == "family_kids" and "kopiec krakusa" in name:
        delta -= 90.0

    if {"water_attractions", "relaxation", "local_food_experience"} <= prefs:
        if any(k in name for k in ("muzeum", "fabryka schindlera")) and "hydropolis" not in name:
            delta -= 70.0

    if tg == "seniors" and ("relaxation" in prefs or style == "relax"):
        if "wieża ratuszowa" in name or "wieza ratuszowa" in name:
            delta -= 80.0

    if tg == "couples" and {"relaxation", "water_attractions", "local_food_experience"} <= prefs:
        if any(k in name for k in ("fabryka schindlera", "muzeum lotnictwa")):
            delta -= 75.0

    # ── Katowice ──
    if _has_church_name(name):
        delta -= 45.0  # FIX #231 extra church demote all profiles

    if "park kościuszki" in name or "park kosciuszki" in name:
        if name in trip_names:
            delta -= 100.0
        if tg == "family_kids":
            delta -= 50.0

    if "muzeum historii katowic" in name and name in trip_names:
        delta -= 100.0

    if "planetarium" in name and tg == "friends" and adv and "active_sport" in prefs:
        delta -= 85.0

    if day == 1 and any(k in name for k in ("rynek w katowicach", "rynek katowic")):
        delta -= 90.0

    if tg == "seniors" and ("relaxation" in prefs or style == "relax"):
        if any(k in name for k in (
            "park śląski", "park slaski", "dolina trzech stawów", "nikiszowiec",
        )):
            delta += 85.0

    if nat_relax:
        if any(k in name for k in ("muzeum historii katowic", "muzeum etnologii", "spodek")):
            delta -= 75.0
        if _has_church_name(name):
            delta -= 60.0

    if "górnośląski park etnograficzny" in name or "gornoslaski park etnograficzny" in name:
        if {"water_attractions", "relaxation"} & prefs or "local_food_experience" in prefs:
            delta -= 70.0

    # ── Poznań ──
    if any(k in name for k in (
        "pomnik bamberki", "pomnik ofiar czerwca", "domy kupieckie",
    )):
        delta -= 80.0

    if adv:
        if any(k in name for k in (
            "okrąglak", "okraglak", "domy kupieckie", "muzeum bambrów", "muzeum bambrow",
            "fotoplastykon",
        )):
            delta -= 85.0
        if _has_church_name(name) and no_history:
            delta -= 70.0

    if ("relaxation" in prefs or style == "relax") and any(k in name for k in (
        "jezioro maltańskie", "jezioro maltanskie", "wartostrada", "park sołacki",
        "park solacki", "ogród botaniczny", "ogrod botaniczny",
    )):
        delta += 85.0

    if "water_attractions" in prefs and any(k in name for k in (
        "jezioro maltańskie", "jezioro maltanskie", "bulwar", "warta",
    )):
        delta += 80.0

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
            delta -= 80.0
        if tg == "friends" and any(k in name for k in ("rynek", "plac ", "most ", "bazylika", "kościół")):
            delta -= 85.0

    # FIX #233 — adventure needs multiple active POIs per day, not one + sightseeing
    if adv and day >= 1:
        if is_active_city_poi(poi):
            delta += 70.0
        _day_active = int(ctx.get("day_active_count") or 0)
        if _day_active >= 1 and no_history:
            if any(k in name for k in ("muzeum", "galeri", "kościół", "bazylika", "katedra")):
                delta -= 90.0
            if any(k in name for k in ("rynek", "stare miasto", "plac ", "most ", "pomnik ")):
                delta -= 75.0

    # FIX #233 — balanced long trips: demote extra museums
    if style == "balanced":
        _trip_mus = int(ctx.get("trip_museum_count") or 0)
        if "muzeum" in name and _trip_mus >= 3 and "museum_heritage" not in prefs[:2]:
            delta -= 70.0
        if "muzeum" in name and day >= 3 and _trip_mus >= 2:
            delta -= 55.0

    # FIX #233 — family_kids: demote Las Wolski, Rynek-area, Matejki, Geologiczne
    if tg == "family_kids":
        if any(k in name for k in (
            "las wolski", "dom jana matejki", "muzeum geologiczne",
            "wieża ratuszowa", "wieza ratuszowa", "park decjusza", "park bednarskiego",
            "kładka bernatka", "kladka bernatka",
        )):
            delta -= 85.0
        if any(k in name for k in ("kolejkowo", "hydropolis", "mini zoo", "papugarn", "pixel")):
            delta += 75.0

    # FIX #233 — Poznań water_attractions: Maltańskie is core
    if "water_attractions" in prefs and any(k in name for k in (
        "jezioro maltańskie", "jezioro maltanskie", "maltanka", "termy malta",
    )):
        delta += 95.0
    if "water_attractions" in prefs and "malta" in name and "muzeum" not in name:
        delta += 80.0

    # FIX #233 Poznań — demote micro heritage
    if any(k in name for k in (
        "muzeum bambrów", "muzeum bambrow", "bazylika archikatedralna",
        "okrąglak", "okraglak",
    )):
        delta -= 85.0

    # FIX #233 Kraków — demote over-ranked micro
    if any(k in name for k in (
        "kościół św. wojciecha", "sw. wojciecha", "muzeum geologiczne",
        "dom jana matejki", "wieża ratuszowa", "wieza ratuszowa",
        "park decjusza", "park bednarskiego", "kładka bernatka", "kladka bernatka",
    )):
        delta -= 90.0

    # FIX #233 Katowice — demote filler museums/churches/parks
    if any(k in name for k in (
        "muzeum historii katowic", "dział etnologii", "dzial etnologii",
        "parafia św. anny", "parafia sw. anny", "park chrobrego",
        "muzeum odlewnictwa", "odlewnictwa artystycznego",
    )):
        delta -= 90.0

    # FIX #233 Wrocław — demote Wena, Arboretum Wojsławice day 1, Ogród Botaniczny repeat
    if "muzeum motoryzacji wena" in name or ("muzeum motoryzacji" in name and "wena" in name):
        delta -= 95.0
    if day == 1 and any(k in name for k in ("arboretum wojsławice", "arboretum wojslawice")):
        delta -= 120.0
    if "ogród botaniczny" in name or "ogrod botaniczny" in name:
        if name in trip_names:
            delta -= 100.0


    # FIX #233 — solo+relax museum demote
    if tg == "solo" and (style == "relax" or "relaxation" in prefs) and "muzeum" in name:
        if not ({"museum_heritage", "history_mystery"} & prefs):
            delta -= 80.0

    # FIX #233 — couples+cultural garden/culture boost, demote active fun
    if tg == "couples" and style == "cultural":
        if any(k in name for k in ("muzeum", "galeria", "zamek", "pałac", "palac", "ogród", "ogrod")):
            delta += 45.0
        if any(k in name for k in ("pixel", "trampolin", "paintball", "gojump")):
            delta -= 85.0

    # FIX #231 — friends + adventure active boost
    if tg == "friends" and adv and "active_sport" in prefs:
        if any(k in name for k in (
            "gojump", "trampolin", "park linowy", "paintball", "escape", "pixel",
            "bungee", "kopalnia", "aquapark", "hydropolis",
        )):
            delta += 80.0

    # ── Relax/nature spread — boost when pref not hit today ──
    needed = ctx.get("prefs_needed_today") or set()
    if "relaxation" in needed and any(k in name for k in (
        "spa", "termy", "bulwar", "ogród", "ogrod", "park ", "palmiarnia",
        "wyspa", "pergola", "malta", "wartostrada", "sołacki", "solacki",
    )):
        delta += 90.0
    if "nature_landscape" in needed and any(k in name for k in (
        "ogród", "ogrod", "botaniczny", "rezerwat", "bulwar", "wyspa", "park szczytnicki",
    )):
        delta += 90.0
    if "active_sport" in needed and any(k in name for k in (
        "gojump", "park linowy", "trampolin", "aquapark", "kopalnia", "bungee",
        "hydropolis", "paintball", "escape", "linowa", "planetarium",
    )):
        delta += 95.0

    # Ojców cluster — strong boost when Maczuga already scheduled today
    if ctx.get("ojcow_day_active") or ctx.get("excursion_day_active"):
        _reg = ctx.get("excursion_day_active") or "region_ojcow"
        from app.domain.planner.engine import poi_geo_region_key
        if poi_geo_region_key(poi) == _reg:
            delta += 90.0
        elif any(k in name for k in ("pieskowa skała", "pieskowa skala", "jaskinia łokietka", "jaskinia lokietka", "zamek w ojcowie", "ojców", "ojcow", "maczuga")):
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
