"""Deduplicate external/map POIs against Excel-curated pool."""
from __future__ import annotations

import re
import unicodedata
from typing import Dict, Iterable, List, Sequence

from app.infrastructure.routing.haversine import haversine_km

_STRIP_WORDS = (
    "muzeum", "museum", "park", "zamek", "castle", "kościół", "kosciol",
    "church", "galeria", "gallery", "centrum", "the", "w", "we", "na",
)


def _normalize_name(name: str) -> str:
    s = (name or "").lower().strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    for w in _STRIP_WORDS:
        s = re.sub(rf"\b{w}\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _name_similarity(a: str, b: str) -> float:
    na, nb = _normalize_name(a), _normalize_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return 0.85
    ta, tb = set(na.split()), set(nb.split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


def is_duplicate_of_excel(
    external: dict,
    excel_poi: dict,
    *,
    distance_m: float = 150.0,
    name_threshold: float = 0.72,
) -> bool:
    lat1, lng1 = external.get("lat"), external.get("lng")
    lat2, lng2 = excel_poi.get("lat"), excel_poi.get("lng")
    if None in (lat1, lng1, lat2, lng2):
        return _name_similarity(
            external.get("name", ""), excel_poi.get("name", "")
        ) >= 0.92
    dist_km = haversine_km(float(lat1), float(lng1), float(lat2), float(lng2))
    if dist_km * 1000 < 50:
        return True
    if dist_km * 1000 > distance_m:
        return False
    sim = _name_similarity(external.get("name", ""), excel_poi.get("name", ""))
    if sim >= name_threshold:
        return True
    if dist_km * 1000 < 50 and sim >= 0.5:
        return True
    return False


def filter_external_duplicates(
    external_candidates: Sequence[dict],
    excel_pool: Sequence[dict],
) -> List[dict]:
    """Keep only external POIs that do not duplicate Excel entries."""
    kept: List[dict] = []
    for ext in external_candidates:
        if any(is_duplicate_of_excel(ext, ex) for ex in excel_pool):
            continue
        kept.append(ext)
    return kept


def dedupe_external_list(candidates: Sequence[dict]) -> List[dict]:
    """Remove duplicates within external candidates."""
    out: List[dict] = []
    for c in candidates:
        if any(is_duplicate_of_excel(c, prev) for prev in out):
            continue
        out.append(c)
    return out
