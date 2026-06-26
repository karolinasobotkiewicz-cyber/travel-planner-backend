"""Routing result types."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class RouteResult:
    """Single leg between two coordinate points."""

    duration_min: int
    distance_km: float
    profile: str  # foot-walking | driving-car
    source: str  # ors | haversine | cache
    geometry: List[List[float]] = field(default_factory=list)
    """GeoJSON order [lng, lat] per point — see docs for Leaflet conversion."""

    def geometry_latlng(self) -> List[List[float]]:
        """Convert to [lat, lng] for Leaflet Polyline."""
        return [[pt[1], pt[0]] for pt in self.geometry if len(pt) >= 2]

    def to_transit_extras(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "distance_km": round(self.distance_km, 3),
            "routing_source": self.source,
        }
        if self.geometry:
            out["geometry"] = self.geometry
            out["geometry_latlng"] = self.geometry_latlng()
        return out
