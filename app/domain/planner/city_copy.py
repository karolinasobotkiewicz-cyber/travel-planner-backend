"""
FIX #188 — city-aware copy and POI city guards (non-Zakopane cities).

Single source for:
- diacritic-insensitive city matching
- Zakopane-only vs neutral free_time / dinner / evening suggestions
"""
from __future__ import annotations

import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Set

ZAKOPANE_REGION_RAW = (
    "zakopane", "szaflary", "chochołów", "białka tatrzańska",
    "bukowina tatrzańska", "kościelisko", "poronin",
    "szczawnica", "niedzica", "niedzica-zamek", "sromowce wyżne", "kluszkowce",
    "jaworki", "ždiar", "vysoké tatry", "małe ciche", "brzegi", "rusinowa polana",
    "witów", "łopuszna", "czerwienne",
)


def normalize_city_name(name: str) -> str:
    """Lowercase + strip diacritics: 'Kraków' → 'krakow', 'Warsaw' → 'warsaw'."""
    if not name:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(name).lower().strip())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# FIX #254: Polish locative for "Must-see w/we …" (client: "Must-see w Wrocław").
_CITY_LOCATIVE_PL = {
    "wroclaw": "we Wrocławiu",
    "krakow": "w Krakowie",
    "warszawa": "w Warszawie",
    "warsaw": "w Warszawie",
    "katowice": "w Katowicach",
    "gliwice": "w Gliwicach",
    "zabrze": "w Zabrzu",
    "chorzow": "w Chorzowie",
    "chorzów": "w Chorzowie",
    "tychy": "w Tychach",
    "poznan": "w Poznaniu",
    "gdansk": "w Gdańsku",
    "gdynia": "w Gdyni",
    "sopot": "w Sopocie",
    "zakopane": "w Zakopanem",
    "karpacz": "w Karpaczu",
    "szklarska poreba": "w Szklarskiej Porębie",
    "jelenia gora": "w Jeleniej Górze",
    "kudowa-zdroj": "w Kudowie-Zdroju",
    "klodzko": "w Kłodzku",
    "polanica-zdroj": "w Polanicy-Zdroju",
}


def city_locative_pl(city: str) -> str:
    """Return 'we Wrocławiu' / 'w Krakowie' etc.; fallback 'w {city}'."""
    raw = (city or "").strip()
    if not raw:
        return "w Twojej destynacji"
    # NFKD does not fold Polish ł → l; do it explicitly for dict lookup.
    key = normalize_city_name(raw).replace("\u0142", "l")
    if key in _CITY_LOCATIVE_PL:
        return _CITY_LOCATIVE_PL[key]
    # Cities starting with W/F often take "we" in Polish — keep it simple.
    if raw[:1].lower() in ("w", "f"):
        return f"we {raw}"
    return f"w {raw}"


ZAKOPANE_REGION_NORM = frozenset(normalize_city_name(c) for c in ZAKOPANE_REGION_RAW)


def poi_city_norm(poi: Dict[str, Any]) -> str:
    return normalize_city_name(poi.get("city") or poi.get("City") or "")


def poi_hub_norm(poi: Dict[str, Any]) -> str:
    """Hub = sheet/region hub (FIX #189) — includes Zone C day-trip POIs near a city."""
    return normalize_city_name(
        poi.get("hub_city") or poi.get("Hub") or poi.get("hub") or ""
    )


# FIX #276/#277: hub city → satellite towns from the client's expanded sheets.
WROCLAW_SATELLITE_CITIES = (
    "Niemcza",
    "Oława",
    "Brzeg",
    "Ząbkowice Śląskie",
    "Mirosławice",
    "Ślęza",
    "Galowice",
    "Paniowice",
    "Żórawina",
)
WROCLAW_SATELLITE_NORMS = frozenset(
    normalize_city_name(c) for c in WROCLAW_SATELLITE_CITIES
)
WROCLAW_RESTAURANT_CITIES = (
    "Wrocław",
    "Oława",
    "Niemcza",
    "Ząbkowice Śląskie",
    "Żórawina",
    "Brzeg",
)

HUB_SATELLITE_CITIES = {
    "wroclaw": WROCLAW_SATELLITE_CITIES,
    "krakow": (
        "Wieliczka", "Bochnia", "Nowy Wiśnicz", "Czerna",
        "Ojców", "Sułoszowa",
    ),
    "poznan": ("Gniezno", "Kórnik", "Lednogóra", "Dziekanowice"),
    "warszawa": (
        "Sochaczew", "Żelazowa Wola", "Pomiechówek", "Granica",
        "Czosnów", "Góra Kalwaria", "Nowy Dwór Mazowiecki",
        "Izabelin", "Kampinos", "Pawilony", "Kiścinne",
    ),
    "warsaw": (
        "Sochaczew", "Żelazowa Wola", "Pomiechówek", "Granica",
        "Czosnów", "Góra Kalwaria", "Nowy Dwór Mazowiecki",
        "Izabelin", "Kampinos", "Pawilony", "Kiścinne",
    ),
}
HUB_RESTAURANT_CITIES = {
    "wroclaw": WROCLAW_RESTAURANT_CITIES,
    "krakow": ("Kraków", "Wieliczka", "Bochnia", "Ojców"),
    "poznan": ("Poznań", "Gniezno", "Kórnik"),
    "warszawa": (
        "Warszawa", "Góra Kalwaria", "Nowy Dwór Mazowiecki",
        "Sochaczew", "Kampinos", "Żelazowa Wola", "Pawilony",
    ),
    "warsaw": (
        "Warszawa", "Góra Kalwaria", "Nowy Dwór Mazowiecki",
        "Sochaczew", "Kampinos", "Żelazowa Wola", "Pawilony",
    ),
    "katowice": (
        "Katowice", "Gliwice", "Zabrze", "Tychy", "Chorzów",
        "Dąbrowa Górnicza",
    ),
}


def _fold_pl_city(name: str) -> str:
    """NFKD leaves Polish ł intact — fold it for Wrocław / Oława keys."""
    return normalize_city_name(name).replace("\u0142", "l").replace("ł", "l")


def wroclaw_poi_load_cities(requested_city: str) -> List[str]:
    """Cities to read from Excel for a Wrocław trip (hub + satellites)."""
    if _fold_pl_city(requested_city) != "wroclaw":
        return [requested_city] if requested_city else []
    return ["Wrocław", *WROCLAW_SATELLITE_CITIES]


def hub_poi_load_cities(requested_city: str) -> List[str]:
    """FIX #277: hub + satellite towns for Wrocław / Kraków / Poznań / Warszawa."""
    if not requested_city:
        return []
    sats = HUB_SATELLITE_CITIES.get(_fold_pl_city(requested_city))
    if not sats:
        return [requested_city]
    seen = []
    for c in (requested_city, *sats):
        if c not in seen:
            seen.append(c)
    return seen


def hub_restaurant_cities(requested_city: str) -> List[str]:
    """FIX #277: restaurants for the hub plus day-trip towns."""
    if not requested_city:
        return []
    cities = HUB_RESTAURANT_CITIES.get(_fold_pl_city(requested_city))
    if not cities:
        return [requested_city]
    return list(cities)


def _poi_excel_city_norm(poi: Dict[str, Any]) -> str:
    return normalize_city_name(poi.get("city_excel") or poi.get("City") or "")


def poi_matches_city_filter(poi: Dict[str, Any], city_filter: str) -> bool:
    req = normalize_city_name(city_filter)
    if not req:
        return True
    hub = poi_hub_norm(poi)
    pc = poi_city_norm(poi)
    excel_city = _poi_excel_city_norm(poi)
    # FIX #276/#277: hub trips may use satellite towns (Wrocław/Kraków/Poznań/Warszawa).
    _hub_key = _fold_pl_city(city_filter)
    _sats = HUB_SATELLITE_CITIES.get(_hub_key) or ()
    _sat = {_fold_pl_city(c) for c in _sats}
    if _sat and (
        _fold_pl_city(excel_city) in _sat or _fold_pl_city(pc) in _sat
    ):
        return True
    # FIX #200: hub is authoritative when set — wrong City column cannot pull POI into another trip
    # (e.g. Ogród Botaniczny Wrocławski with City=Kraków must not appear in Kraków plans).
    if hub:
        if req in ZAKOPANE_REGION_NORM:
            return hub in ZAKOPANE_REGION_NORM or pc in ZAKOPANE_REGION_NORM
        return hub == req
    if req in ZAKOPANE_REGION_NORM:
        return pc in ZAKOPANE_REGION_NORM
    return pc == req


def filter_pois_by_city(pois: List[Dict[str, Any]], city_filter: str) -> List[Dict[str, Any]]:
    if not city_filter:
        return pois
    before = len(pois)
    out = [p for p in pois if poi_matches_city_filter(p, city_filter)]
    if len(out) != before:
        print(f"[FIX #188] City guard '{city_filter}': {before} → {len(out)} POIs")
    return out


def filter_pois_by_cities(
    pois: List[Dict[str, Any]], cities: Iterable[str],
) -> List[Dict[str, Any]]:
    norms = {normalize_city_name(c) for c in cities if c}
    if not norms:
        return pois
    before = len(pois)
    out = [
        p for p in pois
        if poi_city_norm(p) in norms or poi_hub_norm(p) in norms
    ]
    if len(out) != before:
        print(f"[FIX #188] Multi-city guard {sorted(norms)}: {before} → {len(out)} POIs")
    return out


def is_zakopane_trip(context: Optional[Dict[str, Any]] = None) -> bool:
    return bool(context and context.get("is_zakopane_trip"))


def is_city_tourism_trip(context: Optional[Dict[str, Any]] = None) -> bool:
    """FIX #197: single-city urban trips (Kraków, Poznań…) — not Zakopane/mountain-only."""
    if not context or context.get("is_zakopane_trip"):
        return False
    if context.get("trip_type") in ("city_tourism", "mixed", "cluster"):
        return True
    # FIX #271: polish passes may omit trip_type — still walk the old town.
    city = str(context.get("requested_city") or context.get("city") or "").lower()
    return any(
        k in city for k in (
            "kraków", "krakow", "wrocław", "wroclaw", "warszawa", "warsaw",
            "poznań", "poznan", "gdańsk", "gdansk",
        )
    )


def multi_city_density_mode(
    context: Optional[Dict[str, Any]] = None,
    city_pool_size: int = 0,
) -> bool:
    """FIX #194/#209: looser fill gates for modest POI pools and spa clusters."""
    if not context or context.get("is_zakopane_trip"):
        return False
    pool = city_pool_size or int(context.get("city_pool_size") or 0)
    # FIX #209: Kotlina Kłodzka (Kudowa/Polanica/Kłodzko) — aggressive gap-fill.
    if (context.get("signals") or {}).get("cluster_type") == "regional_cluster":
        return True
    if (context.get("signals") or {}).get("cluster_type") == "radius_based":
        return True
    if context.get("soft_cluster"):
        return True
    if pool < 30:
        return True
    if context.get("is_cluster"):
        return False
    return 0 < pool < 85


def dinner_suggestions(is_zakopane: bool) -> List[str]:
    """FIX #234: no generic placeholder restaurants for city trips."""
    if is_zakopane:
        return ["Regionalna restauracja", "Bacówka", "Karcma góralska"]
    return []


def regional_food_free_time_label(is_zakopane: bool) -> str:
    if is_zakopane:
        return "Regionalny przystanek: oscypki, herbata góralska"
    return "Przerwa gastronomiczna: lokalne specjały, kawa"


def evening_kolacja_label(is_zakopane: bool, duration_min: int) -> str:
    if duration_min < 30:
        return "Czas przed kolacją"
    if is_zakopane:
        return "Kolacja i Krupówki: restauracja, spacer po Krupówkach"
    return "Kolacja i spacer: wybierz restaurację w pobliżu ostatniej atrakcji"


def evening_relax_label(is_zakopane: bool, now_min: int, *, long_block: bool = False) -> str:
    # FIX #229 (01.07.2026): "Wieczorny relaks" only from 17:00 — not at 11:00/12:30.
    _evening_start = 1020  # 17:00
    if is_zakopane:
        if now_min >= 1080 or (long_block and now_min >= _evening_start):
            return "Wieczorny relaks: termy, spacer po Krupówkach lub kolacja"
        if now_min >= _evening_start:
            return "Popołudniowy relaks: spacer, kawa, odpoczynek"
    else:
        if now_min >= 1080 or (long_block and now_min >= _evening_start):
            return "Wieczorny relaks: spacer po centrum lub kolacja"
        if now_min >= _evening_start:
            return "Popołudniowy relaks: spacer, kawa, odpoczynek"
    if now_min >= 780:  # 13:00+
        return "Popołudniowy relaks: spacer, kawa, odpoczynek"
    return "Przerwa: kawa, krótki spacer, odpoczynek"


def end_of_day_evening_copy(is_zakopane: bool, gap_to_end: int) -> tuple[str, List[str]]:
    if gap_to_end >= 90:
        label = evening_relax_label(is_zakopane, 900, long_block=True)
        if is_zakopane:
            sugg = [
                "Termy/SPA w okolicy",
                "Spacer po Krupówkach",
                "Kolacja w restauracji góralskiej",
            ]
        else:
            sugg = [
                "Spacer po centrum miasta",
                "Kolacja w restauracji",
                "Kawa w kawiarni",
            ]
    elif gap_to_end >= 60:
        label = "Wieczór: spacer i kolacja w centrum"
        if is_zakopane:
            sugg = [
                "Spacer po centrum Zakopanego",
                "Kolacja w restauracji",
                "Odpoczynek w hotelu",
            ]
        else:
            sugg = [
                "Spacer po centrum",
                "Kolacja w restauracji",
                "Odpoczynek w hotelu",
            ]
    else:
        label = "Czas wolny na koniec dnia"
        sugg = []
    return label, sugg


def evening_merge_suggestions(is_zakopane: bool) -> List[str]:
    if is_zakopane:
        return [
            "Termy/SPA w okolicy",
            "Spacer po Krupówkach",
            "Kolacja w restauracji góralskiej",
            "Relaks w hotelu",
            "Wieczorna kawa z widokiem na Tatry",
        ]
    return [
        "Spacer po centrum",
        "Kolacja w restauracji",
        "Kawa w kawiarni",
        "Relaks w hotelu",
        "Wieczorny widok na miasto",
    ]


def build_day_gap_fill_pool(
    day_num: int,
    all_pois: List[Dict[str, Any]],
    *,
    zone_pools: Optional[List[List[Dict[str, Any]]]] = None,
    zone_fallbacks: Optional[List[List[Dict[str, Any]]]] = None,
    requested_city: str = "",
    cluster_cities: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Per-day POI pool for gap-fill — mirrors engine zone routing."""
    pool: List[Dict[str, Any]] = []
    if zone_pools and day_num < len(zone_pools) and zone_pools[day_num]:
        pool = list(zone_pools[day_num])
    if zone_fallbacks and day_num < len(zone_fallbacks) and zone_fallbacks[day_num]:
        seen = {p.get("id") for p in pool}
        for p in zone_fallbacks[day_num]:
            if p.get("id") not in seen:
                pool.append(p)
                seen.add(p.get("id"))
    if not pool:
        pool = list(all_pois)
    if cluster_cities:
        pool = filter_pois_by_cities(pool, cluster_cities)
    elif requested_city:
        pool = filter_pois_by_city(pool, requested_city)
    return pool


def build_multi_city_gap_fill_pool(
    all_pois: List[Dict[str, Any]],
    *,
    requested_city: str = "",
    cluster_cities: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """FIX #194: full city pool for sparse-day gap-fill (non-Zakopane only)."""
    pool = list(all_pois)
    if cluster_cities:
        return filter_pois_by_cities(pool, cluster_cities)
    if requested_city:
        return filter_pois_by_city(pool, requested_city)
    return pool


def build_cluster_hub_day_pools(
    all_pois: List[Dict[str, Any]],
    num_days: int,
    cluster_cities: Optional[List[str]] = None,
    base_city: str = "",
) -> tuple[List[List[Dict[str, Any]]], List[List[Dict[str, Any]]], List[str]]:
    """FIX #201/#208: one hub city per day for clusters (Trójmiasto, Karkonosze…).

    FIX #208: when ``base_city`` is set (user's requested town), that hub gets the
    majority of early days before sibling cluster cities are introduced.
    """
    import math

    hubs: Dict[str, List[Dict[str, Any]]] = {}
    for p in all_pois:
        h = poi_hub_norm(p) or poi_city_norm(p)
        if not h:
            continue
        hubs.setdefault(h, []).append(p)
    if not hubs:
        full = list(all_pois)
        return [full] * num_days, [full] * num_days, [base_city or ""] * num_days

    base_norm = normalize_city_name(base_city) if base_city else ""

    def _hub_label(norm_h: str) -> str:
        if base_norm and norm_h == base_norm and base_city:
            return base_city
        for c in cluster_cities or []:
            if normalize_city_name(c) == norm_h:
                return c
        return norm_h

    # FIX #214/#215: short cluster trips — stay in requested town (2/3 days minimum).
    if base_norm and base_norm in hubs and num_days <= 4:
        other_hubs = [h for h in hubs if h != base_norm]
        if num_days <= 3:
            base_days = num_days if not other_hubs else max(num_days - 1, 2)
        else:
            base_days = max(num_days - 1, round(num_days * 0.75))
        base_days = min(base_days, num_days)
        day_hub_seq = [base_norm] * base_days
        for i in range(num_days - base_days):
            day_hub_seq.append(other_hubs[i % len(other_hubs)] if other_hubs else base_norm)
        day_hub_seq = day_hub_seq[:num_days]
        pools: List[List[Dict[str, Any]]] = []
        fallbacks: List[List[Dict[str, Any]]] = []
        day_hub_cities: List[str] = []
        for d in range(num_days):
            h = day_hub_seq[d]
            pool = list(hubs.get(h, []))
            pools.append(pool)
            fallbacks.append(list(pool))
            day_hub_cities.append(_hub_label(h))
            print(f"[FIX #214] Cluster day {d + 1} → hub '{day_hub_cities[-1]}' ({len(pool)} POI)")
        return pools, fallbacks, day_hub_cities

    if cluster_cities:
        hub_order = []
        if base_norm and base_norm in hubs:
            hub_order.append(base_norm)
        for c in cluster_cities:
            cn = normalize_city_name(c)
            if cn in hubs and cn not in hub_order:
                hub_order.append(cn)
        for h in sorted(hubs.keys(), key=lambda x: -len(hubs[x])):
            if h not in hub_order:
                hub_order.append(h)
    else:
        hub_order = sorted(hubs.keys(), key=lambda x: -len(hubs[x]))
        if base_norm and base_norm in hub_order:
            hub_order = [base_norm] + [h for h in hub_order if h != base_norm]

    if base_norm and base_norm in hub_order and num_days > len(hub_order):
        other_hubs = [h for h in hub_order if h != base_norm]
        _largest = max(len(hubs[h]) for h in hub_order) if hub_order else 0
        _base_size = len(hubs.get(base_norm, []))
        # FIX #210: smaller base hub (Gdynia/Sopot vs Gdańsk) → more days at base.
        _base_pct = 0.65 if _base_size < _largest else 0.55
        base_days = max(1, round(num_days * _base_pct))
        day_hub_seq = [base_norm] * base_days
        for i in range(num_days - base_days):
            day_hub_seq.append(other_hubs[i % len(other_hubs)] if other_hubs else base_norm)
        day_hub_seq = day_hub_seq[:num_days]
    elif num_days <= len(hub_order):
        day_hub_seq = hub_order[:num_days]
        if base_norm and base_norm in hub_order:
            day_hub_seq[0] = base_norm
    else:
        hub_days = {h: 1 for h in hub_order}
        extra = num_days - len(hub_order)
        total = sum(len(hubs[h]) for h in hub_order) or 1
        if base_norm and base_norm in hub_order:
            _largest2 = max(len(hubs[h]) for h in hub_order) if hub_order else 0
            _base_pct2 = 0.65 if len(hubs.get(base_norm, [])) < _largest2 else 0.55
            base_share = max(1, round(extra * _base_pct2))
            hub_days[base_norm] += base_share
            extra -= base_share
            others = [h for h in hub_order if h != base_norm]
            ototal = sum(len(hubs[h]) for h in others) or 1
            for h in others:
                add = int(math.floor(extra * len(hubs[h]) / ototal)) if extra > 0 else 0
                hub_days[h] += add
            rem = extra - sum(int(math.floor(extra * len(hubs[h]) / ototal)) for h in others)
            rank = {h: i for i, h in enumerate(others)}
            for h in sorted(others, key=lambda z: (-len(hubs[z]), rank.get(z, 99)))[:rem]:
                hub_days[h] += 1
        else:
            raw = {h: extra * len(hubs[h]) / total for h in hub_order}
            base = {h: int(math.floor(raw[h])) for h in hub_order}
            for h in hub_order:
                hub_days[h] = 1 + base[h]
            rem = extra - sum(base.values())
            rank = {h: i for i, h in enumerate(hub_order)}
            for h in sorted(hub_order, key=lambda z: (-(raw[z] - base[z]), rank[z]))[:rem]:
                hub_days[h] += 1
        day_hub_seq = []
        for h in hub_order:
            day_hub_seq += [h] * hub_days[h]
        day_hub_seq = (day_hub_seq + [hub_order[0]] * num_days)[:num_days]
        if base_norm and base_norm in hub_order:
            day_hub_seq[0] = base_norm

    pools: List[List[Dict[str, Any]]] = []
    fallbacks: List[List[Dict[str, Any]]] = []
    day_hub_cities: List[str] = []
    for d in range(num_days):
        h = day_hub_seq[d]
        pool = list(hubs.get(h, []))
        pools.append(pool)
        fallbacks.append(list(pool))
        label = _hub_label(h)
        day_hub_cities.append(label)
        print(f"[FIX #201/#208] Cluster day {d + 1} → hub '{label}' ({len(pool)} POI)")
    return pools, fallbacks, day_hub_cities
