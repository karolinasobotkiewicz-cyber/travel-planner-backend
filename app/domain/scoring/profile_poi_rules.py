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


def poi_trip_repeat_key(name: str) -> str | None:
    """FIX #245: fuzzy trip-level repeat key for filler POIs (Katowice cluster)."""
    n = _safe_str(name)
    _markers = (
        ("park kościuszki", "kat_park_kosciuszki"),
        ("park kosciuszki", "kat_park_kosciuszki"),
        ("rynek w katowicach", "kat_rynek"),
        ("pijalnia czekolady", "kat_wedel"),
        ("planetarium śląskie", "kat_planetarium"),
        ("planetarium slaskie", "kat_planetarium"),
        ("dolina trzech stawów", "kat_dolina"),
        ("dolina trzech stawow", "kat_dolina"),
        ("górnośląski park etnograficzny", "kat_park_etno"),
        ("gornoslaski park etnograficzny", "kat_park_etno"),
        ("muzeum historii katowic", "kat_muzeum_hist"),
        ("pixel xl", "kat_pixel"),
        ("kolejkowo", "kat_kolejkowo"),
        ("nikiszowiec", "kat_nikiszowiec"),
        ("tężnia", "kat_teznia"),
        ("teznia", "kat_teznia"),
        ("park wodny nemo", "kat_nemo"),
        ("nemo", "kat_nemo"),
        ("kościół św. michała", "kat_park_kosciuszki"),
        ("kosciol sw. michala", "kat_park_kosciuszki"),
        ("kosciol sw michala", "kat_park_kosciuszki"),
        ("świętego michała", "kat_park_kosciuszki"),
        ("swietego michala", "kat_park_kosciuszki"),
        ("michała archanioła", "kat_park_kosciuszki"),
        ("michala archaniola", "kat_park_kosciuszki"),
        ("parafia św. michała", "kat_park_kosciuszki"),
        ("parafia sw. michala", "kat_park_kosciuszki"),
        # FIX #247 Warszawa — powtarzalne mikro-fillery
        ("most świętokrzyski", "waw_most_swietokrzyski"),
        ("most swietokrzyski", "waw_most_swietokrzyski"),
        ("pałac prezydencki", "waw_palac_prezydencki"),
        ("palac prezydencki", "waw_palac_prezydencki"),
        ("ogrody zamku", "waw_ogrody_zamku"),
        ("ogrod zamku", "waw_ogrody_zamku"),
        ("plac europejski", "waw_plac_europejski"),
        ("centrum pieniądza", "waw_centrum_pieniadza"),
        ("centrum pieniadza", "waw_centrum_pieniadza"),
        ("browary warszawskie", "waw_browary"),
        # FIX #260 Warszawa — garden / park trip repeats
        ("ogród krasińskich", "waw_ogrod_krasinskich"),
        ("ogrod krasinskich", "waw_ogrod_krasinskich"),
        ("ogród saski", "waw_ogrod_saski"),
        ("ogrod saski", "waw_ogrod_saski"),
        # FIX #309: Kraków UJ garden before generic (Warsaw) botaniczny.
        ("ogród botaniczny uj", "krk_botaniczny"),
        ("ogrod botaniczny uj", "krk_botaniczny"),
        ("ogród botaniczny", "waw_ogrod_botaniczny"),
        ("ogrod botaniczny", "waw_ogrod_botaniczny"),
        ("łazienki królewskie", "waw_lazienki"),
        ("lazienki krolewskie", "waw_lazienki"),
        ("kampinos", "waw_kampinos"),
        # FIX #266: pool filler must not repeat across days
        ("warszawianka", "waw_warszawianka"),
        ("park wodny warszaw", "waw_warszawianka"),
        # FIX #267: iconic WAWA museums/palaces — never D1+D3 duplicates.
        # Must appear BEFORE Poznań "zamek królewski" marker (shared name).
        ("zamek królewski na wawelu", "krk_wawel"),
        ("zamek królewski", "waw_zamek_krolewski"),
        ("zamek krolewski", "waw_zamek_krolewski"),
        ("wilanów", "waw_wilanow"),
        ("wilanow", "waw_wilanow"),
        ("muzeum pałacu króla", "waw_wilanow"),
        ("muzeum palacu krola", "waw_wilanow"),
        ("muzeum pałacu król", "waw_wilanow"),
        # FIX #248 Wrocław — powtarzalne fillery
        ("wyspa słodowa", "wro_wyspa_slodowa"),
        ("wyspa slodowa", "wro_wyspa_slodowa"),
        ("hala stulecia", "wro_hala_stulecia"),
        ("dworzec świebodzki", "wro_dworzec"),
        ("dworzec swiebodzki", "wro_dworzec"),
        ("hydropolis", "wro_hydropolis"),
        ("rynek we wrocławiu", "wro_rynek"),
        ("rynek we wroclawiu", "wro_rynek"),
        ("hala targowa", "wro_hala_targowa"),
        ("bastion sakwowy", "wro_bastion"),
        ("most grunwaldzki", "wro_most_grunwaldzki"),
        ("centrum historii zajezdnia", "wro_zajezdnia"),
        # FIX #259 Wrocław — trip-level icons (client: ×2/×3 duplicates)
        ("muzeum narodowe", "wro_muzeum_narodowe"),
        ("pergola", "wro_pergola"),
        ("browar stu mostów", "wro_browar_stu"),
        ("browar stu mostow", "wro_browar_stu"),
        ("panorama racławicka", "wro_panorama"),
        ("panorama raclawicka", "wro_panorama"),
        ("kolejkowo", "wro_kolejkowo"),
        ("movie gate", "wro_movie_gate"),
        # FIX #265: Park Mamuta must not spam across days
        ("park mamuta", "wro_park_mamuta"),
        ("mamuta", "wro_park_mamuta"),
        # FIX #268: Wrocław icons — client ×3–×7 trip spam (Iluzja/Aquapark/Topacz/Katedra)
        ("świat iluzji", "wro_swiat_iluzji"),
        ("swiat iluzji", "wro_swiat_iluzji"),
        ("muzeum iluzji", "wro_swiat_iluzji"),
        ("aquapark", "wro_aquapark"),
        ("park wodny", "wro_aquapark"),
        ("słoneczny park", "wro_aquapark"),
        ("sloneczny park", "wro_aquapark"),
        ("zamek topacz", "wro_topacz"),
        ("muzeum motoryzacji i techniki zamek topacz", "wro_topacz"),
        ("topacz", "wro_topacz"),
        ("paintball", "wro_paintball"),
        ("citypaintball", "wro_paintball"),
        ("fort przygody", "wro_paintball"),
        ("katedra wrocławska", "wro_katedra"),
        ("katedra wroclawska", "wro_katedra"),
        ("pana tadeusza", "wro_pana_tadeusza"),
        ("pan tadeusz", "wro_pana_tadeusza"),
        # FIX #249 Poznań — powtarzalne fillery centrum
        # (Zamek Królewski trip key is shared via waw_zamek_krolewski above —
        # FIX #267 — same POI name in WAWA/POZ; one key per trip is enough.)
        ("stary rynek w poznaniu", "poz_stary_rynek"),
        ("ratusz w poznaniu", "poz_ratusz"),
        ("park adama mickiewicza", "poz_park_mickiewicza"),
        ("makieta dawnego poznania", "poz_makieta"),
        ("zamek cesarski", "poz_zamek_cesarski"),
        ("domy kupieckie", "poz_domy_kupieckie"),
        ("okrąglak", "poz_okraglak"),
        ("okraglak", "poz_okraglak"),
        # FIX #254: treat similar forts / trampoline parks as one trip slot.
        ("fort iii", "poz_fort_cluster"),
        ("fort va", "poz_fort_cluster"),
        ("fort v ", "poz_fort_cluster"),
        ("jump arena", "poz_trampoline_cluster"),
        ("flypark", "poz_trampoline_cluster"),
        ("fly park", "poz_trampoline_cluster"),
        ("park jordana", "krk_park_jordana"),
        ("city golf", "wro_city_golf"),
        # FIX #255: LEGO / bricks cluster — one slot per trip day.
        ("bricks & figs", "krk_lego_cluster"),
        ("bricks and figs", "krk_lego_cluster"),
        ("bricks &figs", "krk_lego_cluster"),
        ("świat w budowie", "krk_lego_cluster"),
        ("swiat w budowie", "krk_lego_cluster"),
        ("legoland", "krk_lego_cluster"),
        ("wielka wystawa klock", "krk_lego_cluster"),
        # FIX #288: trip-level icons the client saw twice in a row.
        ("loopys", "wro_loopys"),
        # FIX #289: Wrocław icons that densify re-planted after the trip strip.
        ("ogród japoński", "wro_ogrod_japonski"),
        ("ogrod japonski", "wro_ogrod_japonski"),
        ("muzeum przyrodnicze", "wro_muzeum_przyrodnicze"),
        ("przyrodnicze we wrocławiu", "wro_muzeum_przyrodnicze"),
        ("katedra wawelska", "krk_katedra_wawel"),
        ("zakrzówek", "krk_zakrzowek"),
        ("zakrzowek", "krk_zakrzowek"),
        ("błonia", "krk_blonia"),
        ("blonia", "krk_blonia"),
        ("ogród doświadczeń", "krk_doswiadczen"),
        ("ogrod doswiadczen", "krk_doswiadczen"),
        ("funhouse", "kat_funhouse"),
        ("fun house", "kat_funhouse"),
        ("fun-house", "kat_funhouse"),
        # FIX #290: leftover trip icons across WAWA / KRK / KAT / POZ.
        ("archikatedr", "waw_archikatedra"),
        ("zamek ujazdowski", "waw_ujazdowski"),
        ("wioski świata", "krk_wioski"),
        ("wioski swiata", "krk_wioski"),
        ("funzeum", "kat_funzeum"),
        ("park chopina", "kat_park_chopina"),
        ("fryderyka chopina", "kat_park_chopina"),
        ("chopina", "kat_park_chopina"),
        ("park śląski", "kat_park_slaski"),
        ("park slaski", "kat_park_slaski"),
        ("park chrobrego", "kat_park_chrobrego"),
        ("park pileckiego", "kat_park_pilecki"),
        ("park pilecki", "kat_park_pilecki"),
        ("pileckiego", "kat_park_pilecki"),
        ("muzeum śląskie", "kat_muzeum_slaskie"),
        ("muzeum slaskie", "kat_muzeum_slaskie"),
        ("muzeum historii katowic", "kat_mhk"),
        ("muzeum czekolady", "poz_muzeum_czekolady"),
        ("żywego motyla", "krk_motyl"),
        ("zywego motyla", "krk_motyl"),
        ("muzeum motyla", "krk_motyl"),
        # FIX #292: leftover trip icons WRO/KRK/WAWA/KAT/POZ.
        ("park decjusza", "krk_park_decjusza"),
        # FIX #307: Poznań Park Cytadela before generic "cytadela" (Warsaw).
        ("park cytadela", "poz_park_cytadela"),
        ("cytadela", "waw_cytadela"),
        # FIX #295: X Pawilon on D4+D5.
        ("x pawilon", "waw_x_pawilon"),
        ("pawilon x", "waw_x_pawilon"),
        ("muzeum powstania", "waw_powstanie"),
        ("ogród na dachu", "waw_ogrod_dachu"),
        ("ogrod na dachu", "waw_ogrod_dachu"),
        ("dachu biblioteki", "waw_ogrod_dachu"),
        ("stacja muzeum", "waw_stacja_muzeum"),
        ("bazylika archikatedral", "waw_archikatedra"),
        ("park bednarskiego", "krk_bednarskiego"),
        ("stary rynek", "poz_stary_rynek"),
        ("park wilsona", "poz_park_wilsona"),
        ("giszowiec", "kat_giszowiec"),
        ("paprocan", "kat_paprocany"),
        ("hala stulecia", "wro_hala_stulecia"),
        ("park sensoryczny", "kat_sensoryczny"),
        ("animalworld", "kat_animalworld"),
        ("animal world", "kat_animalworld"),
        ("pomnik bamberki", "poz_stary_rynek"),
        ("bamberki", "poz_stary_rynek"),
    )
    for marker, key in _markers:
        if marker in n:
            return key
    return None


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

    # FIX #233/#287 Warszawa — Cmentarz Powązkowski
    if any(k in name for k in (
        "cmentarz powązkowski", "cmentarz powazkowski", "powązk", "powazk",
    )):
        if tg == "family_kids":
            return True
        # Nature + relax opener is a cemetery — never a match.
        if nat_relax and style == "relax":
            return True

    # FIX #258: MiniCiti is for ages 7–15 — never for toddlers (boosts used to win).
    if any(k in name for k in ("miniciti", "mini citi")):
        if child_age is not None and isinstance(child_age, (int, float)) and child_age < 7:
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

    # FIX #264: Park Linowy is high-intensity — never for relax / cultural /
    # nature+relaxation solo days (client WAWA json 8/9).
    if "park linowy" in name or ("linowy" in name and "park" in name):
        if (
            style in ("relax", "cultural")
            or "relaxation" in prefs
            or nat_relax
            or tg in ("seniors",)
        ):
            return True

    # FIX #266: Warszawianka / indoor pool is filler when water is not a pref
    # (client: json4/8/9 — doesn't match nature/relax/museum profiles).
    if any(k in name for k in ("warszawianka", "park wodny warszaw")):
        if "water_attractions" not in prefs and "active_sport" not in prefs:
            if style in ("relax", "cultural") or "relaxation" in prefs or nat_relax:
                return True
            if tg in ("solo", "seniors", "couples") and style == "balanced":
                # Still allow occasional pool day only when explicitly watery.
                if not ({"nature_landscape", "museum_heritage"} & prefs):
                    return False
                return True

    # FIX #282: water parks off city-sightseeing profiles (Wrocław json4 D4).
    if any(k in name for k in ("aquapark", "park wodny", "wodny park", "słoneczny park")):
        if "water_attractions" not in prefs and "kids_attractions" not in prefs:
            if "active_sport" not in prefs:
                if tg in ("solo", "seniors", "couples") or style in (
                    "cultural", "balanced", "relax",
                ):
                    return True

    # FIX #265: Park Mamuta is kids-only — never for adult profiles.
    if "mamuta" in name and tg not in ("family_kids", "family"):
        return True

    # FIX #274 Wrocław: Bobolandia / Kosmopark are kids-only.
    if "bobolandia" in name and tg not in ("family_kids", "family"):
        return True
    if "kosmopark" in name:
        if tg not in ("family_kids", "family") and "kids_attractions" not in prefs:
            return True

    if any(k in name for k in ("wioski świata", "wioski swiata", "ogród doświadczeń", "ogrod doswiadczen")):
        if tg == "couples" and style == "cultural":
            return True

    if any(k in name for k in ("katedra wawelska",)):
        if tg == "family_kids" and (style == "relax" or "relaxation" in prefs):
            if "history_mystery" not in prefs and "museum_heritage" not in prefs:
                return True

    if "hala stulecia" in name:
        if "museum_heritage" not in prefs and "history_mystery" not in prefs:
            if prefs & {"water_attractions", "local_food_experience", "relaxation",
                        "active_sport", "kids_attractions", "nature_landscape"}:
                return True

    if "muzeum narodowe" in name:
        if "museum_heritage" not in prefs and "history_mystery" not in prefs:
            return True

    # FIX #274: Flyspot / Laser Tag off seniors; Laser Tag needs active_sport.
    if tg == "seniors" and any(k in name for k in ("flyspot", "laser tag", "lasertag", "kosmopark")):
        return True
    _laser = (
        "laser tag" in name or "lasertag" in name or "laser-tag" in name
        or ("laser" in name and any(k in name for k in ("tag", "arena", "game", "factory")))
    )
    if _laser and "active_sport" not in prefs:
        return True
    if _laser and (style == "cultural" or tg == "couples") and "active_sport" not in prefs:
        return True
    if "flyspot" in name:
        limit = user.get("daily_limit")
        if limit is None:
            budget = user.get("budget") or {}
            if isinstance(budget, dict):
                limit = budget.get("daily_limit")
        try:
            ticket = float(
                poi.get("ticket_normal")
                or poi.get("Ticket")
                or poi.get("cost_estimate")
                or 299
            )
        except (TypeError, ValueError):
            ticket = 299.0
        if limit is not None and ticket > float(limit):
            return True

    # FIX #283: GoJump / paintball / Flyspot are active-play, not
    # cultural / relax / seniors days (Wrocław json 2/6/9).
    # FIX #288: go-karts / escape rooms are active-play, not cultural or relax.
    _active_play = any(k in name for k in (
        "gojump", "go jump", "trampolin", "paintball",
        "citypaintball", "city paintball", "flyspot", "fly spot",
        "gokart", "go-kart", "go kart", "karting",
        "let me out", "escape room", "escape-room",
        "tepfactor", "tep factor",
        "spływ", "splyw", "ponton",
    ))
    if _active_play:
        if tg == "seniors":
            return True
        if style in ("relax", "cultural"):
            return True
        if "relaxation" in prefs and "active_sport" not in prefs and not adv:
            return True
        # FIX #284: GoJump is not a nature/food/museum filler (Kraków json8/9).
        if "active_sport" not in prefs and not adv and "kids_attractions" not in prefs:
            return True

    # FIX #284: Bricks & Figs is a kids/LEGO stop, not nature+museum days.
    if any(k in name for k in ("bricks & figs", "bricks and figs", "bricks&figs")):
        if tg not in ("family_kids", "family") and "kids_attractions" not in prefs:
            return True

    # FIX #285/#290: Funzeum / FunHouse / JUMPCITY are kids indoor parks.
    if any(k in name for k in (
        "funzeum", "funhouse", "fun house", "fun-house",
        "jumpcity", "jump city", "jump-city",
    )):
        if tg not in ("family_kids", "family") and "kids_attractions" not in prefs:
            return True

    if "grawitacja" in name or "parkour" in name:
        if style in ("relax", "cultural") or "relaxation" in prefs:
            if "active_sport" not in prefs and not adv:
                return True

    if any(k in name for k in ("bajkowy labirynt", "guliwer", "holiday park")):
        if tg not in ("family_kids", "family") and "kids_attractions" not in prefs:
            return True

    # FIX #309: butterfly museum is filler on underground/history adventure days.
    if any(k in name for k in ("żywego motyla", "zywego motyla", "muzeum motyla")):
        if tg == "friends" and adv and (
            "underground" in prefs or "history_mystery" in prefs
        ):
            if "kids_attractions" not in prefs:
                return True

    if "cybermagia" in name:
        # FIX #308: VR is a weak cultural match (Katowice json 2).
        if style == "cultural":
            return True
        if style == "relax" or nat_relax:
            if "active_sport" not in prefs:
                return True

    if any(k in name for k in ("bazylika", "archikatedr")):
        if "history_mystery" not in prefs and "museum_heritage" not in prefs:
            if (
                tg == "family_kids"
                or style in ("relax", "adventure")
                or "relaxation" in prefs
                or "kids_attractions" in prefs
            ):
                return True

    # FIX #301: AnimalWorld is a petting zoo, not museum/nature/relax coverage.
    if "animalworld" in name or "animal world" in name:
        if tg == "seniors" and "kids_attractions" not in prefs:
            if prefs & {"museum_heritage", "nature_landscape", "relaxation"}:
                return True

    if "papugarn" in name:
        if tg not in ("family_kids", "family") and "kids_attractions" not in prefs:
            return True
        # FIX #288: parrot house is not nature/relax/underground coverage.
        if "kids_attractions" not in prefs and not (
            {"nature_landscape", "relaxation"} <= prefs
        ):
            if style in ("relax", "cultural") or tg in ("solo", "seniors", "couples"):
                if "active_sport" not in prefs:
                    return True

    # FIX #288: Wystawa Pająków is a curiosity exhibit, not museum_heritage.
    if any(k in name for k in ("wystawa pająków", "wystawa pajakow", "pająków", "pajakow")):
        if "kids_attractions" not in prefs and tg not in ("family_kids", "family"):
            if style in ("cultural", "relax") or "museum_heritage" in prefs:
                if "active_sport" not in prefs and "kids_attractions" not in prefs:
                    # Keep for families; drop as a fake museum on cultural days.
                    if tg in ("couples", "seniors", "solo"):
                        return True

    if any(k in name for k in ("muzeum śląskie", "muzeum slaskie")):
        if "museum_heritage" not in prefs and "history_mystery" not in prefs:
            if prefs & {"water_attractions", "local_food_experience", "relaxation"}:
                return True

    # FIX #296: dry civic museum / skansen are a poor fit for young kids.
    if tg == "family_kids":
        if "muzeum historii katowic" in name:
            return True
        if child_age is not None and isinstance(child_age, (int, float)) and child_age <= 6:
            if any(k in name for k in (
                "skansen", "etnograficzn", "nikiszowiec",
                "górnośląski park etnograficzny", "gornoslaski park etnograficzny",
            )):
                return True

    # FIX #308: Szyb Wilson is a weak family_kids match.
    if tg == "family_kids" and any(
        k in name for k in ("galeria szyb wilson", "szyb wilson")
    ):
        return True

    # FIX #308: friends+adventure must not burn a Gliwice hop on Chopina lawn.
    if "chopina" in name and tg == "friends" and adv:
        return True
    if any(k in name for k in ("park śląski", "park slaski")):
        if (
            tg == "friends"
            and adv
            and "active_sport" in prefs
            and "nature_landscape" not in prefs
        ):
            return True

    if any(k in name for k in (
        "park chopina", "park chrobrego", "park sensoryczny",
        "pogoria", "park pileckiego", "park pilecki", "pileckiego",
    )):
        # FIX #296: adventure / active_sport must not burn a 30 km hop on a lawn.
        if "nature_landscape" not in prefs and (
            style == "adventure"
            or "active_sport" in prefs
            or {"underground", "history_mystery"} <= prefs
            or ("museum_heritage" in prefs and "active_sport" not in prefs)
        ):
            return True

    if any(k in name for k in ("panorama racławicka", "panorama raclawicka")):
        if "museum_heritage" not in prefs and "history_mystery" not in prefs:
            return True

    if "polin" in name or "muzeum historii żydów" in name or "muzeum historii zydow" in name:
        if "museum_heritage" not in prefs and "history_mystery" not in prefs:
            if tg == "family_kids" and "kids_attractions" in prefs:
                pass
            else:
                return True

    if "muzeum powstania" in name:
        if tg == "family_kids":
            return True
        if nat_relax and "history_mystery" not in prefs and "museum_heritage" not in prefs:
            return True

    if any(k in name for k in ("górka szczęśliwick", "gorka szczesliwick")):
        if "active_sport" not in prefs and "kids_attractions" not in prefs:
            return True

    if any(k in name for k in ("fabryka czekolady", "manufaktura czekolady")):
        if "local_food_experience" not in prefs and "kids_attractions" not in prefs:
            if style in ("relax", "cultural") or nat_relax:
                return True

    if any(k in name for k in ("muzeum polskiej wódki", "muzeum polskiej wodki", "polskiej wódki")):
        if "local_food_experience" not in prefs and "museum_heritage" not in prefs:
            return True

    if "paprocany" in name:
        if "underground" in prefs and "nature_landscape" not in prefs:
            return True
        if style == "relax" and "nature_landscape" not in prefs and "water_attractions" not in prefs:
            return True

    if any(k in name for k in ("kopiec powstania",)):
        if "water_attractions" in prefs and "museum_heritage" not in prefs and "history_mystery" not in prefs:
            return True

    # FIX #274/#283/#288: winter-closed outdoor / seasonal sites.
    _date = user.get("start_date") or user.get("date")
    if _date:
        try:
            from app.domain.filters.seasonality import derive_season
            if derive_season(_date) == "winter":
                if any(k in name for k in (
                    "grabowy labirynt",
                    "ogród doświadczeń", "ogrod doswiadczen",
                    "jaskinia ciemna",
                    "jaskinia łokietka", "jaskinia lokietka",
                )):
                    return True
        except Exception:
            pass

    if any(k in name for k in (
        "aquapark", "park wodny", "wodny park", "wodny park tychy", "nemo",
    )):
        if "water_attractions" not in prefs and "kids_attractions" not in prefs:
            return True

    if any(k in name for k in ("królowa luiza", "krolowa luiza")):
        if tg not in ("family_kids", "family") and "kids_attractions" not in prefs:
            return True
    if ("kopalnia guido" in name or name.strip() == "guido") and tg == "family_kids":
        return True

    if any(k in name for k in ("muzeum śląskie", "muzeum slaskie")):
        if tg == "family_kids" and (style == "relax" or "relaxation" in prefs):
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

    # FIX #254: City Golf — remove from plans (client: does not fit preferences).
    if "city golf" in name:
        return True

    # FIX #255: Muzeum Wsi Mazowieckiej w Sierpcu — too far / not Warsaw trip.
    if any(k in name for k in ("muzeum wsi mazowieckiej", "sierpc")):
        return True

    # FIX #255/#255b: Wedel / Pijalnia — off wrong profiles (not a day anchor).
    if any(k in name for k in ("pijalnia czekolady", "pijalnia wedla", "wedel")):
        if "underground" in prefs or "active_sport" in prefs:
            return True
        if tg == "friends" and adv:
            return True
        # Family wants kids icons (Legendia/Zoo), not chocolate as the day lead.
        if tg == "family_kids" and "kids_attractions" in prefs:
            return True
        # Couples water+relax — chocolate is not a water/relax cover.
        if tg == "couples" and "water_attractions" in prefs:
            return True

    # FIX #255 Warszawa json7: Kopernik / park wodny off friends+adventure+underground.
    if tg == "friends" and adv and "underground" in prefs:
        if any(k in name for k in (
            "centrum nauki kopernik", "kopernik",
        )):
            return True
        if "water_attractions" not in prefs and any(
            k in name for k in ("park wodny", "warszawianka")
        ):
            return True

    # FIX #255: House of Air — not for non-active profiles (Katowice).
    if "house of air" in name and "active_sport" not in prefs and not adv:
        return True

    # FIX #255: House of Spices — poor family+young-kids fit (Wrocław).
    if "house of spices" in name and tg == "family_kids":
        return True

    # FIX #254: adventure — no Pergola / Wyspa / Japanese garden filler.
    if adv and any(k in name for k in (
        "pergola", "wyspa słodowa", "wyspa slodowa",
        "ogród japoński", "ogrod japonski",
    )):
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
        "muzeum uniwesytetu", "uniwesytetu",
    )):
        return True

    # FIX #248 Wrocław — Hala Targowa off family_kids (json1)
    if tg == "family_kids" and "hala targowa" in name:
        return True

    # FIX #248/#255 Wrocław — Pigcasso off non-kids / wrong-profile trips.
    if "pigcasso" in name:
        if tg == "couples" and {"museum_heritage", "relaxation"} <= prefs:
            return True
        if tg == "friends" and adv and "kids_attractions" not in prefs:
            return True
        if "nature_landscape" in prefs and "kids_attractions" not in prefs:
            return True
        if tg in ("seniors", "solo") and "kids_attractions" not in prefs:
            return True

    # FIX #248 Wrocław — Hala Targowa off seniors relax (json6)
    if tg == "seniors" and (style == "relax" or {"relaxation", "nature_landscape"} <= prefs):
        if "hala targowa" in name:
            return True

    # FIX #268: Świat Iluzji is a weak fit for seniors (museum/nature/relax trips).
    if tg == "seniors" and any(k in name for k in ("świat iluzji", "swiat iluzji", "muzeum iluzji")):
        return True
    # FIX #269: Iluzja is a filler, not underground/history/nature/relax.
    if any(k in name for k in ("świat iluzji", "swiat iluzji", "muzeum iluzji")):
        if tg != "family_kids" and "kids_attractions" not in prefs:
            if prefs & {"underground", "nature_landscape", "relaxation"} and "museum_heritage" not in prefs:
                return True
            if "underground" in prefs and "kids_attractions" not in prefs:
                return True

    # FIX #269: Hala Stulecia is architecture, not underground/adventure.
    if "hala stulecia" in name:
        if tg == "friends" and adv and "underground" in prefs:
            if "kids_attractions" not in prefs:
                return True

    # FIX #274: gardens off underground + history + museum + adventure.
    if tg == "friends" and adv and "underground" in prefs:
        if any(k in name for k in (
            "ogród japoński", "ogrod japonski",
            "ogród botaniczny", "ogrod botaniczny",
            "park szczytnicki",
        )):
            return True

    # FIX #248 Wrocław — Fort Przygody/paintball off history+museum bez active_sport (json7)
    if tg == "friends" and adv and "active_sport" not in prefs:
        if any(k in name for k in (
            "fort przygody", "paintball", "quad", "kosmopark", "laser tag",
            "gojump", "citypaintball", "jumpcity", "pitlane", "gokart", "gokarty",
            "aquapark", "kosmopark",
        )):
            return True

    # FIX #248 Wrocław — Fort Przygody/paintball off history+museum bez active_sport (json7)
    if any(k in name for k in ("katedra wrocławska", "katedra wroclawska")):
        if tg == "couples" and {"water_attractions", "relaxation"} <= prefs:
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
        if tg == "seniors" and (style == "relax" or {"relaxation", "nature_landscape"} <= prefs):
            return True
        if tg == "solo" and (style == "relax" or nat_relax):
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
    if ("św. anny" in name or "sw. anny" in name) and prefs & {
        "water_attractions", "nature_landscape", "relaxation",
        "mountain_trails", "kids_attractions", "active_sport",
        "local_food_experience",
    }:
        if "kościół" in name or "kosciol" in name or "parafia" in name:
            return True
    # FIX #273: water+relax couples — kościół św. Anny is not a water day.
    if "water_attractions" in prefs and ("św. anny" in name or "sw. anny" in name):
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

    # FIX #271 Kraków — Park Jordana is a weak cultural/museum match.
    if "park jordana" in name:
        if style == "cultural":
            return True
        if tg == "couples" and "museum_heritage" in prefs and "kids_attractions" not in prefs:
            return True

    # FIX #272 Poznań — Jump Arena is sport, not a default filler.
    if "jump arena" in name and "active_sport" not in prefs:
        return True

    # FIX #272 Poznań — Zamek Cesarski is a weak kids+relax match.
    if "zamek cesarski" in name and tg == "family_kids":
        if "kids_attractions" in prefs or "relaxation" in prefs:
            if "museum_heritage" not in prefs and "history_mystery" not in prefs:
                return True

    # FIX #286: Cesarski is a weak water+food+relax couples match.
    if "zamek cesarski" in name:
        if {"water_attractions", "local_food_experience", "relaxation"} <= prefs:
            if "museum_heritage" not in prefs and "history_mystery" not in prefs:
                return True

    # FIX #286: Bazylika off friends+adventure (json 3).
    if tg == "friends" and adv and any(k in name for k in ("bazylika",)):
        if "museum_heritage" not in prefs:
            return True

    # FIX #286: parks off underground/history adventure when nature is not asked.
    if tg == "friends" and adv and {"underground", "history_mystery"} <= prefs:
        if "nature_landscape" not in prefs and any(
            k in name for k in (
                "park ", "park.", "ogród", "ogrod", "wilson", "sołack", "solack",
                "wodziczk", "cytadela",
            )
        ):
            if not any(k in name for k in ("fort ", "podziem", "szachty")):
                return True

    # FIX #271 Kraków — Park Lotników is not adventure/underground/history.
    if "park lotników" in name or "park lotnikow" in name:
        if adv and ({"underground", "history_mystery"} & prefs) and "nature_landscape" not in prefs:
            return True
        if style == "cultural" and "museum_heritage" in prefs:
            return True

    # FIX #241 Kraków — Lustrzany Labirynt poza dopasowanymi profilami
    if "lustrzany labirynt" in name:
        if style == "cultural":
            return True
        if tg == "couples" and ({"water_attractions", "relaxation"} & prefs):
            return True
        if tg == "couples" and "kids_attractions" not in prefs:
            if "nature_landscape" in prefs or "museum_heritage" in prefs:
                return True
        if adv and no_history:
            return True

    # FIX #246 Kraków — Alvernia Planet off nature-led solo (json4)
    if "alvernia planet" in name:
        if tg == "solo" and "nature_landscape" in prefs:
            return True

    # FIX #246 Kraków — Be Happy Museum off couples nature (json8)
    if "be happy museum" in name:
        if tg == "couples" and "nature_landscape" in prefs and "kids_attractions" not in prefs:
            return True

    # FIX #247 Warszawa — Centrum Pieniądza off solo relax/nature (json9)
    if any(k in name for k in ("centrum pieniądza", "centrum pieniadza")):
        if tg == "solo" and (style == "relax" or {"relaxation", "nature_landscape"} <= prefs):
            return True
        if tg == "couples" and {"water_attractions", "relaxation"} <= prefs:
            return True

    # FIX #247 Warszawa — Plac Europejski (słaby filler)
    if "plac europejski" in name:
        if tg == "couples" and {"water_attractions", "relaxation"} <= prefs:
            return True

    # FIX #247 Warszawa — couples museum/relax: Most + Pałac Prezydencki (json2)
    if tg == "couples" and "museum_heritage" in prefs and "relaxation" in prefs:
        if any(k in name for k in (
            "most świętokrzyski", "most swietokrzyski",
            "pałac prezydencki", "palac prezydencki",
        )):
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

    # FIX #270: Browary is nightlife/food, not kids+nature.
    if "browary warszawskie" in name:
        if tg == "family_kids" and "local_food_experience" not in prefs:
            return True

    # FIX #242 Warszawa — solo+nature+relax: miejskie fillery off
    if tg == "solo" and nat_relax:
        if any(k in name for k in (
            "browary warszawskie", "pałac prezydencki", "palac prezydencki",
            "most świętokrzyski", "most swietokrzyski",
        )):
            return True

    # FIX #247 Warszawa — solo+nature: Most / Pałac Prezydencki (json4)
    if tg == "solo" and "nature_landscape" in prefs:
        if any(k in name for k in (
            "most świętokrzyski", "most swietokrzyski",
            "pałac prezydencki", "palac prezydencki",
        )):
            return True

    # FIX #247 Warszawa — couples water+relax: Pałac Prezydencki (json10)
    if tg == "couples" and {"water_attractions", "relaxation"} <= prefs:
        if any(k in name for k in ("pałac prezydencki", "palac prezydencki", "grób nieznanego", "grob nieznanego")):
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
        if "muzeum" in name and not ({"museum_heritage", "history_mystery"} & prefs):
            return True

    # FIX #245 Katowice — couples water: planetarium off
    if tg == "couples" and "water_attractions" in prefs:
        if "planetarium" in name:
            return True

    # FIX #273: Planetarium is not active_sport coverage (Katowice json3).
    if "planetarium" in name and "active_sport" in prefs and adv:
        return True

    # FIX #244 Poznań — micro heritage off friends adventure
    if tg == "friends" and adv:
        if any(k in name for k in (
            "okrąglak", "okraglak", "ratusz w poznaniu", "domy kupieckie",
        )):
            return True
        if "ratusz" in name and "poznaniu" in name:
            return True

    # FIX #244 Poznań — Pixel XL off history/underground friends
    if tg == "friends" and adv and {"underground", "history_mystery", "museum_heritage"} <= prefs:
        if "pixel xl" in name or "pixel" in name:
            return True

    # FIX #307: Okrąglak is a weak pick for a family with an 8-year-old.
    if tg == "family_kids" and any(k in name for k in ("okrąglak", "okraglak")):
        return True

    # FIX #249 Poznań — Pixel XL / Pomnik Ofiar off family 5 lat (json5)
    _child_age249 = user.get("children_age")
    if tg == "family_kids" and _child_age249 is not None:
        try:
            if int(_child_age249) <= 5:
                if "pixel xl" in name or ("pixel" in name and "pozna" in name):
                    return True
                if "pomnik ofiar czerwca" in name:
                    return True
            # FIX #297: Muzeum Instrumentów is a weak kids match (36 min filler).
            if int(_child_age249) <= 6 and any(
                k in name for k in (
                    "muzeum instrument", "instrumentów muzycz",
                    "instrumentow muzycz",
                )
            ):
                return True
        except (TypeError, ValueError):
            pass

    # FIX #249 Poznań — Muzeum Bambrów off friends underground (json7)
    if tg == "friends" and adv and {"underground", "history_mystery", "museum_heritage"} <= prefs:
        if any(k in name for k in ("muzeum bambrów", "muzeum bambrow")):
            return True

    # FIX #249 Poznań — Makieta off active_sport+friends (json3)
    if tg == "friends" and adv and {"active_sport", "history_mystery"} <= prefs:
        if "makieta dawnego poznania" in name:
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
            # FIX #260: rope parks are not green relaxation.
            if "linowy" not in name:
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
            # FIX #260: Park Linowy ≠ park spacerowy.
            if "linowy" not in name:
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
        delta -= 200.0

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
        "dolina trzech stawów", "dolina trzech stawow", "park śląski", "park slaski",
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

    # FIX #243 Katowice — friends+adventure+history: industrial Śląsk boost (Wilson demote)
    if tg == "friends" and adv and "history_mystery" in prefs:
        if any(k in name for k in (
            "kopalnia guido", "guido", "królowa luiza", "krolowa luiza",
            "carboneum", "sztolnia", "jumpcity",
        )):
            delta += 115.0
        if "kopalnia guido" in name or (name.strip() == "guido"):
            delta += 80.0
        if "królowa luiza" in name or "krolowa luiza" in name:
            delta += 70.0
        if any(k in name for k in ("galeria szyb wilson", "szyb wilson")):
            delta -= 110.0
        if any(k in name for k in ("muzeum śląskie", "muzeum slaskie")) and "active_sport" in prefs:
            delta -= 90.0

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
        "gojump", "park linowy", "trampolin", "house of air", "aquapark",
        "bungee", "hydropolis", "paintball", "escape", "linowa",
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

    # FIX #308: active_sport days must actually pick sport POIs.
    if "active_sport" in prefs:
        if any(k in name for k in (
            "jumpcity", "jump city", "gojump", "park linowy", "legendia",
            "funhouse", "fun house", "pitlane", "gokart", "paintball",
        )):
            delta += 120.0

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

    # ── FIX #244 Poznań client feedback json 1–10 ──
    if any(k in name for k in ("nowe zoo", "stare zoo")):
        if int(ctx.get("day_zoo_count") or 0) >= 1:
            delta -= 200.0

    if tg == "friends" and adv:
        if any(k in name for k in (
            "okrąglak", "okraglak", "domy kupieckie", "ratusz w poznaniu",
        )):
            delta -= 120.0
        if day == 1 and "ratusz" in name:
            delta -= 80.0

    if tg == "family_kids" and "pixel xl" in name:
        _ca244 = user.get("children_age")
        try:
            if _ca244 is not None and int(_ca244) <= 5:
                delta -= 120.0
            else:
                delta += 70.0
        except (TypeError, ValueError):
            delta += 70.0

    _day_mus = int(ctx.get("day_museum_count") or 0)
    if _day_mus >= 2 and "muzeum" in name:
        if tg == "couples" and style == "cultural" and "relaxation" in prefs:
            delta -= 110.0
        elif tg == "seniors" and "relaxation" in prefs:
            delta -= 110.0
        elif style == "balanced" and "museum_heritage" not in top_prefs:
            delta -= 100.0
    if _day_mus >= 2 and tg == "seniors" and "relaxation" in prefs:
        if any(k in name for k in (
            "park ", "ogród", "ogrod", "wilson", "sołack", "solack", "cytadel",
        )):
            delta += 90.0

    # FIX #286 json 10: keep water + local food on day 2, not a dry castle day.
    if tg == "couples" and {"water_attractions", "local_food_experience"} <= prefs:
        if any(k in name for k in (
            "malta", "termy", "plaża", "plaza", "wartostrada", "jezioro",
        )):
            delta += 95.0
        if "zamek cesarski" in name:
            delta -= 140.0
        if any(k in name for k in ("rogalowe", "pyra", "kuchnia", "food", "targ")):
            delta += 70.0

    if num_days >= 7 and day >= 7:
        if any(k in name for k in (
            "malta", "dolina", "park ", "fort ", "botaniczny", "jezioro", "bulwar",
        )):
            delta += 90.0
        if "muzeum" in name and _day_mus >= 1:
            delta -= 70.0

    if tg == "solo" and nat_relax:
        if any(k in name for k in (
            "jezioro maltańskie", "jezioro maltanskie", "park sołacki", "park solacki",
            "wartostrada", "palmiarnia", "dolina trzech",
        )):
            delta += 85.0

    # ── FIX #249 Poznań client feedback json 3/4/5/6/7/8/9 ──
    if "park adama mickiewicza" in name:
        if tg == "family_kids" and "relaxation" in prefs:
            delta -= 120.0
        if tg == "seniors" and (style == "relax" or {"relaxation", "nature_landscape"} <= prefs):
            delta -= 115.0
        if tg == "friends" and "active_sport" in prefs:
            delta -= 120.0
        if tg == "solo" and {"nature_landscape", "museum_heritage", "history_mystery"} <= prefs:
            delta -= 100.0

    if "makieta dawnego poznania" in name:
        if tg == "friends" and adv and "active_sport" in prefs:
            delta -= 130.0

    if tg == "family_kids" and "kids_attractions" in prefs:
        if "palmiarnia" in name and "relaxation" in prefs:
            delta -= 90.0
        if any(k in name for k in ("nowe zoo", "stare zoo", "termy malta", "jezioro malta")):
            delta += 85.0

    if tg == "couples" and num_days >= 7 and day >= 2:
        _had_center = any(
            any(k in (tn or "") for k in ("stary rynek w poznaniu", "zamek królewski", "zamek krolewski"))
            for tn in trip_names
        )
        if _had_center and any(k in name for k in (
            "stary rynek w poznaniu", "zamek królewski", "zamek krolewski",
            "ratusz w poznaniu", "domy kupieckie", "okrąglak", "okraglak",
        )):
            delta -= 145.0
        if day >= 6 and any(k in name for k in ("domy kupieckie", "okrąglak", "okraglak", "ratusz w poznaniu")):
            delta -= 160.0

    if tg == "solo" and nat_relax and day >= 2:
        if any(k in name for k in (
            "stary rynek", "ostrów tumski", "ostrow tumski", "bazylika",
            "plac wolności", "plac wolnosci", "trakt królewsko", "trakt krolewsko",
            "ratusz w poznaniu", "zamek cesarski",
        )):
            delta -= 125.0
        if any(k in name for k in (
            "jezioro malta", "wartostrada", "park sołacki", "park solacki",
            "dolina trzech", "park cytadela", "rezerwat", "lasek",
        )):
            delta += 100.0

    if tg == "friends" and adv and {"underground", "history_mystery", "museum_heritage"} <= prefs:
        if _has_church_name(name) and int(ctx.get("day_church_count") or 0) >= 1:
            delta -= 135.0
        if any(k in name for k in (
            "flypark", "jump arena", "fort ", "termy malta", "centrum szyfrów",
            "centrum szyfrow", "enigma", "brama poznania", "szachty", "podziem",
        )):
            delta += 95.0

    if "active_sport" in prefs and adv:
        if any(k in name for k in (
            "flypark", "jump arena", "wartostrada", "park linowy", "trampolin",
            "paintball", "escape", "gokart", "fort va", "fort bonin",
            "letni tor", "saneczkowy",
        )):
            delta += 130.0
        if any(k in name for k in ("park adama mickiewicza", "makieta dawnego poznania")):
            delta -= 110.0

    # ── FIX #245 Katowice — powtórki fillerów, kids, water, sparse dni ──
    _rk245 = poi_trip_repeat_key(name)
    if _rk245:
        for _tn in trip_names:
            if poi_trip_repeat_key(_tn) == _rk245:
                delta -= 160.0
                break

    if tg == "family_kids" and "kids_attractions" in prefs:
        if any(k in name for k in (
            "papugarnia", "jumpcity", "pixel xl", "pixel", "zoo", "funhouse",
        )):
            delta += 90.0
        _trip_kids245 = int(ctx.get("trip_kids_attraction_count") or 0)
        if day >= 2 and _trip_kids245 >= 1:
            if any(k in name for k in (
                "pijalnia czekolady", "planetarium", "galeria szyb wilson", "szyb wilson",
            )):
                delta -= 95.0

    if tg == "couples" and "water_attractions" in prefs:
        if any(k in name for k in ("park wodny", "nemo", "wodny park", "tychy")):
            # FIX #255b: must win even on tight 200 PLN budgets (KAT test-10).
            delta += 220.0
        if "park kościuszki" in name or "park kosciuszki" in name:
            delta -= 100.0
        if "planetarium" in name:
            delta -= 95.0
        if any(k in name for k in (
            "muzeum śląskie", "muzeum slaskie", "rynek w katowicach", "rynek katowic",
            "pijalnia", "wedel", "kościół", "kosciol", "parafia",
        )):
            delta -= 100.0
        if int(ctx.get("trip_water_count") or 0) < 1 and not any(
            k in name for k in ("park wodny", "nemo", "wodny park", "tychy", "aquapark")
        ):
            delta -= 60.0

    if tg == "solo" and nat_relax and not ({"museum_heritage", "history_mystery"} & prefs):
        if "muzeum" in name or "planetarium" in name:
            delta -= 100.0

    if num_days >= 7 and day >= 7:
        if any(k in name for k in (
            "park wodny", "nemo", "dolina trzech", "palmiarnia", "nikiszowiec",
            "tężnia", "teznia", "park śląski", "park slaski",
        )):
            delta += 95.0

    # ── FIX #246 Kraków client feedback (json 2/4/5/8/10) ──
    if "lustrzany labirynt" in name:
        delta -= 140.0
        if tg == "couples" and "kids_attractions" not in prefs:
            delta -= 100.0

    if tg == "family_kids" and "kids_attractions" in prefs:
        if any(k in name for k in (
            "papugarnia", "kolejkowo", "pixel", "guliwer", "w budowie", "lego",
            "smoczy", "iluzj", "motyl", "fabryka cukier", "park wodny", "trampolin",
            "gojump", "smart kids", "miniciti",
        )):
            delta += 115.0
        _trip_kids246 = int(ctx.get("trip_kids_attraction_count") or 0)
        if _trip_kids246 < 2:
            if any(k in name for k in ("muzeum lotnictwa", "zamek królewski", "zamek krolewski")):
                delta -= 90.0

    if tg == "solo" and "nature_landscape" in prefs:
        if any(k in name for k in (
            "ogród botaniczny", "ogrod botaniczny", "bulwary", "kopiec krakusa",
            "kopiec kościuszki", "kopiec kosciuszki", "park decjusza", "rezerwat",
            "zespół przyrodniczo", "zespol przyrodniczo", "błonia", "blonia",
        )):
            delta += 105.0
        if "nature_landscape" in top_prefs and "muzeum" in name:
            if int(ctx.get("day_museum_count") or 0) >= 2:
                delta -= 95.0

    if "alvernia planet" in name:
        delta -= 120.0

    if tg == "couples" and {"water_attractions", "relaxation", "local_food_experience"} <= prefs:
        from app.domain.scoring.preference_coverage import poi_covers_preference_report
        if poi_covers_preference_report(poi, "relaxation") or poi_covers_preference_report(poi, "water_attractions"):
            delta += 115.0
        if any(k in name for k in (
            "rynek główny", "rynek glowny", "sukiennice", "plac bohaterów getta",
            "plac bohaterow getta", "barbakan", "pomnik smoka",
        )):
            delta -= 100.0
        if "muzeum" in name and int(ctx.get("day_museum_count") or 0) >= 1:
            delta -= 75.0

    # ── FIX #247 Warszawa — client feedback json 2/3/4/7/8/9/10 ──
    _waw247_filler = (
        "most świętokrzyski", "most swietokrzyski", "pałac prezydencki", "palac prezydencki",
        "plac europejski", "centrum pieniądza", "centrum pieniadza",
    )
    if any(k in name for k in _waw247_filler):
        delta -= 130.0

    if any(k in name for k in ("ogrody zamku", "ogrod zamku")):
        delta -= 110.0
        if name in trip_names:
            delta -= 90.0

    if tg == "friends" and adv and "active_sport" in prefs:
        if any(k in name for k in (
            "tepfactor", "park linowy", "kajak", "kajaki", "trampolin", "gojump",
            "paintball", "escape", "gokart", "wspinacz",
        )):
            delta += 125.0
        if any(k in name for k in ("centrum nauki kopernik", "pijalnia czekolady", "polin")):
            if int(ctx.get("trip_active_sport_count") or 0) < 1:
                delta -= 85.0

    # FIX #260: Park Linowy / Kampinos wrong for soft cultural-relax-food days.
    _soft_waw = {"cultural", "museum_heritage", "relaxation", "local_food_experience"}
    _active_waw = {"adventure", "active_sport", "nature_landscape"}
    if "park linowy" in name or ("linowy" in name and "park" in name):
        if (prefs & _soft_waw) and not (prefs & _active_waw) and style != "adventure":
            delta -= 220.0
        elif (prefs & {"cultural", "museum_heritage", "relaxation"}) and not (
            prefs & _active_waw
        ) and style != "adventure":
            # cultural+museum+relaxation without local_food still a soft day.
            delta -= 180.0
    if "kampinos" in name:
        _hist_waw = {"underground", "history_mystery", "museum_heritage"}
        if (prefs & _hist_waw) and "nature_landscape" not in prefs and "active_sport" not in prefs:
            delta -= 200.0
        # Long hop tax unless nature/active is explicitly requested.
        if "nature_landscape" not in prefs and "active_sport" not in prefs and style != "adventure":
            delta -= 80.0
    # FIX #260: local_food_experience — boost edible landmarks, demote illusion parks.
    if "local_food_experience" in prefs:
        if any(k in name for k in (
            "wedel", "manufaktura cukierków", "manufaktura cukierkow",
            "browary warszawskie", "pijalnia czekolady", "muzeum polskiej wódki",
            "muzeum polskiej wodki",
        )):
            delta += 140.0
        if any(k in name for k in ("świat iluzji", "swiat iluzji", "iluzji")):
            if not (prefs & {"kids_attractions", "adventure", "active_sport"}):
                delta -= 160.0
    # Soft cultural days: Świat Iluzji is a weak fit.
    if any(k in name for k in ("świat iluzji", "swiat iluzji")):
        if (prefs & {"museum_heritage", "cultural", "history_mystery"}) and not (
            prefs & {"kids_attractions", "adventure"}
        ):
            delta -= 120.0
        # FIX #268: seniors + nature/museum/relax — never treat as filler.
        if tg == "seniors" or (
            prefs & {"nature_landscape", "relaxation", "museum_heritage"}
            and not (prefs & {"kids_attractions", "active_sport"})
        ):
            delta -= 180.0
    # FIX #268: expensive fillers that cover no selected prefs (Kosmopark / Zajezdnia).
    if "kosmopark" in name and not (prefs & {"kids_attractions", "active_sport", "adventure"}):
        delta -= 220.0
    if "zajezdnia" in name and not (
        prefs & {"history_mystery", "museum_heritage", "underground"}
    ):
        delta -= 140.0
    # Nature+relax days: demote PKiN / Stare Miasto icons.
    if {"nature_landscape", "relaxation"} <= prefs and "museum_heritage" not in prefs:
        if any(k in name for k in (
            "pałac kultury", "palac kultury", "pkin", "stare miasto",
        )):
            delta -= 130.0

    # FIX #267: preferences define WHAT — boost real underground POIs for any
    # group when underground is selected (X Pawilon / Gazownia exist in WAWA).
    if "underground" in prefs:
        if any(k in name for k in (
            "cytadel", "x pawilon", "muzeum gazowni", "gazowni",
            "podziemia", "schron", "bunkier",
        )):
            delta += 200.0
        if any(k in name for k in (
            "stacja grawitacja", "górka szczęśliwick", "gorka szczesliwick",
            "jeziorko", "kampinos", "park linowy",
        )):
            delta -= 160.0
    if "history_mystery" in prefs and "nature_landscape" not in prefs:
        if any(k in name for k in (
            "muzeum powstania", "muzeum wojska", "cytadel", "zamek królewski",
            "zamek krolewski", "gazowni", "x pawilon",
        )):
            delta += 90.0
        if any(k in name for k in (
            "jeziorko", "górka szczęśliwick", "gorka szczesliwick",
            "stacja grawitacja", "kampinos",
        )):
            delta -= 120.0

    if tg == "friends" and adv and {"underground", "history_mystery"} <= prefs:
        if any(k in name for k in (
            "podziemia", "schron", "krypta", "bunkier", "fort ", "katakumby",
            "muzeum powstania", "kopiec powstania", "cytadela", "zamek królewski",
            "zamek krolewski", "norblin", "muzeum gazowni", "x pawilon",
        )):
            delta += 160.0
        # FIX #260/#267: Gazownia is real underground — keep boost; demote
        # adventure fillers that cover none of the selected prefs.
        if any(k in name for k in ("tepfactor", "kajak", "escape")):
            delta += 80.0
        if "grawitacja" in name:
            delta -= 100.0
        if "park linowy" in name:
            delta -= 160.0
        if any(k in name for k in (
            "pałac kultury", "palac kultury", "pkin", "polin",
            "centrum nauki kopernik", "park wodny", "warszawianka",
        )):
            delta -= 140.0
        if any(k in name for k in ("pałac kultury", "palac kultury", "pkin")):
            if int(ctx.get("day_museum_count") or 0) >= 1:
                delta -= 95.0
            delta -= 60.0
        if "kampinos" in name:
            delta -= 180.0

    # FIX #264: rope parks clash with relax / cultural / seniors profiles.
    _style264 = _safe_str(user.get("travel_style"))
    if "park linowy" in name and (
        _style264 in ("relax", "cultural")
        or "relaxation" in prefs
        or tg in ("seniors", "solo")
    ):
        delta -= 220.0

    if tg == "solo" and "nature_landscape" in prefs:
        if any(k in name for k in (
            "łazienki królewskie", "lazienki krolewskie", "ogród botaniczny", "ogrod botaniczny",
            "bulwary wiślane", "bulwary wislane", "wilanów", "wilanow", "kopiec",
            "ogrody zamku", "ogrod zamku", "palmiarnia",
        )):
            delta += 100.0
        if any(k in name for k in _waw247_filler):
            delta -= 80.0
        if "muzeum" in name and int(ctx.get("day_museum_count") or 0) >= 2:
            delta -= 90.0

    if tg == "couples" and {"water_attractions", "relaxation"} <= prefs:
        if any(k in name for k in (
            "park wodny", "warszawianka", "bulwary wiślane", "bulwary wislane",
            "łazienki królewskie", "lazienki krolewskie",
        )):
            delta += 120.0
        if any(k in name for k in ("pałac prezydencki", "palac prezydencki", "grób nieznanego", "grob nieznanego")):
            delta -= 100.0

    if num_days >= 7 and day >= 6:
        if any(k in name for k in (
            "łazienki królewskie", "lazienki krolewskie", "wilanów", "wilanow",
            "ogród botaniczny", "ogrod botaniczny", "bulwary", "muzeum pałacu",
            "muzeum palacu", "park wodny",
        )):
            delta += 85.0
        if any(k in name for k in (
            "centrum pieniądza", "centrum pieniadza", "muzeum geologiczne",
            "muzeum gazowni", "cmentarz powązkowski", "cmentarz powazkowski",
        )):
            delta -= 75.0

    # ── FIX #248 Wrocław — client feedback json 1–10 ──
    if any(k in name for k in ("dworzec świebodzki", "dworzec swiebodzki")):
        delta -= 80.0
        if tg in ("seniors", "solo") and (style == "relax" or "relaxation" in prefs):
            delta -= 90.0

    # FIX #259: Hala Stulecia is a weak cover for water + food + relaxation.
    if "hala stulecia" in name and {
        "water_attractions", "local_food_experience", "relaxation",
    } <= prefs:
        delta -= 120.0
    # Prefer real green when relaxation / nature are requested but day is dry.
    # FIX #261: stronger boost — winter WRO plans kept scheduling museums while
    # Pergola/Wyspa/Zatoka sat unused and prefs reported uncovered.
    if ("relaxation" in prefs or "nature_landscape" in prefs) and any(
        k in name for k in (
            "park szczytnicki", "pergola", "wyspa słodowa", "wyspa slodowa",
            "bulwar", "ogród japoński", "ogrod japonski", "lasek", "las strzeli",
            "zatoka gondoli", "ogród botaniczny", "ogrod botaniczny",
        )
    ):
        delta += 140.0
        if "muzeum" not in name and "zajezdnia" not in name:
            delta += 40.0
    if ("relaxation" in prefs or "nature_landscape" in prefs) and any(
        k in name for k in ("zajezdnia", "aula leopoldina", "panorama racławicka",
                            "panorama raclawicka")
    ):
        delta -= 70.0

    if tg == "friends" and adv and {"history_mystery", "museum_heritage", "underground"} <= prefs:
        if "active_sport" not in prefs:
            if any(k in name for k in (
                "fort przygody", "paintball", "quad", "kosmopark", "laser tag",
                "gojump", "citypaintball",
            )):
                delta -= 130.0
            if any(k in name for k in (
                "panorama racławicka", "muzeum narodowe", "centrum historii zajezdnia",
                "zajezdnia", "hydropolis", "katedra",
            )):
                delta += 95.0

    if tg == "friends" and adv and {"active_sport", "history_mystery"} <= prefs:
        if any(k in name for k in ("rynek we wrocławiu", "rynek we wroclawiu", "hala stulecia")):
            delta -= 130.0
        if any(k in name for k in ("gojump", "citypaintball", "paintball", "park linowy")):
            delta += 100.0

    if tg == "couples" and style == "cultural" and "relaxation" in prefs:
        if any(k in name for k in (
            "wyspa słodowa", "wyspa slodowa", "pergola", "park szczytnicki",
            "ogród japoński", "ogrod japonski", "bulwar", "odra",
        )):
            delta += 110.0
        if "pigcasso" in name:
            delta -= 120.0

    if tg == "seniors" and {"museum_heritage", "nature_landscape", "relaxation"} <= prefs:
        if any(k in name for k in (
            "park szczytnicki", "pergola", "wyspa słodowa", "wyspa slodowa",
            "ogród japoński", "ogrod japonski", "lasek", "las strzeli",
        )):
            delta += 105.0
        if "muzeum" in name and int(ctx.get("day_museum_count") or 0) >= 2:
            delta -= 95.0

    # FIX #283: 5-day Wrocław + nature should pick Niemcza/Arboretum
    # as the one allowed trip, not a random Brzeg hop.
    try:
        _days_ctx = int(ctx.get("num_days") or ctx.get("trip_days") or 0)
    except (TypeError, ValueError):
        _days_ctx = 0
    if "nature_landscape" in prefs and _days_ctx >= 5:
        if any(k in name for k in (
            "niemcz", "wojsław", "wojslaw", "dolina tatarska",
            "arboretum wojsław", "arboretum wojslaw",
        )):
            delta += 95.0

    if tg == "solo" and nat_relax:
        if any(k in name for k in (
            "park szczytnicki", "pergola", "wyspa słodowa", "wyspa slodowa",
            "ogród japoński", "ogrod japonski", "lasek", "las strzeli",
            "ogród botaniczny", "ogrod botaniczny", "arboretum",
        )):
            delta += 100.0
        if "muzeum" in name and not ({"museum_heritage", "history_mystery"} & prefs):
            if "hydropolis" not in name:
                delta -= 100.0
        if day >= 3 and "muzeum" in name:
            delta -= 90.0

    if tg == "couples" and {"water_attractions", "relaxation"} <= prefs:
        if any(k in name for k in ("katedra wrocławska", "katedra wroclawska")):
            delta -= 130.0

    if tg == "family_kids" and "hala targowa" in name:
        delta -= 110.0

    if num_days >= 7 and day >= 6:
        if any(k in name for k in (
            "park szczytnicki", "pergola", "wyspa słodowa", "wyspa slodowa",
            "ogród japoński", "ogrod japonski", "ogród botaniczny", "ogrod botaniczny",
            "lasek", "las strzeli",
        )):
            delta += 90.0
        if any(k in name for k in ("aquapark", "city golf", "movie gate", "pigcasso")):
            delta -= 85.0

    # FIX #287 Warszawa — water / active / food-hall opener / history spread.
    if "water_attractions" in prefs:
        if any(k in name for k in (
            "warszawianka", "park fontann", "fontanna multimedialna",
            "jeziorko czerniakowskie", "kajak",
            "bulwary wiślane", "bulwary wislane",
        )):
            delta += 180.0
        if "koszyki" in name:
            delta -= 200.0
    if "koszyki" in name and int(ctx.get("day_attraction_count") or 0) == 0:
        delta -= 160.0
    if "active_sport" in prefs:
        if any(k in name for k in (
            "tepfactor", "stacja grawitacja", "grawitacja", "flyspot",
            "jumpcity", "jump arena", "gojump",
        )):
            delta += 170.0
    if "history_mystery" in prefs and day >= 2:
        if any(k in name for k in (
            "muzeum powstania", "muzeum wojska", "cytadel",
            "zamek królewski", "zamek krolewski", "gazowni", "x pawilon",
        )):
            delta += 90.0

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
        "pixel xl", "escape", "paintball", "linowa", "kajak", "gokart", "tepfactor",
        "grawitacja", "flyspot", "jumpcity",
    )
    return any(n in name for n in _active_names)
