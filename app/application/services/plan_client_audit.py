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


def _norm_name(s: str) -> str:
    s = (s or "").lower()
    for a, b in (("ł", "l"), ("ó", "o"), ("ś", "s"), ("ź", "z"), ("ż", "z"), ("ę", "e"), ("ą", "a"), ("ć", "c"), ("ń", "n")):
        s = s.replace(a, b)
    return s


def _attr_names_set(items: Sequence[Any]) -> set[str]:
    names: set[str] = set()
    for it in items:
        if _type_val(it) == ItemType.ATTRACTION.value:
            n = getattr(it, "name", "") or ""
            if n:
                names.add(n)
                names.add(_norm_name(n))
    return names


def audit_timeline_overlaps(items: Sequence[Any]) -> List[str]:
    issues: List[str] = []
    ordered = _sorted_timed(items)
    for i in range(len(ordered) - 1):
        cur, nxt = ordered[i], ordered[i + 1]
        if time_min(cur.end_time) > time_min(nxt.start_time):
            issues.append(
                f"overlap {getattr(cur, 'name', _type_val(cur))} "
                f"({cur.start_time}-{cur.end_time}) vs "
                f"{getattr(nxt, 'name', _type_val(nxt))} ({nxt.start_time})"
            )
    return issues


def audit_before_day_start(items: Sequence[Any], day_start: str) -> List[str]:
    issues: List[str] = []
    if not day_start:
        return issues
    floor = time_min(day_start)
    for it in items:
        if _type_val(it) not in (
            ItemType.ATTRACTION.value,
            ItemType.LUNCH_BREAK.value,
            ItemType.DINNER_BREAK.value,
            ItemType.TRANSIT.value,
            ItemType.FREE_TIME.value,
        ):
            continue
        st = getattr(it, "start_time", None)
        if st and time_min(st) < floor:
            issues.append(
                f"starts before day_start ({day_start}): "
                f"{getattr(it, 'name', _type_val(it))} at {st}"
            )
    return issues


def audit_orphan_transits(items: Sequence[Any]) -> List[str]:
    issues: List[str] = []
    names = _attr_names_set(items)
    # FIX #251: meal restaurants are valid transit endpoints.
    for it in items:
        if _type_val(it) not in (
            ItemType.LUNCH_BREAK.value,
            ItemType.DINNER_BREAK.value,
        ):
            continue
        for sug in (getattr(it, "suggestions", None) or [])[:1]:
            rn = (getattr(sug, "name", None) or "").strip()
            if rn:
                names.add(rn)
                names.add(_norm_name(rn))

    def _matches(name: str) -> bool:
        if not name:
            return True
        nn = _norm_name(name)
        if name in names or nn in names:
            return True
        return any(nn in _norm_name(n) or _norm_name(n) in nn for n in names if n)

    for it in items:
        if _type_val(it) != ItemType.TRANSIT.value:
            continue
        fr = (getattr(it, "from_location", "") or "").strip()
        to = (getattr(it, "to_location", "") or "").strip()
        if to and not _matches(to):
            issues.append(f"orphan transit to {to!r}")
        if fr and not to and not _matches(fr):
            issues.append(f"orphan transit from {fr!r}")
    return issues


def audit_budget_exceeded(items: Sequence[Any], daily_limit: float | int | None) -> List[str]:
    if not daily_limit or float(daily_limit) <= 0:
        return []
    total = 0.0
    for it in items:
        c = getattr(it, "cost_estimate", None) or getattr(it, "total_cost", None) or 0
        try:
            total += float(c)
        except (TypeError, ValueError):
            pass
    if total > float(daily_limit):
        return [f"budget exceeded {int(total)} > {int(daily_limit)} PLN"]
    return []


def audit_day(
    day,
    *,
    day_label: str = "",
    day_start: str = "",
    daily_limit: float | int | None = None,
) -> List[str]:
    items = day.items or []
    prefix = f"{day_label}day{day.day}: " if day_label or getattr(day, "day", None) else ""
    issues: List[str] = []
    checks = [
        audit_timeline_overlaps,
        audit_before_day_start,
        audit_orphan_transits,
        audit_transit_routing,
        audit_missing_transits,
        audit_free_time,
        audit_large_idle_gaps,
    ]
    for fn in checks:
        if fn is audit_before_day_start:
            msgs = fn(items, day_start)
        else:
            msgs = fn(items)
        for msg in msgs:
            issues.append(prefix + msg)
    for msg in audit_budget_exceeded(items, daily_limit):
        issues.append(prefix + msg)
    return issues
