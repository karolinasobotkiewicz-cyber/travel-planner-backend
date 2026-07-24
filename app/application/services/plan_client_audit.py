"""Shared plan quality checks for client JSON regression tests (FIX #239)."""
from __future__ import annotations

import math
from typing import Any, List, Sequence, Tuple

from app.domain.models.plan import ItemType


def _type_val(item: Any) -> str:
    t = getattr(item, "type", None)
    if hasattr(t, "value"):
        return str(t.value)
    return str(t or "")


def time_min(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _sorted_timed(items: Sequence[Any]) -> List[Any]:
    out = [it for it in items if getattr(it, "start_time", None) and getattr(it, "end_time", None)]
    return sorted(out, key=lambda x: time_min(x.start_time))


def audit_transit_routing(items: Sequence[Any]) -> List[str]:
    issues: List[str] = []
    for it in items:
        if _type_val(it) != ItemType.TRANSIT.value:
            continue
        src = getattr(it, "routing_source", None)
        mode = str(getattr(it, "mode", "") or "").lower()
        is_walk = "walk" in mode
        if src is None or src == "":
            issues.append("transit routing_source null")
        elif src == "haversine" and not is_walk:
            issues.append(f"transit car/public haversine ({getattr(it, 'from_location', '')}->{getattr(it, 'to_location', '')})")
        frm = getattr(it, "from_location", "") or ""
        to = getattr(it, "to_location", "") or ""
        lat_ok = getattr(it, "geometry", None) or getattr(it, "geometry_latlng", None)
        if not lat_ok and frm and to and frm not in ("Zakopane (Hotel)",) and "hotel" not in frm.lower():
            issues.append(f"transit missing geometry {frm}->{to}")
    return issues


def _attr_coords(item: Any) -> Tuple[float | None, float | None]:
    lat = getattr(item, "lat", None)
    lng = getattr(item, "lng", None)
    if lat is not None and lng is not None:
        return float(lat), float(lng)
    return None, None


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
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


def audit_missing_transits(items: Sequence[Any], *, min_km: float = 0.35, max_gap_min: int = 25) -> List[str]:
    """Between consecutive attractions: need transit or small gap if far apart."""
    attrs = [it for it in items if _type_val(it) == ItemType.ATTRACTION.value]
    issues: List[str] = []
    for i in range(len(attrs) - 1):
        a, b = attrs[i], attrs[i + 1]
        if not a.end_time or not b.start_time:
            continue
        gap = time_min(b.start_time) - time_min(a.end_time)
        la, ln = _attr_coords(a)
        lb, lnb = _attr_coords(b)
        if la is None or lb is None:
            continue
        dist = _haversine_km(la, ln, lb, lnb)
        if dist < min_km:
            continue
        # any transit between them in timeline order?
        a_end = time_min(a.end_time)
        b_start = time_min(b.start_time)
        has_transit = any(
            _type_val(it) == ItemType.TRANSIT.value
            and getattr(it, "start_time", None)
            and a_end <= time_min(it.start_time) < b_start
            for it in items
        )
        if not has_transit and gap > max_gap_min:
            issues.append(
                f"no transit {getattr(a, 'name', '?')}->{getattr(b, 'name', '?')} "
                f"({dist:.1f}km, {gap}min gap)"
            )
    return issues


def audit_free_time(items: Sequence[Any], *, max_total: int = 45, max_block: int = 35) -> List[str]:
    issues: List[str] = []
    total = 0
    for it in items:
        if _type_val(it) != ItemType.FREE_TIME.value:
            continue
        dur = int(getattr(it, "duration_min", 0) or 0)
        total += dur
        if dur > max_block:
            issues.append(f"free_time block {dur}min")
    if total > max_total:
        issues.append(f"free_time total {total}min")
    return issues


def audit_large_idle_gaps(items: Sequence[Any], *, max_gap_min: int = 90) -> List[str]:
    """Idle time between consecutive scheduled items (not explained by meals/transit duration)."""
    issues: List[str] = []
    ordered = _sorted_timed(items)
    skip_types = {ItemType.DAY_START.value, ItemType.DAY_END.value}
    for i in range(len(ordered) - 1):
        cur, nxt = ordered[i], ordered[i + 1]
        if _type_val(cur) in skip_types or _type_val(nxt) in skip_types:
            continue
        gap = time_min(nxt.start_time) - time_min(cur.end_time)
        if gap <= max_gap_min:
            continue
        # FIX #240: bufor przed kolacją po 17:30 jest akceptowalny do 150–300 min
        if _type_val(nxt) == ItemType.DINNER_BREAK.value:
            _dinner_ok = time_min(nxt.start_time) >= 17 * 60 + 30
            _buf = 300 if _dinner_ok else 150
            if _dinner_ok and gap <= _buf:
                continue
        # FIX #240: lunch buffer do 180 min
        if _type_val(nxt) == ItemType.LUNCH_BREAK.value and gap <= 180:
            continue
        if _type_val(cur) == ItemType.FREE_TIME.value or _type_val(nxt) == ItemType.FREE_TIME.value:
            issues.append(f"idle gap {gap}min around free_time")
        elif _type_val(cur) == ItemType.ATTRACTION.value and _type_val(nxt) == ItemType.ATTRACTION.value:
            issues.append(f"idle gap {gap}min between attractions")
        elif _type_val(cur) == ItemType.ATTRACTION.value and _type_val(nxt) in (
            ItemType.DINNER_BREAK.value,
            ItemType.LUNCH_BREAK.value,
        ):
            if not (
                _type_val(nxt) == ItemType.DINNER_BREAK.value
                and time_min(nxt.start_time) >= 17 * 60 + 30
                and gap <= 300
            ):
                issues.append(f"idle gap {gap}min before meal")
    return issues


def audit_day(day, *, day_label: str = "") -> List[str]:
    items = day.items or []
    prefix = f"{day_label}day{day.day}: " if day_label or getattr(day, "day", None) else ""
    issues: List[str] = []
    for fn in (
        audit_transit_routing,
        audit_missing_transits,
        audit_free_time,
        audit_large_idle_gaps,
    ):
        for msg in fn(items):
            issues.append(prefix + msg)
    return issues
