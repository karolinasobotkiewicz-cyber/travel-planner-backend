"""OpenRouteService HTTP client — Directions + Matrix."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests

from app.infrastructure.config.settings import settings

logger = logging.getLogger(__name__)

ORS_BASE = "https://api.openrouteservice.org"


class ORSBudgetExhausted(Exception):
    """Daily ORS call budget exceeded — use haversine."""


class ORSClient:
    def __init__(self) -> None:
        self._directions_today = 0
        self._matrix_today = 0

    @property
    def api_key(self) -> str:
        return (settings.ors_api_key or "").strip()

    def enabled(self) -> bool:
        return bool(settings.ors_enabled and settings.ors_routing_enabled and self.api_key)

    def matrix_enabled(self) -> bool:
        return bool(self.enabled() and settings.ors_matrix_enabled)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }

    def _check_directions_budget(self) -> None:
        if self._directions_today >= settings.ors_daily_budget_directions:
            raise ORSBudgetExhausted("ORS directions daily budget exhausted")

    def _check_matrix_budget(self) -> None:
        if self._matrix_today >= settings.ors_daily_budget_matrix:
            raise ORSBudgetExhausted("ORS matrix daily budget exhausted")

    def directions(
        self,
        lat1: float,
        lng1: float,
        lat2: float,
        lng2: float,
        profile: str,
    ) -> Optional[Dict[str, Any]]:
        if not self.enabled():
            return None
        self._check_directions_budget()
        url = f"{ORS_BASE}/v2/directions/{profile}"
        body = {
            "coordinates": [[lng1, lat1], [lng2, lat2]],
            "geometry": True,
            "instructions": False,
            "format": "geojson",
        }
        try:
            r = requests.post(url, json=body, headers=self._headers(), timeout=15)
            self._directions_today += 1
            if r.status_code == 429:
                logger.warning("ORS rate limit — falling back to haversine")
                return None
            r.raise_for_status()
            data = r.json()
        except requests.RequestException as exc:
            logger.warning("ORS directions failed: %s", exc)
            return None

        routes = data.get("routes") or []
        if not routes:
            return None
        summary = routes[0].get("summary") or {}
        geometry = routes[0].get("geometry")
        coords: List[List[float]] = []
        if isinstance(geometry, dict) and geometry.get("type") == "LineString":
            coords = geometry.get("coordinates") or []
        elif isinstance(geometry, str) and geometry:
            coords = [[lng1, lat1], [lng2, lat2]]
        if not coords:
            coords = [[lng1, lat1], [lng2, lat2]]
        duration_sec = float(summary.get("duration") or 0)
        distance_m = float(summary.get("distance") or 0)
        return {
            "duration_min": max(int(duration_sec / 60), 1),
            "distance_km": distance_m / 1000.0,
            "geometry": coords,
            "profile": profile,
        }

    def matrix_durations(
        self,
        coordinates: Sequence[Tuple[float, float]],
        profile: str,
    ) -> Optional[List[List[float]]]:
        """Return duration matrix in minutes (NxN). coordinates = [(lat,lng), ...]."""
        if not self.matrix_enabled() or len(coordinates) < 2:
            return None
        n = len(coordinates)
        if n > settings.ors_matrix_max_locations:
            return None
        self._check_matrix_budget()
        url = f"{ORS_BASE}/v2/matrix/{profile}"
        body = {
            "locations": [[lng, lat] for lat, lng in coordinates],
            "metrics": ["duration"],
            "units": "m",
        }
        try:
            r = requests.post(url, json=body, headers=self._headers(), timeout=20)
            self._matrix_today += 1
            if r.status_code == 429:
                return None
            r.raise_for_status()
            data = r.json()
        except requests.RequestException as exc:
            logger.warning("ORS matrix failed: %s", exc)
            return None

        durations = data.get("durations")
        if not durations:
            return None
        out: List[List[float]] = []
        for row in durations:
            out.append([(d or 0) / 60.0 for d in row])
        return out


_ors_client: Optional[ORSClient] = None


def get_ors_client() -> ORSClient:
    global _ors_client
    if _ors_client is None:
        _ors_client = ORSClient()
    return _ors_client
