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
    nat_relax = {"nature_landscape", "relaxation"} <= prefs
    no_history = not ({"history_mystery", "museum_heritage", "underground"} & prefs)

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

    # Katowice: Kościół św. Michała for family_kids (FIX #243: pełna nazwa POI)
    if tg == "family_kids" and any(k in name for k in (
        "św. michała", "sw. michala", "świętego michała", "swietego michala",
        "michała archanioła", "michala archanioła",
    )):
        return True

    # FIX #235 Katowice — Śląskie Centrum Wolności for family_kids
    if tg == "family_kids" and any(k in name for k in (
        "śląskie centrum wolności", "slaskie centrum wolnosci",
        "centrum wolności i solidarności", "centrum wolnosci i solidarnosci",
    )):
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

    # FIX #234 couples+cultural — Park Wodny / aquapark off
    if tg == "couples" and style == "cultural":
        if any(k in name for k in ("park wodny", "aquapark", "aquaparki")):
            return True

    # FIX #234 Wrocław family_kids — Muzeum Uniwersytetu
    if tg == "family_kids" and any(k in name for k in (
        "muzeum uniwersytetu", "muzeum uniwersyteckie",
    )):
        return True

    # FIX #240 Wrocław family_kids — Dworzec Świebodzki, Browar (wieczorny)
    if tg == "family_kids" and any(k in name for k in (
        "dworzec świebodzki", "dworzec swiebodzki",
        "browar stu mostów", "browar stu mostow",
    )):
        return True

    # FIX #240 Wrocław — Hala Targowa nie pasuje do active_sport + history_mystery
    if "hala targowa" in name and {"active_sport", "history_mystery"} <= prefs:
        return True

    # FIX #240 — Dworzec Świebodzki poza profilami heritage/history
    if any(k in name for k in ("dworzec świebodzki", "dworzec swiebodzki")):
        if tg == "family_kids":
            return True
        if not ({"museum_heritage", "history_mystery"} & prefs):
            return True

    # FIX #240 Wrocław — family_kids + relaxation: Wystawa Pająków off
    if tg == "family_kids" and "relaxation" in prefs:
        if any(k in name for k in ("pająk", "pajak", "spider", "wystawa pająk")):
            return True

    # FIX #240 — Fontanna Multimedialna zimą (sezonowość też w filter_by_season)

    # FIX #234 Warszawa family_kids — Zamek Ujazdowski
    if tg == "family_kids" and any(k in name for k in (
        "zamek ujazdowski", "ujazdowski",
    )):
        return True

    # FIX #231 — Katowice family: Kościół św. Anny
    if tg == "family_kids" and ("św. anny" in name or "sw. anny" in name):
        if "kościół" in name or "kosciol" in name or "parafia" in name:
            return True

    # FIX #241 Kraków — Kładka Bernatka (słaby filler we wszystkich planach)
    if any(k in name for k in (
        "kładka bernatka", "kladka bernatka", "kładka ojca bernatka", "ojca bernatka",
    )):
        return True

    # FIX #241 Kraków — solo+relax+nature bez history: bez ikon muzealnych
    if tg == "solo" and nat_relax and no_history:
        if any(k in name for k in (
            "podziemia rynku", "fabryka schindlera", "wieliczka", "kopalnia soli",
        )):
            return True

    # FIX #241 Kraków — Kino 7D / VR / pixel zamiast aktywności adventure
    if adv and any(k in name for k in (
        "kino 7d", "kino 7 d", "& vr", "7d & vr", "digital floor", "pixel xl",
    )):
        return True

    # FIX #241 Kraków — Lustrzany Labirynt poza dopasowanymi profilami
    if "lustrzany labirynt" in name:
        if style == "cultural":
            return True
        if tg == "couples" and ({"water_attractions", "relaxation"} & prefs):
            return True
        if adv and no_history:
            return True

    # FIX #241 Kraków — friends+history: Park Decjusza, Kopiec Wandy, Kładka
    if tg == "friends" and adv and {"underground", "history_mystery", "museum_heritage"} <= prefs:
        if any(k in name for k in (
            "park decjusza", "kopiec wandy", "kładka bernatka", "kladka bernatka",
            "stare miasto",
        )):
            return True

    # FIX #242 Warszawa — Pomnik Syreny (słaby filler we wszystkich planach)
    if any(k in name for k in (
        "pomnik syrenki", "pomnik syreny", "syrenki warszawskiej", "syreny warszawskiej",
    )):
        return True

    # FIX #242 Warszawa — friends+adventure+active_sport: PKiN/bulwary/muzea zamiast aktywności
    if tg == "friends" and adv and "active_sport" in prefs and "museum_heritage" not in prefs:
        if any(k in name for k in (
            "pałac kultury", "palac kultury", "pkin", "bulwary wiślane", "bulwary wislane",
            "ogrody zamku", "ogrod zamku", "muzeum fabryki norblina", "norblin",
            "centrum pieniądza", "centrum pieniadza", "muzeum sztuki nowoczesnej",
        )):
            return True

    # FIX #242 Warszawa — solo+nature+relax: miejskie fillery off
    if tg == "solo" and nat_relax:
        if any(k in name for k in (
            "browary warszawskie", "pałac prezydencki", "palac prezydencki",
            "most świętokrzyski", "most swietokrzyski",
        )):
            return True

    # FIX #242 Warszawa — friends+adventure+history: słabe mikro-atrakcje
    if tg == "friends" and adv and {"underground", "history_mystery"} <= prefs:
        if any(k in name for k in (
            "most świętokrzyski", "most swietokrzyski", "grób nieznanego", "grob nieznanego",
            "taras widokowy na dzwonnicy", "taras przy kościele", "plac europejski",
            "pałac prezydencki", "palac prezydencki", "ogrody zamku", "ogrod zamku",
        )):
            return True

    # FIX #242 Warszawa — taras przy kościele (micro filler)
    if any(k in name for k in (
        "taras widokowy na dzwonnicy", "taras przy kościele", "taras przy kosciolu",
    )):
        return True

    # FIX #242 Warszawa — friends+adventure+active_sport: taras/micro off
    if tg == "friends" and adv and "active_sport" in prefs:
        if any(k in name for k in (
            "taras widokowy na dzwonnicy", "taras przy kościele", "taras przy kosciolu",
        )):
            return True

    # FIX #243 Katowice — Spodek we wszystkich planach (słaby filler)
    if "spodek" in name:
        if tg == "family_kids":
            return True
        if tg == "solo" and nat_relax:
            return True
        if tg == "friends" and adv:
            return True
        if tg == "couples":
            return True

    # FIX #243 Katowice — Rynek dla family_kids i friends adventure
    if tg == "family_kids" and any(k in name for k in ("rynek w katowicach", "rynek katowic")):
        return True
    if tg == "friends" and adv and any(k in name for k in ("rynek w katowicach", "rynek katowic")):
        return True

    # FIX #243 Katowice — couples+cultural: kościół św. Anny
    if tg == "couples" and style == "cultural":
        if any(k in name for k in ("św. anny", "sw. anny")) and any(
            k in name for k in ("parafia", "kościół", "kosciol")
        ):
            return True

    # FIX #243 Katowice — solo+nature+relax: miejskie fillery off
    if tg == "solo" and nat_relax:
        if any(k in name for k in (
            "pijalnia czekolady", "muzeum historii katowic", "planetarium śląskie",
            "planetarium slaskie",
        )):
            return True

    # FIX #241 Kraków — couples+water+relax (json10)
    if tg == "couples" and {"water_attractions", "relaxation", "local_food_experience"} <= prefs:
        if _is_zoo(poi):
            return True
        if "zoo" in name and "mini" not in name:
            return True
        if any(k in name for k in (
            "kościół św. wojciecha", "sw. wojciecha", "nowa huta",
            "bazylika mariacka", "lustrzany labirynt",
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
    top_prefs = {_safe_str(p) for p in (user.get("preferences") or [])[:2]}
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
            delta += 85.0
        _day_active = int(ctx.get("day_active_count") or 0)
        if _day_active >= 1 and no_history:
            if any(k in name for k in ("muzeum", "galeri", "kościół", "bazylika", "katedra")):
                delta -= 90.0
            if any(k in name for k in ("rynek", "stare miasto", "plac ", "most ", "pomnik ")):
                delta -= 75.0

    # FIX #233 — balanced long trips: demote extra museums
    if style == "balanced":
        _trip_mus = int(ctx.get("trip_museum_count") or 0)
        _day_mus = int(ctx.get("day_museum_count") or 0)
        if "muzeum" in name and _day_mus >= 1 and "museum_heritage" not in top_prefs:
            delta -= 85.0
        if "muzeum" in name and _trip_mus >= 2 and "museum_heritage" not in top_prefs:
            delta -= 70.0
        if "muzeum" in name and day >= 3 and _trip_mus >= 1:
            delta -= 55.0

    # FIX #234 — adventure style: stronger active character, fewer museums/sightseeing
    if adv:
        if any(k in name for k in (
            "gojump", "bungee", "park linowy", "trampolin", "paintball", "escape",
            "kopalnia", "sztolnia", "hydropolis", "pixel", "kolejkowo",
        )):
            delta += 60.0
        if "muzeum" in name and "museum_heritage" not in top_prefs:
            delta -= 95.0
        if tg == "friends" and any(k in name for k in (
            "łazienki", "lazienki", "bulwar", "ogród na dachu", "ogrod na dachu",
            "muzeum sztuki nowoczesnej", "centrum pieniądza", "centrum pieniadza",
            "park decjusza", "park bednarskiego", "błonia", "blonia", "kładka bernatka",
            "kladka bernatka",
        )):
            delta -= 90.0

    # FIX #234 Kraków — solo+relax / seniors+relax demotes
    if tg == "solo" and (style == "relax" or "relaxation" in prefs):
        if any(k in name for k in ("kładka bernatka", "kladka bernatka", "park bednarskiego")):
            delta -= 90.0
    if tg == "seniors" and (style == "relax" or "relaxation" in prefs):
        if any(k in name for k in (
            "kościół św. wojciecha", "sw. wojciecha", "wieża ratuszowa", "wieza ratuszowa",
        )):
            delta -= 95.0

    # FIX #234 Kraków friends+adventure — calm parks/bridges
    if tg == "friends" and adv:
        if any(k in name for k in (
            "błonia krakowskie", "blonia krakowskie", "park decjusza", "park bednarskiego",
            "kładka bernatka", "kladka bernatka",
        )):
            delta -= 95.0

    # FIX #240 Wrocław — family_kids + relaxation: demote spider exhibit
    if tg == "family_kids" and "relaxation" in prefs:
        if any(k in name for k in ("pająk", "pajak", "spider", "wystawa pająk")):
            delta -= 100.0

    # FIX #240 Wrocław — Dworzec Świebodzki extra demote (ranking bazowy za wysoki)
    if any(k in name for k in ("dworzec świebodzki", "dworzec swiebodzki")):
        delta -= 120.0

    # FIX #240 Wrocław — Muzeum Motoryzacji Topacz bez dopasowanych preferencji
    if "motoryzacji" in name and "topacz" in name:
        if not ({"museum_heritage", "history_mystery"} & prefs):
            delta -= 90.0

    # FIX #240 Wrocław — Pigcasso słaby przy nature + museum (json8)
    if "pigcasso" in name and "nature_landscape" in prefs:
        delta -= 85.0

    # FIX #240 Wrocław — seniors + relax: max różnorodność, demote kolejne muzeum
    if tg == "seniors" and (style == "relax" or "relaxation" in prefs):
        _day_mus = int(ctx.get("day_museum_count") or 0)
        if "muzeum" in name and _day_mus >= 1:
            delta -= 95.0
        if any(k in name for k in (
            "park szczytnicki", "pergola", "bulwar", "wyspa słodowa", "wyspa slodowa",
            "ogród japoński", "ogrod japonski", "lasek", "las strzeli",
        )):
            delta += 90.0

    # FIX #240 Wrocław — dzień 1 bez dalekiego Arboretum Wojsławice (json9)
    if day == 1 and any(k in name for k in ("arboretum wojsławice", "arboretum wojslawice", "wojsławice")):
        delta -= 100.0
        if num_days >= 5:
            delta -= 50.0

    # FIX #240 Wrocław — nature + relaxation: więcej terenów zielonych
    if nat_relax and any(k in name for k in (
        "park szczytnicki", "pergola", "bulwar", "wyspa słodowa", "wyspa slodowa",
        "ogród japoński", "ogrod japonski", "lasek", "las strzeli", "rędziński",
        "redzinski", "odra", "zoo",
    )):
        delta += 70.0

    if tg == "family_kids" and any(k in name for k in (
        "hydropolis", "kolejkowo", "pixel xl", "pixel",
    )):
        delta += 95.0
    if tg == "family_kids" and "muzeum uniwersytetu" in name:
        delta -= 100.0

    # FIX #234 Warszawa — family kids interactive boosts / demotes
    if tg == "family_kids":
        if any(k in name for k in (
            "smart kids", "miniciti", "mini citi", "kolejkowo", "kopernik",
            "centrum nauki", "pixel xl", "pixel",
        )):
            delta += 100.0
        if any(k in name for k in ("bulwary wiślane", "bulwary wislane")):
            delta -= 85.0

    # FIX #234 Warszawa — couples+cultural needs more culture
    if tg == "couples" and style == "cultural":
        if any(k in name for k in ("muzeum", "galeria", "teatr", "opera", "filharmonia", "zamek", "pałac")):
            delta += 65.0

    # FIX #234 Warszawa — relax demote cemetery
    if (style == "relax" or "relaxation" in prefs) and any(k in name for k in (
        "cmentarz powązkowski", "cmentarz powazkowski", "powązk", "powazk",
    )):
        delta -= 95.0

    # FIX #234 Warszawa — friends+adventure calm spots
    if tg == "friends" and adv and any(k in name for k in (
        "łazienki królewskie", "lazienki krolewskie", "bulwary wiślane", "bulwary wislane",
        "ogród na dachu", "ogrod na dachu", "muzeum sztuki nowoczesnej",
        "centrum pieniądza", "centrum pieniadza",
    )):
        delta -= 90.0

    # FIX #243 Katowice — friends+adventure+history: industrial Śląsk boost (było błędnie demote)
    if tg == "friends" and adv and "history_mystery" in prefs:
        if any(k in name for k in (
            "kopalnia guido", "guido", "królowa luiza", "krolowa luiza",
            "carboneum", "galeria szyb wilson", "szyb wilson", "sztolnia",
        )):
            delta += 115.0

    # FIX #234 Katowice — relax demote churches
    if (style == "relax" or "relaxation" in prefs) and any(k in name for k in (
        "św. michała", "sw. michala", "parafia św. anny", "parafia sw. anny",
    )):
        delta -= 90.0

    # FIX #234 Poznań — micro heritage demote
    if any(k in name for k in (
        "plac wolności", "plac wolnosci", "trakt królewsko", "trakt krolewsko",
        "rynku jeżyckiego", "rynku jezyckiego", "rynek jeżycki",
    )):
        delta -= 90.0
    if tg == "friends" and adv and any(k in name for k in (
        "muzeum historii poznania", "domy kupieckie", "trakt królewsko", "trakt krolewsko",
    )):
        delta -= 95.0
    if tg == "couples" and style == "cultural" and "muzeum iluzji" in name:
        delta -= 85.0
    if tg == "family_kids" and "park adama mickiewicza" in name:
        delta -= 85.0
    if (style == "relax" or "relaxation" in prefs) and "trakt królewsko" in name:
        delta -= 80.0

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

    # ── FIX #235 — client feedback round 6 (global + per city) ──
    _trip_kids = int(ctx.get("trip_kids_attraction_count") or 0)

    # Family kids: parks/classic city only after top kids attractions used
    if tg == "family_kids" and _trip_kids < 2:
        if any(k in name for k in (
            "park ", "bulwar", "błonia", "blonia", "stare miasto", "rynek",
            "planty", "ogród botaniczny", "ogrod botaniczny", "spacer",
        )):
            delta -= 95.0
        if any(k in name for k in (
            "zoo", "aquapark", "hydropolis", "kolejkowo", "pixel", "papugarnia",
            "mini zoo", "smart kids", "miniciti", "kopernik", "centrum nauki",
        )):
            delta += 100.0

    # Wrocław FIX #235
    if tg == "family_kids":
        if any(k in name for k in ("rynek", "ostrów tumski", "ostrow tumski", "ogród botaniczny", "ogrod botaniczny")):
            if _trip_kids >= 1:
                delta -= 90.0
    if tg == "couples" and style == "cultural" and "city golf" in name:
        delta -= 100.0
    if any(k in name for k in ("dworzec świebodzki", "dworzec swiebodzki")):
        delta -= 110.0
    if tg == "solo" and (style == "relax" or "relaxation" in prefs) and "bastion sakwowy" in name:
        delta -= 95.0
    if tg == "solo" and (style == "relax" or "relaxation" in prefs) and "browar stu mostów" in name:
        delta -= 90.0

    # Kraków FIX #235
    if tg == "family_kids" and "park bednarskiego" in name:
        delta -= 100.0
    if tg == "family_kids" and any(k in name for k in ("bulwary wiślane", "bulwary wislane", "błonia", "blonia")):
        if _trip_kids < 2:
            delta -= 95.0
    if tg == "friends" and adv and "park decjusza" in name:
        delta -= 100.0

    # Katowice FIX #235
    if any(k in name for k in (
        "galeria szyb wilson", "szyb wilson", "muzeum historii katowic",
        "parafia św. anny", "parafia sw. anny",
    )):
        delta -= 95.0
    if tg == "family_kids" and any(k in name for k in (
        "śląskie centrum wolności", "slaskie centrum wolnosci",
        "kościół św. michała", "sw. michala", "świętego michała", "swietego michala",
        "michała archanioła", "michala archanioła", "rynek w katowicach", "rynek katowic",
    )):
        delta -= 100.0
    if tg == "seniors" and (style == "relax" or "relaxation" in prefs):
        if any(k in name for k in ("św. michała", "sw. michala", "muzeum historii katowic")):
            delta -= 95.0
    if tg == "friends" and adv and any(k in name for k in ("rynek w katowicach", "rynek katowic")):
        delta -= 90.0

    # Warszawa FIX #235
    if tg == "family_kids" and any(k in name for k in ("syrenk", "ogrody zamku", "ogrod zamku")):
        delta -= 90.0
    if style == "cultural" and any(k in name for k in ("bulwary wiślane", "bulwary wislane")):
        delta -= 70.0
    if tg == "friends" and adv and any(k in name for k in (
        "centrum pieniądza", "centrum pieniadza", "ogród na dachu", "ogrod na dachu",
        "muzeum sztuki nowoczesnej", "bulwary wiślane", "bulwary wislane",
    )):
        delta -= 95.0

    # Poznań FIX #235
    if any(k in name for k in (
        "domy kupieckie", "plac wolności", "plac wolnosci", "park adama mickiewicza",
        "rynek jeżycki", "rynek jezycki", "park jana pawła", "park jana pawla",
        "park stare koryto", "fort va", "fort bonin",
    )):
        delta -= 90.0
    if tg == "family_kids" and "pomnik bamberki" in name:
        delta -= 95.0
    if tg == "friends" and adv and any(k in name for k in (
        "park jana pawła", "park jana pawla", "park stare koryto",
    )):
        delta -= 95.0
    if tg == "couples" and (style == "relax" or "relaxation" in prefs):
        if "park stare koryto" in name:
            delta -= 85.0
    if tg == "seniors" and (style == "relax" or "relaxation" in prefs) and "fort va" in name:
        delta -= 100.0

    # ── FIX #241 Kraków client feedback ──
    if any(k in name for k in (
        "kładka bernatka", "kladka bernatka", "kładka ojca bernatka", "ojca bernatka",
    )):
        delta -= 150.0

    _trip_old_town = any(
        any(k in (tn or "") for k in (
            "rynek główny", "rynek glowny", "stare miasto", "sukiennice", "planty",
        ))
        for tn in trip_names
    )
    if _trip_old_town and name not in trip_names:
        if any(k in name for k in ("rynek główny", "rynek glowny", "stare miasto", "sukiennice")):
            delta -= 150.0
        elif any(k in name for k in ("rynek", "stare miasto")) and day >= 2:
            delta -= 120.0

    if tg == "seniors" and _trip_old_town:
        if any(k in name for k in ("rynek", "stare miasto", "bazylika mariacka")):
            delta -= 100.0

    if tg == "solo" and nat_relax and no_history:
        if any(k in name for k in (
            "podziemia rynku", "fabryka schindlera", "wieliczka", "kopalnia soli",
        )):
            delta -= 130.0
        if any(k in name for k in (
            "park ", "rezerwat", "bulwar", "dolina", "jaskinia", "las ", "skansen",
            "botaniczny", "zieleniec",
        )) and "wanda" not in name and "krakusa" not in name:
            delta += 95.0

    _child_age241 = user.get("children_age")
    if tg == "family_kids" and _child_age241 is not None:
        try:
            if int(_child_age241) <= 5:
                if any(k in name for k in (
                    "papugarnia", "kolejkowo", "pixel", "smoczy", "fabryka cukier",
                    "mini zoo", "park wodny", "aquapark", "fabryka cukierk",
                )):
                    delta += 120.0
                if any(k in name for k in (
                    "kładka bernatka", "kladka bernatka", "park decjusza", "kopiec wandy",
                )):
                    delta -= 110.0
        except (TypeError, ValueError):
            pass

    if "nowa huta" in name:
        delta -= 100.0
        if not ({"history_mystery", "museum_heritage"} & prefs):
            delta -= 60.0

    if ctx.get("ojcow_day_active") or ctx.get("excursion_day_active") == "region_ojcow":
        from app.domain.planner.engine import poi_geo_region_key
        if poi_geo_region_key(poi) != "region_ojcow":
            if not any(k in name for k in (
                "ojców", "ojcow", "maczuga", "pieskowa", "jaskinia",
            )):
                delta -= 145.0

    if adv and any(k in name for k in (
        "escape room", "escape ", "paintball", "park linowy", "gojump", "bungee",
    )):
        delta += 85.0
    if adv and any(k in name for k in ("kino 7d", "kino 7 d", "& vr")):
        delta -= 120.0

    if tg == "couples" and style == "cultural":
        if any(k in name for k in ("fabryka wódki", "fabryka wodki")):
            delta -= 40.0

    if tg == "friends" and adv and "kopiec wandy" in name:
        delta -= 110.0

    # ── FIX #242 Warszawa — client feedback json 1–10 ──
    _waw_filler = (
        "pałac prezydencki", "palac prezydencki", "most świętokrzyski", "most swietokrzyski",
        "grób nieznanego", "grob nieznanego", "taras widokowy na dzwonnicy",
        "plac europejski", "bazylika św. jana", "bazylika sw. jana",
    )
    if any(k in name for k in _waw_filler):
        delta -= 120.0

    if tg == "friends" and adv and "active_sport" in prefs:
        if any(k in name for k in ("kajak", "park linowy", "gokart", "escape", "paintball")):
            delta += 100.0
        if any(k in name for k in (
            "pałac kultury", "palac kultury", "pkin", "bulwary wiślane", "bulwary wislane",
        )):
            delta -= 120.0

    if tg == "friends" and adv and {"underground", "history_mystery"} <= prefs:
        if any(k in name for k in (
            "muzeum powstania", "podziemia", "schron", "krypta", "bunkier", "fort ",
            "muzeum wojska", "polin",
        )):
            delta += 90.0
        _day_hist = int(ctx.get("day_museum_count") or 0)
        if _day_hist >= 1 and any(k in name for k in (
            "most ", "pomnik ", "taras ", "grób", "grob", "plac europejski",
        )):
            delta -= 110.0

    if tg == "family_kids" and "kids_attractions" in prefs:
        if any(k in name for k in (
            "smart kids", "miniciti", "kopernik", "centrum nauki", "park wodny",
            "warszawianka", "zoo", "kolejkowo",
        )):
            delta += 90.0
        if day == 1 and any(k in name for k in (
            "bulwary wiślane", "bulwary wislane", "pałac kultury", "palac kultury", "pkin",
        )):
            delta -= 100.0

    if tg == "solo" and nat_relax:
        if any(k in name for k in (
            "ogród botaniczny", "ogrod botaniczny", "łazienki królewskie", "lazienki krolewskie",
            "bulwary", "palmiarnia", "jeziorko",
        )):
            delta += 75.0

    if num_days >= 5 and day >= 4:
        if any(k in name for k in _waw_filler):
            delta -= 90.0
        if "museum_heritage" in prefs and any(k in name for k in ("muzeum", "norblin", "zamek", "polin")):
            delta += 70.0

    # ── FIX #243 Katowice client feedback json 1–10 ──
    if "spodek" in name:
        delta -= 120.0
        if day == 1:
            delta -= 60.0

    if tg == "couples" and style == "cultural":
        if any(k in name for k in ("św. anny", "sw. anny")) and "parafia" in name:
            delta -= 120.0

    if tg == "friends" and adv:
        if any(k in name for k in ("rynek w katowicach", "rynek katowic")):
            delta -= 100.0
        if "spodek" in name:
            delta -= 80.0

    if tg == "solo" and nat_relax:
        if any(k in name for k in (
            "dolina trzech stawów", "dolina trzech stawow", "palmiarnia",
            "park śląski", "park slaski", "tężnia", "teznia", "nikiszowiec",
            "górnośląski park etnograficzny", "gornoslaski park etnograficzny",
        )):
            delta += 95.0

    if num_days >= 7 and day >= 4 and tg == "couples":
        if any(k in name for k in (
            "nikiszowiec", "kopalnia guido", "dolina trzech", "tężnia", "teznia",
            "palmiarnia", "carboneum",
        )):
            delta += 85.0
        if "spodek" in name:
            delta -= 100.0
        if any(k in name for k in ("św. anny", "sw. anny")) and "parafia" in name:
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
        "pixel xl", "escape", "paintball", "linowa", "kajak", "gokart",
    )
    return any(n in name for n in _active_names)
