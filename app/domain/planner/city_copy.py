"""
FIX #188 — city-aware copy and POI city guards (non-Zakopane cities).

Single source for:
- diacritic-insensitive city matching
- Zakopane-only vs neutral free_time / dinner / evening suggestions
"""
from __future__ import annotations

import unicodedata
from typing import Any, Dict, Iterable, List, Optional

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


ZAKOPANE_REGION_NORM = frozenset(normalize_city_name(c) for c in ZAKOPANE_REGION_RAW)


def poi_city_norm(poi: Dict[str, Any]) -> str:
    return normalize_city_name(poi.get("city") or poi.get("City") or "")


def poi_hub_norm(poi: Dict[str, Any]) -> str:
    """Hub = sheet/region hub (FIX #189) — includes Zone C day-trip POIs near a city."""
    return normalize_city_name(
        poi.get("hub_city") or poi.get("Hub") or poi.get("hub") or ""
    )


def poi_matches_city_filter(poi: Dict[str, Any], city_filter: str) -> bool:
    req = normalize_city_name(city_filter)
    if not req:
        return True
    if poi_hub_norm(poi) == req:
        return True
    pc = poi_city_norm(poi)
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


def multi_city_density_mode(
    context: Optional[Dict[str, Any]] = None,
    city_pool_size: int = 0,
) -> bool:
    """FIX #194: looser fill gates for single-city trips with a modest POI pool."""
    if not context or context.get("is_zakopane_trip") or context.get("is_cluster"):
        return False
    pool = city_pool_size or int(context.get("city_pool_size") or 0)
    return 0 < pool < 85


def dinner_suggestions(is_zakopane: bool) -> List[str]:
    if is_zakopane:
        return ["Regionalna restauracja", "Bacówka", "Karcma góralska"]
    return ["Restauracja w centrum", "Lokalna kuchnia regionalna", "Kawiarnia z kolacją"]


def regional_food_free_time_label(is_zakopane: bool) -> str:
    if is_zakopane:
        return "Regionalny przystanek: oscypki, herbata góralska"
    return "Przerwa gastronomiczna: lokalne specjały, kawa"


def evening_kolacja_label(is_zakopane: bool, duration_min: int) -> str:
    if duration_min < 30:
        return "Czas przed kolacją"
    if is_zakopane:
        return "Kolacja i Krupówki: restauracja, spacer po Krupówkach"
    return "Kolacja i spacer: restauracja w centrum"


def evening_relax_label(is_zakopane: bool, now_min: int, *, long_block: bool = False) -> str:
    if is_zakopane:
        if now_min >= 1080 or long_block:
            return "Wieczorny relaks: termy, spacer po Krupówkach lub kolacja"
        if now_min >= 900:
            return "Wieczorny relaks: termy, spacer po Krupówkach lub kolacja"
    else:
        if now_min >= 1080 or long_block:
            return "Wieczorny relaks: spacer po centrum lub kolacja"
        if now_min >= 900:
            return "Wieczorny relaks: spacer po starówce lub kolacja"
    return "Czas wolny do końca dnia: kolacja, spacer, zakupy, relaks"


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
