"""Supplement Excel POI pool with map-sourced candidates (gap-fill only)."""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Sequence

from app.infrastructure.config.settings import settings
from app.infrastructure.routing.dedup import dedupe_external_list, filter_external_duplicates
from app.infrastructure.routing.overpass import fetch_tourism_cached

logger = logging.getLogger(__name__)


def _city_center(pool: Sequence[dict], city: str) -> Optional[tuple]:
    coords = [
        (float(p["lat"]), float(p["lng"]))
        for p in pool
        if p.get("lat") is not None
        and p.get("lng") is not None
        and (not city or (p.get("city") or p.get("hub_city") or "").lower() == city.lower())
    ]
    if not coords:
        coords = [
            (float(p["lat"]), float(p["lng"]))
            for p in pool
            if p.get("lat") is not None and p.get("lng") is not None
        ]
    if not coords:
        return None
    return sum(c[0] for c in coords) / len(coords), sum(c[1] for c in coords) / len(coords)


def should_supplement(
    attraction_count: int,
    free_time_min: int,
    *,
    day_num: int = 1,
    num_days: int = 1,
    duplication_gap: bool = False,
) -> bool:
    """
    FIX #221: Overpass supplement ONLY when gap-fill exhausted the Excel pool.
    Triggers: empty/sparse day after fill, large free_time blocks, dedup exhaustion.
    No proactive supplement on merely sparse pre-check days (regression vs FIX #220).
    """
    if not settings.ors_poi_supplement_enabled or not settings.ors_enabled:
        return False
    if duplication_gap:
        return True
    if attraction_count == 0 and free_time_min >= 90:
        return True
    if free_time_min >= 180:
        return True
    if free_time_min >= 120 and attraction_count < 4:
        return True
    return False


def supplement_external_pois(
    excel_pool: Sequence[dict],
    city: str,
    user_preferences: Sequence[str],
    *,
    max_candidates: int = 12,
) -> List[dict]:
    """
    Fetch Overpass POIs near city center, dedupe against Excel, score by prefs.
    Returns normalized POI dicts ready for gap-fill (never replaces Excel).
    """
    center = _city_center(excel_pool, city)
    if not center:
        return []
    lat, lng = center
    raw = fetch_tourism_cached(lat, lng, city, radius_m=settings.ors_overpass_radius_m)
    unique = dedupe_external_list(filter_external_duplicates(raw, excel_pool))
    if not unique:
        return []

    prefs = set(user_preferences or [])

    def _score(p: dict) -> float:
        tags = set(str(t).lower() for t in (p.get("tags") or []))
        s = 0.0
        for pref in prefs:
            if pref in tags:
                s += 10.0
        s -= 5.0  # external penalty vs Excel
        return s

    ranked = sorted(unique, key=_score, reverse=True)
    out = ranked[:max_candidates]
    logger.info(
        "[ORS/Overpass] Supplement %s: %d candidates (from %d raw)",
        city, len(out), len(raw),
    )
    return out
