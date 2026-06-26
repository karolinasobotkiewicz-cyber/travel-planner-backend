"""Unified travel route provider — cache → ORS → haversine."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.infrastructure.config.settings import settings
from app.infrastructure.routing.cache import get_cached, make_route_key, set_cached
from app.infrastructure.routing.haversine import haversine_route, resolve_profile
from app.infrastructure.routing.models import RouteResult
from app.infrastructure.routing.ors_client import ORSBudgetExhausted, get_ors_client

logger = logging.getLogger(__name__)

_session: Dict[str, RouteResult] = {}


def clear_route_session() -> None:
    _session.clear()


def _coords(a: dict, b: dict) -> Optional[tuple]:
    lat1, lng1 = a.get("lat"), a.get("lng")
    lat2, lng2 = b.get("lat"), b.get("lng")
    if not all(v is not None for v in (lat1, lng1, lat2, lng2)):
        return None
    return float(lat1), float(lng1), float(lat2), float(lng2)


def get_travel_route(a: dict, b: dict, context: Optional[dict] = None) -> RouteResult:
    ctx = context or {}
    coords = _coords(a, b)
    if coords is None:
        return RouteResult(10, 0.0, "driving-car", "haversine")

    lat1, lng1, lat2, lng2 = coords
    profile = resolve_profile(a, b, ctx)
    session_key = make_route_key(lat1, lng1, lat2, lng2, profile)
    if session_key in _session:
        return _session[session_key]

    ttl = settings.ors_cache_ttl_days * 86400
    cached = get_cached(session_key, ttl)
    if cached:
        result = RouteResult(
            duration_min=int(cached["duration_min"]),
            distance_km=float(cached["distance_km"]),
            profile=cached.get("profile", profile),
            source="cache",
            geometry=cached.get("geometry") or [],
        )
        _session[session_key] = result
        return result

    result: RouteResult
    client = get_ors_client()
    if client.enabled():
        try:
            ors = client.directions(lat1, lng1, lat2, lng2, profile)
            if ors:
                result = RouteResult(
                    duration_min=int(ors["duration_min"]),
                    distance_km=float(ors["distance_km"]),
                    profile=profile,
                    source="ors",
                    geometry=ors.get("geometry") or [[lng1, lat1], [lng2, lat2]],
                )
                set_cached(session_key, {
                    "duration_min": result.duration_min,
                    "distance_km": result.distance_km,
                    "profile": profile,
                    "geometry": result.geometry,
                })
                _session[session_key] = result
                return result
        except ORSBudgetExhausted:
            logger.info("ORS budget exhausted — haversine fallback")

    result = haversine_route(a, b, ctx)
    _session[session_key] = result
    return result


def get_travel_minutes(a: dict, b: dict, context: Optional[dict] = None) -> int:
    return get_travel_route(a, b, context).duration_min
