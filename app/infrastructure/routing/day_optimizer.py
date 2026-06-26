"""Optimize attraction visit order within a day using ORS Matrix."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from app.infrastructure.config.settings import settings
from app.infrastructure.routing.haversine import haversine_km, resolve_profile
from app.infrastructure.routing.ors_client import get_ors_client

logger = logging.getLogger(__name__)


def _attractions_from_day_plan(day_items: List[dict]) -> List[dict]:
    out = []
    for it in day_items:
        if it.get("type") != "attraction":
            continue
        poi = it.get("poi") or {}
        if poi.get("lat") is not None and poi.get("lng") is not None:
            out.append(it)
    return out


def _haversine_matrix(coords: Sequence[tuple]) -> List[List[float]]:
    n = len(coords)
    m = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            lat1, lng1 = coords[i]
            lat2, lng2 = coords[j]
            km = haversine_km(lat1, lng1, lat2, lng2)
            m[i][j] = max(km / 45.0 * 60, 5)
    return m


def _nearest_neighbor_order(matrix: List[List[float]], start: int = 0) -> List[int]:
    n = len(matrix)
    if n <= 1:
        return list(range(n))
    visited = {start}
    order = [start]
    cur = start
    while len(visited) < n:
        best_j = None
        best_d = float("inf")
        for j in range(n):
            if j in visited:
                continue
            d = matrix[cur][j]
            if d < best_d:
                best_d = d
                best_j = j
        if best_j is None:
            break
        visited.add(best_j)
        order.append(best_j)
        cur = best_j
    return order


def _two_opt(matrix: List[List[float]], order: List[int], max_iter: int = 20) -> List[int]:
    n = len(order)
    if n < 4:
        return order

    def _tour_len(ord_: List[int]) -> float:
        return sum(matrix[ord_[i]][ord_[i + 1]] for i in range(len(ord_) - 1))

    best = order[:]
    best_len = _tour_len(best)
    for _ in range(max_iter):
        improved = False
        for i in range(1, n - 2):
            for j in range(i + 1, n):
                if j - i == 1:
                    continue
                new = best[:i] + best[i:j][::-1] + best[j:]
                new_len = _tour_len(new)
                if new_len + 0.01 < best_len:
                    best, best_len = new, new_len
                    improved = True
        if not improved:
            break
    return best


def optimize_day_attraction_order(
    day_items: List[dict],
    context: Optional[dict] = None,
) -> List[dict]:
    """
    Reorder attraction entries in engine day plan to reduce travel time.
    Preserves non-attraction items (lunch, free_time) — only permutes attractions.
    """
    if not settings.ors_matrix_enabled:
        return day_items

    attrs = _attractions_from_day_plan(day_items)
    if len(attrs) < 3 or len(attrs) > settings.ors_matrix_max_locations:
        return day_items

    coords = [(float(a["poi"]["lat"]), float(a["poi"]["lng"])) for a in attrs]
    ctx = context or {}
    profile = resolve_profile(attrs[0]["poi"], attrs[1]["poi"], ctx)

    matrix: Optional[List[List[float]]] = None
    client = get_ors_client()
    if client.matrix_enabled():
        matrix = client.matrix_durations(coords, profile)
    if matrix is None:
        matrix = _haversine_matrix(coords)

    order = _nearest_neighbor_order(matrix, start=0)
    order = _two_opt(matrix, order)

    old_total = sum(matrix[i][i + 1] for i in range(len(order) - 1))
    # Try different starts
    for start in range(1, len(order)):
        cand = _two_opt(matrix, _nearest_neighbor_order(matrix, start=start))
        cand_total = sum(matrix[cand[i]][cand[i + 1]] for i in range(len(cand) - 1))
        if cand_total < old_total:
            order, old_total = cand, cand_total

    ordered_attrs = [attrs[i] for i in order]
    logger.info(
        "[ORS Matrix] Reordered %d attractions (est. travel %.0f min)",
        len(attrs), old_total,
    )

    out: List[dict] = []
    ai = 0
    for it in day_items:
        if it.get("type") == "attraction" and it in attrs:
            out.append(ordered_attrs[ai])
            ai += 1
        else:
            out.append(it)
    return out
