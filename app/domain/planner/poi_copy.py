"""FIX #253: category-aware Polish copy for POIs (description_short / pro_tip).

The client reported three problems that all trace back to the old fallback copy:
  * only three description variants ever appeared,
  * descriptions contradicted the attraction ("Jump Arena — zielona przestrzeń"),
  * pro tips repeated ("sprawdź godziny otwarcia", "weź wodę", "parking").

Excel already ships `Description_short` and `Pro_tip` for virtually every POI, so
this module is only a safety net. It classifies a POI into a semantic category
using token matching (never raw substrings — `trampoline_park` must not match
`park`) and derives copy from that category.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

_TOKEN_SPLIT = re.compile(r"[^0-9a-ząćęłńóśźż]+")


def _tokens(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw = " ".join(str(v) for v in value)
    else:
        raw = str(value)
    return [t for t in _TOKEN_SPLIT.split(raw.lower()) if t]


def poi_token_set(poi: Dict[str, Any]) -> set:
    """All lowercase tokens from tags + category + name (word-boundary safe)."""
    return _primary_tokens(poi) | _mapped_tokens(poi)


def _primary_tokens(poi: Dict[str, Any]) -> set:
    """Descriptive tokens: raw Excel tags, attraction type, subcategory, name.

    `tags` is deliberately excluded here: it holds coarse preference labels
    produced by `apply_tag_mapping` (e.g. `architecture_landmark` becomes
    `museum_heritage`), which used to classify the Rynek as a museum.
    """
    out: set = set()
    out.update(_tokens(poi.get("tags_excel")))
    out.update(_tokens(poi.get("type_of_attraction") or poi.get("Type of attraction")))
    out.update(_tokens(poi.get("subcategory")))
    out.update(_tokens(poi.get("name") or poi.get("Name")))
    return out


def _mapped_tokens(poi: Dict[str, Any]) -> set:
    out: set = set()
    out.update(_tokens(poi.get("tags")))
    out.update(_tokens(poi.get("category")))
    return out


# Ordered most-specific first: the first category whose tokens match wins.
_CATEGORY_RULES: List[Tuple[str, Tuple[str, ...]]] = [
    # "water" alone is far too broad — it also tags the Japanese garden's ponds.
    ("aquapark", ("aquapark", "waterpark", "basen", "baseny", "pływalnia", "plywalnia",
                  "zjeżdżalnie", "zjezdzalnie", "termy", "thermal", "slides")),
    ("spa", ("spa", "wellness", "sauna", "masaż", "masaz")),
    ("trampoline", ("trampoline", "trampolin", "jump", "jumping")),
    ("climbing", ("rope", "linowy", "climbing", "wspinaczka", "wspinaczkowa", "boulder")),
    ("motorsport", ("gokart", "gokarty", "karting", "kartingowy", "racing", "tor", "quad",
                    "quady", "motor")),
    ("shooting", ("paintball", "laser", "lasertag", "asg", "strzelnica", "shooting")),
    ("escape_room", ("escape", "quest", "pokój", "pokoj", "zagadk")),
    ("maze", ("maze", "labirynt")),
    ("amusement", ("rollercoaster", "lunapark", "amusement", "rozrywki", "theme",
                   "thematic", "dinosaur", "prehistoric")),
    ("playground", ("playground", "indoor", "softplay", "soft", "plac", "zabaw",
                    "kids", "children", "dzieci")),
    ("zoo", ("zoo", "aquarium", "akwarium", "oceanarium", "safari", "terrarium")),
    ("science", ("science", "nauka", "interactive", "interaktywne", "planetarium",
                 "experiment", "eksperyment", "hydropolis", "technika", "technology")),
    ("museum", ("museum", "muzeum", "gallery", "galeria", "exhibition", "wystawa",
                "sztuka", "panorama")),
    # Market squares and promenades are places to stroll, not monuments — this
    # must win before the broad heritage rule (client: "Rynek opisany jako muzeum").
    ("old_town", ("rynek", "starówka", "starowka", "oldtown", "deptak", "promenada")),
    ("heritage", ("heritage", "historic", "historical", "history", "zabytek", "zabytki",
                  "castle", "zamek", "palace", "pałac", "palac", "cathedral", "katedra",
                  "church", "kościół", "kosciol", "fort", "twierdza", "monument")),
    ("old_town", ("square", "old", "town", "market", "plac", "ulica", "street")),
    ("viewpoint", ("viewpoint", "widokowy", "widokowa", "panoramic", "observation",
                   "wieża", "wieza", "tower", "taras")),
    ("garden", ("botanical", "botaniczny", "garden", "ogród", "ogrod", "arboretum",
                "greenhouse", "palmiarnia", "japoński", "japonski")),
    ("park", ("park", "skwer", "zieleń", "zielen", "greenery", "promenade",
              "lawn", "łąka", "laka")),
    ("water_nature", ("lake", "jezioro", "river", "rzeka", "wyspa", "island", "beach",
                      "plaża", "plaza", "waterfront", "bulwar", "nabrzeże", "nabrzeze")),
    ("hiking", ("hiking", "trail", "szlak", "trekking", "mountain", "góra", "gora",
                "summit", "szczyt")),
    ("cruise", ("cruise", "rejs", "statek", "statkiem", "gondola", "gondol", "kajak",
                "boat", "łódź", "lodz")),
    ("winter_sport", ("ski", "narty", "narciarski", "snowboard", "kulig", "sleigh",
                      "sanki", "saneczkowy", "lodowisko", "skating")),
    ("sport", ("sport", "active", "aktywny", "stadion", "stadium", "arena", "bowling",
               "kręgle", "kregle", "rower", "bike", "cycling", "golf")),
    ("nightlife", ("nightlife", "club", "klub", "pub", "bar", "brewery", "browar")),
    ("shopping", ("shopping", "zakupy", "mall", "galeria", "targ", "bazar", "market")),
    ("entertainment", ("theatre", "teatr", "cinema", "kino", "opera", "filharmonia",
                       "concert", "koncert", "show", "spektakl")),
]


def poi_name_tokens(poi: Dict[str, Any]) -> set:
    """Lowercase tokens of the POI name only."""
    return set(_tokens(poi.get("name") or poi.get("Name")))


def classify_poi_category(poi: Dict[str, Any]) -> str:
    """Semantic category used for copy + explainability. Never raises."""
    name = str(poi.get("name") or poi.get("Name") or "").lower()
    # FIX #273: Nikiszowiec is a historic workers' settlement, not a museum hall.
    if "nikiszowiec" in name:
        return "heritage"
    # FIX #254: name overrides before token rules (wrong Excel tags / false positives).
    if "obwarzank" in name:
        return "museum"
    # FIX #264: Muzeum Ewolucji/Geologiczne are museums, not amusement/science tips.
    if "muzeum ewolucji" in name or "muzeum geologiczne" in name:
        return "museum"
    if any(k in name for k in ("skałki twardowskiego", "skalki twardowskiego")):
        return "park"
    if "park jordana" in name:
        return "park"
    # FIX #265: Park Mamuta is outdoor kids dinosaurs — never museum.
    if "mamuta" in name:
        return "playground"
    if any(k in name for k in ("jeziorko czerniakowskie", "jezioro czerniak")):
        return "water_nature"
    if "kampinos" in name:
        return "hiking"
    if "wyspa" in name and ("słodow" in name or "slodow" in name):
        return "water_nature"
    if "pergola" in name:
        return "park"
    if any(k in name for k in ("sky tower", "punkt widokowy")):
        return "viewpoint"
    # FIX #295: Most Świętokrzyski is a lookout walk, not a heritage monument.
    if any(k in name for k in ("most świętokrzyski", "most swietokrzyski")):
        return "viewpoint"
    if any(k in name for k in ("park linowy", "rope park")) or (
        "linowy" in name and "park" in name
    ):
        return "climbing"
    # FIX #255: Lustrzany Labirynt is indoor — not "na świeżym powietrzu".
    if "lustrzan" in name or ("mirror" in name and "labirynt" in name):
        return "mirror_maze"
    if "park lotników" in name or "park lotnikow" in name:
        return "park"

    _PLAYGROUND_SAFE = frozenset({
        "playground", "indoor", "softplay", "soft", "zabaw",
    })
    _CLIMB_NAME = ("linowy", "rope", "wspin", "boulder", "climbing", "park linowy")

    primary = _primary_tokens(poi)
    for label, keys in _CATEGORY_RULES:
        if label == "climbing":
            if not any(k in name for k in _CLIMB_NAME):
                continue
        if label == "playground":
            # "plac" alone matches Plac Bohaterów Getta / Plac Europejski.
            if primary.intersection(_PLAYGROUND_SAFE):
                return label
            if any(k in name for k in ("plac zabaw", "softplay", "playground", "zabaw dla")):
                return label
            continue
        if label == "maze" and ("lustrzan" in name or "mirror" in name):
            return "mirror_maze"
        if primary.intersection(keys):
            return label
    mapped = _mapped_tokens(poi)
    for label, keys in _CATEGORY_RULES:
        if label == "climbing" and not any(k in name for k in _CLIMB_NAME):
            continue
        if label == "playground":
            if not mapped.intersection(_PLAYGROUND_SAFE) and "zabaw" not in name:
                continue
        if label == "maze" and ("lustrzan" in name or "mirror" in name):
            return "mirror_maze"
        if mapped.intersection(keys):
            return label
    return "attraction"


_DESC_BY_CATEGORY: Dict[str, str] = {
    "aquapark": "{name} — kompleks basenów i atrakcji wodnych{loc}.",
    "spa": "{name} — strefa spa i wellness na regenerację{loc}.",
    "trampoline": "{name} — park trampolin z torami i strefami do skakania{loc}.",
    "climbing": "{name} — park linowy z trasami o różnym stopniu trudności{loc}.",
    "motorsport": "{name} — tor wyścigowy z gokartami i sportową dawką adrenaliny{loc}.",
    "shooting": "{name} — arena gier zespołowych z adrenaliną{loc}.",
    "escape_room": "{name} — escape room z zagadkami do rozwiązania w grupie{loc}.",
    "maze": "{name} — labirynt na świeżym powietrzu, świetna zabawa na orientację{loc}.",
    "mirror_maze": "{name} — lustrzany labirynt w budynku, zabawa na orientację{loc}.",
    "amusement": "{name} — park tematyczny pełen atrakcji i rozrywki{loc}.",
    "playground": "{name} — kryta strefa zabaw dla dzieci{loc}.",
    "zoo": "{name} — świat zwierząt z bliska, atrakcja dla całej rodziny{loc}.",
    "science": "{name} — interaktywne centrum nauki z eksponatami do samodzielnego testowania{loc}.",
    "museum": "{name} — muzeum z ekspozycją wartą dłuższej wizyty{loc}.",
    "heritage": "{name} — zabytek z bogatą historią{loc}.",
    "old_town": "{name} — tętniące życiem serce starego miasta{loc}.",
    "viewpoint": "{name} — punkt widokowy z panoramą okolicy{loc}.",
    "garden": "{name} — ogród z kolekcjami roślin i alejkami na spokojny spacer{loc}.",
    "park": "{name} — zielona przestrzeń na spacer i odpoczynek{loc}.",
    "water_nature": "{name} — nadwodny zakątek z widokami{loc}.",
    "hiking": "{name} — trasa spacerowa wśród przyrody{loc}.",
    "cruise": "{name} — rejs z widokiem na miasto od strony wody{loc}.",
    "winter_sport": "{name} — zimowa atrakcja sportowa{loc}.",
    "sport": "{name} — miejsce na aktywne spędzenie czasu{loc}.",
    "nightlife": "{name} — klimatyczne miejsce na wieczór{loc}.",
    "shopping": "{name} — miejsce na zakupy i przerwę przy kawie{loc}.",
    "entertainment": "{name} — scena kulturalna z bogatym repertuarem{loc}.",
    "attraction": "{name} — atrakcja warta odwiedzenia{loc}.",
}


_TIP_BY_CATEGORY: Dict[str, str] = {
    "aquapark": "Zabierz klapki i ręcznik — wejściówki czasowe warto kupić online.",
    "spa": "Zarezerwuj zabieg z wyprzedzeniem i przyjdź 15 min wcześniej na przebranie.",
    "trampoline": "Wymagane są skarpetki antypoślizgowe — kupisz je na miejscu lub weź własne.",
    "climbing": "Załóż sportowe buty i związ długie włosy — uprząż zakłada obsługa.",
    "motorsport": "Zarezerwuj sesję online; przyjedź kwadrans wcześniej na instruktaż.",
    "shooting": "Rezerwacja jest obowiązkowa; ubierz się na warstwy i nie żałuj wygodnych butów.",
    "escape_room": "Zarezerwuj slot z wyprzedzeniem — pokoje schodzą na kilka dni naprzód.",
    "maze": "Weź wodę i nakrycie głowy — trasa prowadzi głównie w pełnym słońcu.",
    "mirror_maze": "Kup bilet online; w środku bywa chłodniej — warto mieć lekką bluzę.",
    "amusement": "Kup bilet online i zacznij od najpopularniejszych atrakcji, zanim zrobi się tłoczno.",
    "playground": "Skarpetki antypoślizgowe są obowiązkowe, a strefa zwykle pustoszeje przed południem.",
    "zoo": "Zacznij od najdalszych wybiegów i sprawdź godziny karmienia zwierząt.",
    "science": "Zaplanuj więcej czasu na stanowiska interaktywne i kup bilet z wyprzedzeniem.",
    "museum": "Sprawdź, czy tego dnia obowiązuje wstęp bezpłatny — bywa najtłoczniej.",
    "heritage": "Warto dołączyć do oprowadzania z przewodnikiem — historia robi tu różnicę.",
    "old_town": "Najlepszy klimat jest wcześnie rano i po zmroku, gdy zapalają się latarnie.",
    "viewpoint": "Wybierz bezchmurny dzień i celuj w złotą godzinę tuż przed zachodem słońca.",
    "garden": "Najpiękniej jest w sezonie kwitnienia — sprawdź, które kolekcje są akurat otwarte.",
    "park": "Weź coś do picia i zaplanuj spokojny spacer bez pośpiechu.",
    "water_nature": "Zabierz wiatrówkę — nad wodą bywa chłodniej niż w centrum.",
    "hiking": "Sprawdź prognozę i zabierz wodę oraz buty z dobrą podeszwą.",
    "cruise": "Kup bilet wcześniej i zajmij miejsce na górnym pokładzie.",
    "winter_sport": "Ubierz się warstwowo i sprawdź warunki przed wyjazdem.",
    "sport": "Weź strój sportowy i zarezerwuj termin, zwłaszcza w weekend.",
    "nightlife": "Wieczorem bywa tłoczno — warto zarezerwować stolik.",
    "shopping": "Zaplanuj przerwę na kawę i sprawdź godziny otwarcia w niedziele.",
    "entertainment": "Bilety warto kupić wcześniej — popularne terminy znikają szybko.",
    "attraction": "Zaplanuj dojazd z buforem 10–15 min na parking i dojście.",
}


def build_fallback_copy(poi: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """Return (description_short, pro_tip), preferring the values from Excel."""
    name = str(poi.get("name") or poi.get("Name") or "Atrakcja").strip()
    city = str(poi.get("city") or "").strip()
    try:
        from app.domain.planner.city_copy import city_locative_pl
        loc = f" {city_locative_pl(city)}" if city else ""
    except Exception:
        loc = f" w {city}" if city else ""

    desc = str(
        poi.get("description_short") or poi.get("Description_short") or ""
    ).strip()
    tip = str(poi.get("pro_tip") or poi.get("Pro_tip") or "").strip() or None
    name_l = name.lower()

    # FIX #254: hard overrides for known bad Excel / generic copy.
    # FIX #259/#263: free attractions must not tip "kup bilet online".
    _ticket_free = False
    try:
        tn = poi.get("ticket_normal")
        if tn is not None and float(tn) == 0:
            _ticket_free = True
    except Exception:
        pass
    if "park mamuta" in name_l or "mamuta" in name_l:
        _ticket_free = True
        desc = (
            "Park Mamuta — plenerowa ekspozycja rzeźb dinozaurów dla rodzin "
            "z dziećmi, wstęp wolny."
        )
        tip = "Wstęp wolny — idealny na krótki spacer z dziećmi między większymi atrakcjami."
        return desc, tip
    if _ticket_free and tip and any(
        k in tip.lower() for k in ("bilet", "ticket", "kup online", "kup bilet")
    ):
        tip = "Wejście darmowe — warto sprawdzić aktualne godziny przed wizytą."
    # FIX #264: Muzeum Geologiczne / free museums must not tip ticket purchase.
    if any(k in name_l for k in ("muzeum geologiczne", "muzeum ewolucji")):
        try:
            if float(poi.get("ticket_normal") or 0) == 0:
                _ticket_free = True
        except Exception:
            pass
        if _ticket_free and tip and any(
            k in tip.lower() for k in ("bilet", "ticket", "kup ")
        ):
            tip = "Wstęp wolny — sprawdź aktualne godziny otwarcia przed wizytą."
        if "muzeum ewolucji" in name_l and (
            not desc or "park tematycznego" in desc.lower()
        ):
            desc = (
                "Muzeum Ewolucji — paleontologia i historia życia na Ziemi "
                "w zbiorach PAN w Warszawie."
            )
    # FIX #260: Browary Warszawskie — never tip/compare to Hala Koszyki.
    if "browary warszawskie" in name_l:
        desc = (
            "Browary Warszawskie — kompleks z restauracjami, piwem rzemieślniczym "
            "i przestrzenią eventową na Woli."
        )
        tip = (
            "Zaplanuj czas na obiad lub degustację piwa na miejscu — "
            "wieczorem bywa tłoczno."
        )
        return desc, tip
    # FIX #258: Wedel — classic café is on Szpitalna; POI row is aleja Wedla 5.
    if any(k in name_l for k in ("wedel", "pijalnia czekolady")):
        addr = str(poi.get("address") or poi.get("Address") or "").strip()
        if "wedla" in addr.lower() or "warsz" in (city or "").lower() or not addr:
            desc = (
                "Pijalnia Czekolady E. Wedel — muzeum i degustacja czekolady "
                "przy alei Wedla 5 w Warszawie (Praga)."
            )
            tip = tip or "Sprawdź godziny i bilety online — to lokal przy alei Wedla 5, nie przy ul. Szpitalnej."
            return desc, tip
    if "obwarzank" in name_l:
        desc = "Muzeum Obwarzanka Krakowskiego — historia i wypiek symbolu Krakowa."
        tip = "Spróbuj świeżego obwarzanka na miejscu — to lokalny smak Krakowa."
        return desc, tip
    if "bajgl" in (desc or "").lower() and "obwarzank" in name_l:
        desc = "Muzeum Obwarzanka Krakowskiego — historia i wypiek symbolu Krakowa."
    # FIX #256/#261: GoJump Excel row reused Kraków copy for Wrocław.
    _gojump_foreign = ("w krakowie", "w kraków", "w krakow", "krakowie", "krakowa")
    if "gojump" in name_l and any(
        k in (desc or "").lower() or k in (tip or "").lower() for k in _gojump_foreign
    ):
        city_bit = city or "mieście"
        loc_bit = loc.strip() or ("w " + city_bit)
        if any(k in (desc or "").lower() for k in _gojump_foreign):
            desc = (
                f"GoJump to duży park trampolin {loc_bit} "
                f"— strefy dla różnych poziomów zaawansowania."
            )
        if tip and any(k in tip.lower() for k in _gojump_foreign):
            tip = f"Sprawdź aktualne godziny i bilety GoJump {loc_bit}."
    if "wena" in name_l and tip and any(
        k in tip.lower() for k in ("umówieniu", "umowieniu", "wcześniejszym", "wczesniejszym")
    ):
        tip = "Sprawdź aktualne godziny na stronie muzeum przed wizytą."
    if tip and "koronach drzew" in tip.lower() and "linowy" not in name_l:
        tip = None
    if tip and any(k in tip.lower() for k in (
        "promocji rodzinnych", "dla rodzin", "z dziećmi", "dla dzieci",
        "dzieci i młodzież", "dzieci i mlodziez", "warsztat", "warsztaty dla",
    )):
        # Couples / adult plans must not get kids/family promo tips.
        tip = None
    if tip and any(k in tip.lower() for k in ("pokaz", "fontann")) and "pergola" in name_l:
        # Winter callers strip season elsewhere; keep tip neutral year-round.
        tip = "Spacer wokół Hali Stulecia — Pergola jest ładna o każdej porze dnia."

    if desc and tip:
        return desc, tip

    category = classify_poi_category(poi)
    if not desc:
        desc = _DESC_BY_CATEGORY.get(category, _DESC_BY_CATEGORY["attraction"]).format(
            name=name, loc=loc
        )
    if not tip:
        tip = _TIP_BY_CATEGORY.get(category, _TIP_BY_CATEGORY["attraction"])
        if category == "aquapark":
            tip = "Zabierz klapki i ręcznik — wejściówki czasowe warto kupić online."
    return desc, tip


def category_is_green(category: str) -> bool:
    return category in ("garden", "park", "water_nature", "hiking")


def category_is_indoor_kids(category: str) -> bool:
    return category in ("playground", "trampoline")


__all__ = [
    "build_fallback_copy",
    "classify_poi_category",
    "poi_token_set",
    "poi_name_tokens",
    "category_is_green",
    "category_is_indoor_kids",
]
