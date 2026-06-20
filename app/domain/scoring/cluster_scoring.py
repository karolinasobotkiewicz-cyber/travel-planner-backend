"""
FIX #212 — wire DestinationClusters scoring_weights into score_poi() / travel.

Weights from destination_clusters.py (Phase 7):
  urban_organism:     location_diversity, transit_penalty, urban_accessibility
  regional_cluster:   location_diversity, transit_penalty, spa_wellness, slow_pace
  radius_based:       location_diversity, transit_penalty, mountain_nature,
                      outdoor_activities, scenic_views
"""
from __future__ import annotations

from typing import Any, Dict, Optional


def _poi_hub_key(poi: Optional[dict]) -> str:
    if not poi:
        return ""
    from app.domain.planner.city_copy import poi_hub_norm, poi_city_norm
    return poi_hub_norm(poi) or poi_city_norm(poi) or ""


def effective_travel_minutes(
    travel_min: int,
    context: dict,
    from_poi: Optional[dict] = None,
    to_poi: Optional[dict] = None,
) -> int:
    """Apply cluster transit_penalty when crossing hub cities."""
    if travel_min <= 0:
        return travel_min
    weights = (context or {}).get("scoring_weights") or {}
    tp = float(weights.get("transit_penalty", 1.0))
    if tp == 1.0:
        return travel_min
    hub_a = _poi_hub_key(from_poi)
    hub_b = _poi_hub_key(to_poi)
    if hub_a and hub_b and hub_a != hub_b:
        return max(int(travel_min * tp), 1)
    return travel_min


def apply_cluster_scoring_weights(
    score: float,
    poi: dict,
    user: dict,
    context: dict,
    scoring_weights: Dict[str, float],
    *,
    tag_bonus: float,
    poi_matches_preferences: bool,
) -> float:
    """Apply cluster-specific scoring multipliers from router config."""
    if not scoring_weights:
        return score

    cluster_type = (context or {}).get("signals", {}).get("cluster_type")
    if not cluster_type:
        return score

    tags = {str(t).lower() for t in (poi.get("tags") or []) if t}
    name = str(poi.get("name", "")).lower()
    delta = 0.0

    # ── urban_organism (Trójmiasto) ──
    ua = float(scoring_weights.get("urban_accessibility", 1.0))
    if ua > 1.0 and cluster_type == "urban_organism":
        crowd_raw = str(poi.get("crowd_level", "")).strip()
        try:
            crowd = int(crowd_raw) if crowd_raw else 99
        except (ValueError, TypeError):
            crowd = 99
        space = str(poi.get("space", "")).lower()
        accessible = (
            crowd <= 2
            or space == "indoor"
            or "public_transport" in tags
            or "accessible" in tags
            or "urban" in tags
        )
        if accessible:
            boost = score * (ua - 1.0) * 0.35
            score += boost
            delta += boost

    # ── location_diversity — reward POI outside base hub ──
    ld = float(scoring_weights.get("location_diversity", 1.0))
    if ld > 1.0:
        from app.domain.planner.city_copy import normalize_city_name
        req = normalize_city_name((context or {}).get("requested_city", ""))
        hub = _poi_hub_key(poi)
        if hub and hub != req:
            if poi_matches_preferences and tag_bonus > 0:
                boost = tag_bonus * (ld - 1.0)
            else:
                boost = score * 0.04 * (ld - 1.0)
            score += boost
            delta += boost

    # ── regional_cluster (Kotlina) — spa / slow pace ──
    sw = float(scoring_weights.get("spa_wellness", 1.0))
    if sw > 1.0 and cluster_type == "regional_cluster":
        from app.domain.planner.engine import is_termy_spa, is_relax_gap_fill_poi
        if is_termy_spa(poi) or is_relax_gap_fill_poi(poi):
            boost = (tag_bonus if tag_bonus > 0 else 30.0) * (sw - 1.0)
            score += boost
            delta += boost

    sp = float(scoring_weights.get("slow_pace", 1.0))
    if sp > 1.0 and cluster_type == "regional_cluster":
        prefs = user.get("preferences") or []
        if user.get("travel_style") == "relax" or "relaxation" in prefs:
            dur = int(poi.get("time_min") or poi.get("duration_min") or 60)
            intensity = str(poi.get("intensity", "")).lower()
            if dur <= 90 and intensity in ("low", "medium", ""):
                boost = 12.0 * (sp - 1.0) * 5
                score += boost
                delta += boost

    # ── radius_based (Karkonosze) — mountain / outdoor / scenic ──
    if cluster_type == "radius_based":
        mn = float(scoring_weights.get("mountain_nature", 1.0))
        if mn > 1.0 and (
            poi.get("type") == "trail"
            or tags & {"nature", "mountain", "nature_landscape", "waterfall", "forest"}
        ):
            boost = (tag_bonus if tag_bonus > 0 else 28.0) * (mn - 1.0)
            score += boost
            delta += boost

        oa = float(scoring_weights.get("outdoor_activities", 1.0))
        if oa > 1.0 and (
            poi.get("type") == "trail"
            or tags & {"outdoor", "hiking", "active_sport", "mountain_trails"}
        ):
            boost = 18.0 * (oa - 1.0)
            score += boost
            delta += boost

        sv = float(scoring_weights.get("scenic_views", 1.0))
        if sv > 1.0 and (
            tags & {"scenic_viewpoint", "viewpoint", "panoramic_view", "mountain_viewpoint"}
            or "widok" in name or "punkt widok" in name
        ):
            boost = 15.0 * (sv - 1.0)
            score += boost
            delta += boost

    if delta > 0.5:
        poi_name = str(poi.get("name", "Unknown")).encode("ascii", errors="ignore").decode("ascii")
        print(f"    [FIX #212 CLUSTER WEIGHTS] {poi_name}: +{delta:.1f} ({cluster_type})")

    return score
