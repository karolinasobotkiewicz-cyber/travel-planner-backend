"""FIX #360: route defects the client mails that the older gates let through.

The physics checks in `mail_gate_checks` accept a day whose `from` fields all
line up. The client reads the order instead: a visit that happens after the
group already walked away, a car that appears at a POI nobody drove to, a loop
back to a place with nothing in between, and hours of buffer blocks.

Only Kraków / Katowice / Poznań gates use this. Wrocław and Zakopane are not
audited here.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.application.services.plan_service import (
    _fold_place_label, _is_hub_place_label, _place_names_match,
)
from app.domain.models.plan import ItemType
from app.domain.planner.time_utils import time_to_minutes
from app.domain.validators.client_invariants import GENERIC_MEAL, _tv

MEAL_TYPES = (ItemType.LUNCH_BREAK.value, ItemType.DINNER_BREAK.value)
THIN_FREE_MIN = 150
LATE_DINNER_MIN = 20 * 60
MEAL_WAIT_MIN = 40

PREF_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "underground": (
        "guido", "luiza", "sztoln", "podziem", "kopaln", "carboneum",
        "jaskin", "schron", "bunkr", "adit",
    ),
    "active_sport": (
        "gokart", "wspin", "linow", "cybermagi", "bowling", "skate",
        "jump", "rower", "kajak", "fitnes", "trampolin", "saneczk",
    ),
    "water_attractions": (
        "term", "aquapark", "park wodny", "jezior", "malta", "basen",
        "plaza", "kapiel",
    ),
    "local_food_experience": (
        "browar", "muzeum obwarzanka", "rogalowe", "fabryka wodki",
        "pijalnia", "winnic", "czekolad", "serowarn", "targ",
    ),
}


def _stop_name(it: Any) -> Optional[str]:
    """Attraction name, or a named restaurant. A generic meal is not a stop."""
    tv = _tv(it)
    if tv == ItemType.ATTRACTION.value:
        nm = (getattr(it, "name", "") or "").strip()
        return nm or None
    if tv in MEAL_TYPES:
        for s in (getattr(it, "suggestions", None) or [])[:1]:
            nm = (
                (s.get("name") or "") if isinstance(s, dict)
                else (getattr(s, "name", "") or "")
            ).strip()
            if nm:
                return nm
        label = (
            getattr(it, "label", None) or getattr(it, "name", None) or ""
        ).strip()
        if label and _fold_place_label(label) not in GENERIC_MEAL:
            return label
    return None


def _clock(it: Any, field: str) -> Optional[int]:
    raw = getattr(it, field, None) or getattr(it, "time", None)
    if not raw:
        return None
    try:
        return time_to_minutes(raw)
    except Exception:
        return None


def _mode(it: Any) -> str:
    return str(
        getattr(getattr(it, "mode", None), "value", getattr(it, "mode", "")) or ""
    ).lower()


def collect_route_defects(
    *,
    num: int,
    day: Any,
    payload: Dict[str, Any],
    city: str,
) -> List[str]:
    hits: List[str] = []
    items = list(day.items or [])
    tag = f"J{num} D{day.day}"
    window = payload.get("daily_time_window") or {}

    def hub(nm: str) -> bool:
        return bool(nm) and (
            _is_hub_place_label(nm) or _place_names_match(nm, city)
        )

    stops = [nm for nm in (_stop_name(it) for it in items) if nm]
    folded_stops = {_fold_place_label(nm) for nm in stops}

    # 1. A visit that happens after the group already left for another stop.
    for idx, it in enumerate(items):
        if _tv(it) != ItemType.ATTRACTION.value:
            continue
        name = (getattr(it, "name", "") or "").strip()
        if not name:
            continue
        inbound = None
        for j in range(idx - 1, -1, -1):
            if _tv(items[j]) != ItemType.TRANSIT.value:
                continue
            if _place_names_match(
                (getattr(items[j], "to_location", "") or ""), name,
            ):
                inbound = j
                break
        if inbound is None:
            continue
        blockers = [
            _stop_name(items[k]) for k in range(inbound + 1, idx)
        ]
        blockers = [
            b for b in blockers if b and not _place_names_match(b, name)
        ]
        if blockers:
            hits.append(
                f"{tag} [visit_after_leaving] {name} zwiedzane po postoju "
                f"{blockers[-1]}"
            )

    # 2. A car that appears at a place nobody drove to.
    car_at: Optional[str] = None
    for it in items:
        if _tv(it) != ItemType.TRANSIT.value:
            continue
        frm = (getattr(it, "from_location", "") or "").strip()
        to = (getattr(it, "to_location", "") or "").strip()
        if "car" not in _mode(it):
            continue
        if not hub(frm) and (car_at is None or not _place_names_match(frm, car_at)):
            hits.append(f"{tag} [ghost_car] auto rusza z '{frm}' bez dojazdu")
        if to:
            car_at = to

    # 3. A loop that leaves a place and comes back with nothing in between,
    #    and a waypoint the plan never actually visits.
    hops = [
        (i, it) for i, it in enumerate(items)
        if _tv(it) == ItemType.TRANSIT.value
    ]
    for pos, (idx, it) in enumerate(hops):
        to = (getattr(it, "to_location", "") or "").strip()
        if not to or hub(to):
            continue
        folded = _fold_place_label(to)
        visited = folded in folded_stops or any(
            len(s) >= 8 and (folded in s or s in folded) for s in folded_stops
        )
        if visited:
            continue
        if pos + 1 < len(hops):
            nxt_idx, nxt = hops[pos + 1]
            nxt_to = (getattr(nxt, "to_location", "") or "").strip()
            frm = (getattr(it, "from_location", "") or "").strip()
            between = [
                _stop_name(items[k]) for k in range(idx + 1, nxt_idx)
            ]
            if not any(between) and nxt_to and _place_names_match(nxt_to, frm):
                hits.append(
                    f"{tag} [loop_no_stop] {frm} → {to} → {frm} bez postoju"
                )
                continue
        hits.append(f"{tag} [waypoint_only] {to} tylko przejazdem")

    # 4. Hours of buffer instead of a plan.
    free_min = 0
    n_attr = 0
    for it in items:
        if _tv(it) == ItemType.FREE_TIME.value:
            try:
                free_min += int(getattr(it, "duration_min", 0) or 0)
            except (TypeError, ValueError):
                pass
        elif _tv(it) == ItemType.ATTRACTION.value:
            n_attr += 1
    if free_min >= THIN_FREE_MIN:
        hits.append(f"{tag} [thin_day] {free_min} min wolnego czasu")
    try:
        win_len = time_to_minutes(window.get("end") or "20:00") - time_to_minutes(
            window.get("start") or "09:00"
        )
    except Exception:
        win_len = 0
    if n_attr <= 1 and win_len >= 6 * 60:
        hits.append(f"{tag} [thin_day] {n_attr} atrakcji w oknie {win_len} min")

    # 5. Meals: the guest must already be there, and not wait for an hour.
    for idx, it in enumerate(items):
        if _tv(it) not in MEAL_TYPES:
            continue
        name = _stop_name(it)
        st = _clock(it, "start_time")
        if not name:
            continue
        prev_stop = None
        for j in range(idx - 1, -1, -1):
            got = _stop_name(items[j])
            if got:
                prev_stop = got
                break
        inbound_end = None
        for j in range(idx - 1, -1, -1):
            if _tv(items[j]) != ItemType.TRANSIT.value:
                continue
            if _place_names_match(
                (getattr(items[j], "to_location", "") or ""), name,
            ):
                inbound_end = _clock(items[j], "end_time")
                break
        here = prev_stop is not None and _place_names_match(prev_stop, name)
        if not here and inbound_end is None:
            hits.append(f"{tag} [meal_no_hop] {name} bez dojścia")
        if inbound_end is not None and st is not None and st - inbound_end >= MEAL_WAIT_MIN:
            hits.append(
                f"{tag} [meal_wait] {st - inbound_end} min czekania na {name}"
            )
        if (
            _tv(it) == ItemType.DINNER_BREAK.value
            and st is not None
            and st >= LATE_DINNER_MIN
        ):
            hits.append(f"{tag} [late_dinner] {getattr(it, 'start_time', '')}")

    return hits


def collect_trip_defects(
    *,
    num: int,
    plan: Any,
    payload: Dict[str, Any],
) -> List[str]:
    """A preference the whole trip never delivers."""
    hits: List[str] = []
    prefs = [str(p).lower() for p in (payload.get("preferences") or [])]
    names = " ".join(
        _fold_place_label(getattr(it, "name", "") or "")
        for day in plan.days
        for it in (day.items or [])
        if _tv(it) == ItemType.ATTRACTION.value
    )
    for key, words in PREF_KEYWORDS.items():
        if key not in prefs:
            continue
        if not any(w in names for w in words):
            hits.append(f"J{num} [pref_missing] {key}")
    return hits
