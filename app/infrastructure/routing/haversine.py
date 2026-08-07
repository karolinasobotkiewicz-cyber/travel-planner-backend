"""Haversine travel time — mirrors engine.py logic (fallback)."""
from __future__ import annotations

import math
from typing import Any, Dict, Optional

from app.infrastructure.routing.models import RouteResult

WALK_THRESHOLD_KM = 1.2
CITY_TOURISM_WALK_THRESHOLD_KM = 3.5
CITY_TOURISM_WALK_SPEED_KMH = 4.5
WALK_THRESHOLD_MOUNTAIN_KM = 0.6

CLUSTER_ROAD_SPEEDS_KMH = {
    "urban_organism": 60.0,
    "regional_cluster": 50.0,
    "radius_based": 40.0,
    "standalone_city": 45.0,
}


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


def _walk_threshold_km(a: dict, b: dict, context: Optional[dict]) -> float:
    from app.domain.planner.city_copy import is_city_tourism_trip

    if context and is_city_tourism_trip(context):
        return CITY_TOURISM_WALK_THRESHOLD_KM
    for p in (a, b):
        tags = {str(t).lower() for t in (p.get("tags") or [])}
        if tags & {"mountain_trails", "hiking", "trail", "alpine"}:
            return WALK_THRESHOLD_MOUNTAIN_KM
        if str(p.get("type", "")).lower() == "trail":
            return WALK_THRESHOLD_MOUNTAIN_KM
    return WALK_THRESHOLD_KM


def resolve_profile(a: dict, b: dict, context: Optional[dict]) -> str:
    lat1, lng1 = a.get("lat"), a.get("lng")
    lat2, lng2 = b.get("lat"), b.get("lng")
    if not all(v is not None for v in (lat1, lng1, lat2, lng2)):
        return "driving-car"
    dist = haversine_km(float(lat1), float(lng1), float(lat2), float(lng2))
    ctx = context or {}
    # FIX #255: align with get_transport_mode — car users drive urban legs ≥1.2 km
    # (previously foot-walking up to 3.5 km produced 40–90 min "walks" to lunch).
    from app.domain.planner.city_copy import is_city_tourism_trip
    modes = ctx.get("transport_modes") or []
    if ctx.get("has_car", True) and ("car" in modes or not modes):
        city = is_city_tourism_trip(ctx)
        floor = 1.2 if city else 0.6
        if dist >= floor:
            return "driving-car"
        if city and dist < 1.0:
            return "foot-walking"
    thresh = _walk_threshold_km(a, b, context)
    return "foot-walking" if dist < thresh else "driving-car"


def haversine_route(a: dict, b: dict, context: Optional[dict] = None) -> RouteResult:
    ctx = context or {}
    if not ctx.get("has_car", True):
        return RouteResult(0, 0.0, "foot-walking", "haversine")

    lat1, lng1 = a.get("lat"), a.get("lng")
    lat2, lng2 = b.get("lat"), b.get("lng")
    if not all(v is not None for v in (lat1, lng1, lat2, lng2)):
        return RouteResult(10, 0.0, "driving-car", "haversine")

    lat1, lng1, lat2, lng2 = float(lat1), float(lng1), float(lat2), float(lng2)
    distance_km = haversine_km(lat1, lng1, lat2, lng2)
    from app.domain.planner.city_copy import is_city_tourism_trip

    city_trip = is_city_tourism_trip(ctx)
    walk_thresh = _walk_threshold_km(a, b, ctx)
    # FIX #255: same car preference as resolve_profile / get_transport_mode.
    modes = ctx.get("transport_modes") or []
    prefer_car = ctx.get("has_car", True) and ("car" in modes or not modes)
    car_floor = 1.2 if city_trip else 0.6
    use_walk = distance_km < walk_thresh
    if prefer_car and distance_km >= car_floor:
        use_walk = False
    if city_trip and prefer_car and distance_km < 1.0:
        use_walk = True

    if use_walk:
        speed = CITY_TOURISM_WALK_SPEED_KMH if city_trip else 5.0
        mins = max(int((distance_km / speed) * 60), 5)
        profile = "foot-walking"
        road_km = distance_km
    else:
        road_km = distance_km * (1.45 if city_trip else 1.0)
        cluster_type = (ctx.get("signals") or {}).get("cluster_type", "standalone_city")
        speed = CLUSTER_ROAD_SPEEDS_KMH.get(cluster_type, 45.0)
        raw = max(int((road_km / speed) * 60 + 5), 10)
        try:
            from app.domain.planner.engine import effective_travel_minutes

            mins = effective_travel_minutes(raw, ctx, from_poi=a, to_poi=b)
        except Exception:
            mins = raw
        profile = "driving-car"

    geometry = [[lng1, lat1], [lng2, lat2]]
    source = "estimated_road" if profile == "driving-car" else "haversine"
    return RouteResult(mins, road_km, profile, source, geometry)
