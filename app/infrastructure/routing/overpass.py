"""Overpass API — fetch tourism POIs when Excel pool is insufficient."""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Dict, List, Optional, Sequence

import requests

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

_OSM_TAG_TO_OUR = {
    "museum": ("museum_heritage",),
    "gallery": ("museum_heritage",),
    "artwork": ("museum_heritage",),
    "attraction": ("museum_heritage", "history_mystery"),
    "viewpoint": ("nature_landscape",),
    "park": ("nature_landscape", "relaxation"),
    "garden": ("nature_landscape", "relaxation"),
    "zoo": ("kids_attractions",),
    "theme_park": ("kids_attractions", "active_sport"),
    "castle": ("museum_heritage", "history_mystery"),
    "ruins": ("history_mystery",),
    "archaeological_site": ("history_mystery", "museum_heritage"),
    "monastery": ("history_mystery",),
    "place_of_worship": ("history_mystery",),
}


def _stable_id(name: str, lat: float, lng: float) -> str:
    raw = f"{name}|{round(lat, 5)}|{round(lng, 5)}"
    return "ext_osm_" + hashlib.sha1(raw.encode()).hexdigest()[:12]


def _tags_from_element(tags: dict) -> List[str]:
    out: List[str] = []
    for key in ("tourism", "leisure", "historic", "amenity"):
        val = tags.get(key)
        if not val:
            continue
        mapped = _OSM_TAG_TO_OUR.get(val)
        if mapped:
            out.extend(mapped)
    if tags.get("tourism") == "museum":
        out.append("museum")
    return list(dict.fromkeys(out))


def _duration_for_tags(tags: List[str]) -> int:
    if "museum_heritage" in tags:
        return 90
    if "nature_landscape" in tags:
        return 60
    if "kids_attractions" in tags:
        return 120
    return 45


def normalize_overpass_element(el: dict, city: str) -> Optional[dict]:
    tags = el.get("tags") or {}
    name = tags.get("name") or tags.get("name:pl") or tags.get("name:en")
    if not name:
        return None
    lat = el.get("lat")
    lng = el.get("lon")
    if lat is None or lng is None:
        center = el.get("center") or {}
        lat, lng = center.get("lat"), center.get("lon")
    if lat is None or lng is None:
        return None

    tag_list = _tags_from_element(tags)
    if not tag_list:
        tag_list = ["museum_heritage"]

    dur = _duration_for_tags(tag_list)
    return {
        "id": _stable_id(name, float(lat), float(lng)),
        "name": name,
        "lat": float(lat),
        "lng": float(lng),
        "type": "poi",
        "source": "external_overpass",
        "confidence": "low",
        "priority_level": 2,
        "must_see": 0,
        "tags": tag_list,
        "tags_excel": tag_list,
        "target_groups": ["all", "friends", "couples", "solo", "family_kids"],
        "city": city,
        "hub_city": city,
        "time_min": dur,
        "time_max": dur + 30,
        "duration_min": dur,
        "season_fit": {"winter": 1, "spring": 1, "summer": 1, "autumn": 1},
        "opening_hours": None,
        "description_short": f"Atrakcja uzupełniająca z mapy (OpenStreetMap): {name}.",
    }


def fetch_tourism_near(
    lat: float,
    lng: float,
    radius_m: int = 2500,
    city: str = "",
    limit: int = 25,
) -> List[dict]:
    """Query Overpass for tourism/leisure POIs near a point."""
    query = f"""
    [out:json][timeout:25];
    (
      node["tourism"](around:{radius_m},{lat},{lng});
      way["tourism"](around:{radius_m},{lat},{lng});
      node["leisure"~"park|garden|nature_reserve"](around:{radius_m},{lat},{lng});
      way["leisure"~"park|garden|nature_reserve"](around:{radius_m},{lat},{lng});
      node["historic"](around:{radius_m},{lat},{lng});
      way["historic"](around:{radius_m},{lat},{lng});
    );
    out center {limit};
    """
    try:
        r = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=30,
            headers={"User-Agent": "TravelPlannerBackend/1.0"},
        )
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as exc:
        logger.warning("Overpass query failed: %s", exc)
        return []

    elements = data.get("elements") or []
    out: List[dict] = []
    for el in elements:
        poi = normalize_overpass_element(el, city)
        if poi:
            out.append(poi)
        if len(out) >= limit:
            break
    return out


_overpass_cache: Dict[str, tuple] = {}
_CACHE_TTL = 3600


def fetch_tourism_cached(
    lat: float, lng: float, city: str, radius_m: int = 2500,
) -> List[dict]:
    key = f"{round(lat, 3)}|{round(lng, 3)}|{radius_m}|{city}"
    now = time.time()
    hit = _overpass_cache.get(key)
    if hit and now - hit[0] < _CACHE_TTL:
        return hit[1]
    pois = fetch_tourism_near(lat, lng, radius_m=radius_m, city=city)
    _overpass_cache[key] = (now, pois)
    return pois
