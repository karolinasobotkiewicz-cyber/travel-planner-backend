"""FIX #317: trip-level invariants the client actually reads.

Not a second planner. Call after the last polish pass (or from tests) on a
finished DayPlan list. Each defect is a class from the Wrocław JSON reports,
not a pair of POI names.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.domain.models.plan import ItemType
from app.domain.planner.time_utils import time_to_minutes
from app.infrastructure.routing.haversine import haversine_km


GENERIC_MEAL = (
    "restauracja", "restauracja (obiad)", "restauracja (kolacja)",
    "lunch", "kolacja", "obiad", "posiłek", "posilek",
    "przerwa regeneracyjna", "lunch / przerwa regeneracyjna",
)

# FIX #324: the client reads a day, not a defect list. Every marker below
# comes from one of her Wrocław remarks.
SLIVER_MAX_MIN = 12
SLIVER_RUN = 3
LONG_FREE_TIME_MIN = 100
SHORT_DAY_END_MIN = 15 * 60
SHORT_DAY_WINDOW_MIN = 18 * 60
CAR_MAX_KMH = 60.0
CAR_HIGHWAY_KM = 15.0
CAR_HIGHWAY_MAX_KMH = 95.0

_ADRENALINE_MARKERS = (
    "bungee", "skok na", "paintball", "quad", "gokart", "go-kart", "kart",
    "adrenalin", "tyrolka", "zipline", "via ferrata", "wspinacz",
    "park linowy", "strzelnic", "motocross", "wakepark", "surf",
)
_CALM_STYLES = frozenset({"relax", "relaks", "slow", "wypoczynkowy"})
_CALM_GROUPS = frozenset({"seniors", "seniorzy", "senior"})


@dataclass(frozen=True)
class Defect:
    code: str
    day: int
    message: str
    meta: Dict[str, Any] = field(default_factory=dict)


def _tv(it: Any) -> str:
    t = getattr(it, "type", None)
    if hasattr(t, "value"):
        return str(t.value)
    return str(t or "")


def _is_attr(it: Any) -> bool:
    return _tv(it) == ItemType.ATTRACTION.value


def _is_transit(it: Any) -> bool:
    return _tv(it) == ItemType.TRANSIT.value


def _is_meal(it: Any) -> bool:
    return _tv(it) in (
        ItemType.LUNCH_BREAK.value, ItemType.DINNER_BREAK.value,
    )


def _is_ft(it: Any) -> bool:
    return _tv(it) == ItemType.FREE_TIME.value


def _clock(it: Any) -> Tuple[Optional[int], Optional[int]]:
    st = getattr(it, "start_time", None) or getattr(it, "time", None)
    en = getattr(it, "end_time", None)
    if _tv(it) == ItemType.DAY_END.value and not en:
        en = st
    if _tv(it) == ItemType.DAY_START.value:
        en = st
    try:
        sm = time_to_minutes(st) if st else None
    except Exception:
        sm = None
    try:
        em = time_to_minutes(en) if en else None
    except Exception:
        em = None
    return sm, em


def _fold(name: Any) -> str:
    s = str(name or "").strip().lower()
    for a, b in (
        ("ł", "l"), ("ó", "o"), ("ś", "s"), ("ź", "z"), ("ż", "z"),
        ("ę", "e"), ("ą", "a"), ("ć", "c"), ("ń", "n"),
    ):
        s = s.replace(a, b)
    return " ".join(s.split())


def _names_match(a: str, b: str) -> bool:
    aa, bb = _fold(a), _fold(b)
    if not aa or not bb:
        return False
    if aa == bb:
        return True
    shorter, longer = (aa, bb) if len(aa) <= len(bb) else (bb, aa)
    if len(shorter) >= 7 and shorter in longer:
        return True
    return False


def _meal_name(it: Any) -> Optional[str]:
    for s in (getattr(it, "suggestions", None) or [])[:1]:
        if isinstance(s, dict):
            nm = (s.get("name") or "").strip()
        else:
            nm = (getattr(s, "name", "") or "").strip()
        if nm:
            return nm
    label = (getattr(it, "label", None) or getattr(it, "name", None) or "").strip()
    if label and _fold(label) not in GENERIC_MEAL:
        return label
    return None


def _stop_name(it: Any) -> Optional[str]:
    if _is_attr(it):
        nm = (getattr(it, "name", "") or "").strip()
        return nm or None
    if _is_meal(it):
        return _meal_name(it)
    return None


def _coords(it: Any) -> Optional[Tuple[float, float]]:
    lat = getattr(it, "lat", None)
    lng = getattr(it, "lng", None)
    if lat is None or lng is None:
        sug = (getattr(it, "suggestions", None) or [None])[0]
        if sug is not None:
            if isinstance(sug, dict):
                lat, lng = sug.get("lat"), sug.get("lng")
            else:
                lat = getattr(sug, "lat", None)
                lng = getattr(sug, "lng", None)
    try:
        if lat is None or lng is None:
            return None
        return float(lat), float(lng)
    except (TypeError, ValueError):
        return None


def _mode(it: Any) -> str:
    m = getattr(it, "mode", None)
    return str(getattr(m, "value", m) or "").lower()


def _day_num(day: Any, fallback: int) -> int:
    try:
        return int(getattr(day, "day", None) or fallback)
    except Exception:
        return fallback


def _day_end_marker(items: Sequence[Any]) -> Optional[int]:
    for it in items:
        if _tv(it) == ItemType.DAY_END.value:
            sm, em = _clock(it)
            return em or sm
    return None


def _day_start_marker(items: Sequence[Any], context: Optional[Dict[str, Any]]) -> int:
    for it in items:
        if _tv(it) == ItemType.DAY_START.value:
            sm, _ = _clock(it)
            if sm is not None:
                return sm
    try:
        return time_to_minutes((context or {}).get("day_start") or "09:00")
    except Exception:
        return 9 * 60


def _sort_items(items: Sequence[Any]) -> List[Any]:
    def key(it: Any):
        sm, _ = _clock(it)
        return sm if sm is not None else 10**9
    return sorted(list(items), key=key)


def _region(name: str) -> Optional[str]:
    from app.application.services.plan_service import _timeline_satellite_kind
    try:
        return _timeline_satellite_kind(name)
    except Exception:
        return None


def audit_day(
    items: Sequence[Any],
    *,
    day: int = 1,
    context: Optional[Dict[str, Any]] = None,
    trip_days: int = 1,
) -> List[Defect]:
    """Return every invariant break on one finished day."""
    if not items:
        return [Defect("empty_day", day, f"Dzień {day}: brak itemów")]
    ordered = _sort_items(items)
    defects: List[Defect] = []
    marker_end = _day_end_marker(ordered)
    marker_start = _day_start_marker(ordered, context)

    # --- after_day_end ---
    if marker_end is not None:
        for it in ordered:
            if _tv(it) in (ItemType.DAY_START.value, ItemType.DAY_END.value):
                continue
            sm, _ = _clock(it)
            if sm is not None and sm >= marker_end:
                defects.append(Defect(
                    "after_day_end", day,
                    f"Dzień {day}: {_tv(it)} startuje po day_end "
                    f"({_fmt(sm)} ≥ {_fmt(marker_end)})",
                    {"start": sm},
                ))

    # --- overlap ---
    timed: List[Tuple[Any, int, int]] = []
    for it in ordered:
        if _tv(it) in (ItemType.DAY_START.value, ItemType.DAY_END.value):
            continue
        sm, em = _clock(it)
        if sm is None or em is None or em <= sm:
            continue
        timed.append((it, sm, em))
    for i, (a, as_, ae) in enumerate(timed):
        for b, bs, be in timed[i + 1:]:
            if ae <= bs or be <= as_:
                continue
            defects.append(Defect(
                "overlap", day,
                f"Dzień {day}: nakładka {_tv(a)} {_fmt(as_)}–{_fmt(ae)} × "
                f"{_tv(b)} {_fmt(bs)}–{_fmt(be)}",
            ))

    # --- anonymous_gap (between covered spans, inside the marker window) ---
    win_end = marker_end
    if win_end is None:
        try:
            win_end = time_to_minutes((context or {}).get("day_end") or "20:00")
        except Exception:
            win_end = 20 * 60
    spans: List[Tuple[int, int]] = []
    for it in ordered:
        if _tv(it) in (ItemType.DAY_START.value, ItemType.DAY_END.value):
            continue
        sm, em = _clock(it)
        if sm is None or em is None or em <= sm:
            continue
        spans.append((sm, em))
    spans.sort()
    cursor = marker_start
    for s, e in spans:
        if s > cursor + 9:
            defects.append(Defect(
                "anonymous_gap", day,
                f"Dzień {day}: {_fmt(cursor)}–{_fmt(min(s, win_end))} "
                f"({min(s, win_end) - cursor} min) bez bloku",
                {"start": cursor, "end": min(s, win_end)},
            ))
        cursor = max(cursor, e)
        if cursor >= win_end:
            break
    if cursor + 9 < win_end:
        # Tail before day_end marker is a hole the client reads.
        defects.append(Defect(
            "anonymous_gap", day,
            f"Dzień {day}: {_fmt(cursor)}–{_fmt(win_end)} "
            f"({win_end - cursor} min) bez bloku przed day_end",
            {"start": cursor, "end": win_end},
        ))

    # --- hops between occupied stops ---
    stops: List[Tuple[int, Any, str]] = []
    for idx, it in enumerate(ordered):
        nm = _stop_name(it)
        if nm:
            stops.append((idx, it, nm))
    for (ia, a, na), (ib, b, nb) in zip(stops, stops[1:]):
        between = ordered[ia + 1:ib]
        hops = [x for x in between if _is_transit(x)]
        hop_hits = False
        for h in hops:
            to = (getattr(h, "to_location", "") or "").strip()
            if to and _names_match(to, nb):
                hop_hits = True
                break
            if not to and hops:
                hop_hits = True
        as_, ae = _clock(a)
        bs, _be = _clock(b)
        pt_a, pt_b = _coords(a), _coords(b)
        km = None
        if pt_a and pt_b:
            km = haversine_km(pt_a[0], pt_a[1], pt_b[0], pt_b[1])
        courtyard = km is not None and km < 0.20
        clock_teleport = (
            ae is not None and bs is not None and abs(bs - ae) <= 2
        )
        if courtyard:
            continue
        if hop_hits:
            continue
        # FIX #324: a restaurant without coords is still a place the guest
        # has to reach. Client D3: free_time 11:00–11:30 then lunch in
        # Żórawina, and only *after* lunch a 25 min hop back to Wrocław.
        gap_ab = (bs - ae) if (ae is not None and bs is not None) else None
        if km is None and not clock_teleport and hops:
            # A hop exists but points elsewhere — the retarget pass owns it.
            continue
        defects.append(Defect(
            "missing_hop", day,
            f"Dzień {day}: brak dojazdu {na} → {nb}"
            + (
                f" ({km:.2f} km)" if km is not None
                else f" (brak współrzędnych, przerwa {gap_ab} min)"
                if gap_ab is not None else " (brak współrzędnych)"
            ),
            {"from": na, "to": nb, "km": km},
        ))

    # leading hop: first stop glued to day_start
    if stops:
        _i0, first, n0 = stops[0]
        fs, _ = _clock(first)
        pt = _coords(first)
        leading = [
            x for x in ordered[:_i0] if _is_transit(x)
        ]
        has_lead = False
        for h in leading:
            to = (getattr(h, "to_location", "") or "").strip()
            if not to or _names_match(to, n0):
                has_lead = True
                break
        # FIX #324: a technical buffer is not a transit. The client saw
        # 10 min (ZOO 09:10), 15 min (Ogród Botaniczny 09:45) and 60 min
        # (Muzeum Przyrodnicze 10:00) of padding instead of "Wrocław → X".
        folded = _fold(n0)
        rynek_hub = (
            "rynek" in folded
            and "olaw" not in folded
            and "zabkow" not in folded
        )
        gap0 = (fs - marker_start) if fs is not None else None
        glued_rynek = rynek_hub and gap0 is not None and gap0 <= 5
        if fs is not None and not has_lead and not glued_rynek:
            defects.append(Defect(
                "missing_hop", day,
                f"Dzień {day}: {n0} startuje o {_fmt(fs)} bez dojazdu "
                f"z punktu startu (bufor {gap0} min nie zastępuje przejazdu)",
                {"to": n0, "km": None, "buffer_min": gap0},
            ))

    # --- honest_leg / urban_car / from_mismatch ---
    prev_stop: Optional[str] = None
    for i, it in enumerate(ordered):
        if _stop_name(it):
            if _is_transit(it):
                pass
            else:
                prev_stop = _stop_name(it)
        if not _is_transit(it):
            continue
        frm = (getattr(it, "from_location", "") or "").strip()
        to = (getattr(it, "to_location", "") or "").strip()
        sm, em = _clock(it)
        try:
            km = float(getattr(it, "distance_km", None) or 0)
        except (TypeError, ValueError):
            km = 0.0
        dur = int(getattr(it, "duration_min", 0) or 0)
        if sm is not None and em is not None and em > sm:
            clock = em - sm
        else:
            clock = dur
        pace = min(clock, dur) if clock and dur else (clock or dur)
        is_walk = "walk" in _mode(it) or "foot" in _mode(it)
        is_car = "car" in _mode(it)

        if prev_stop and frm and not _names_match(frm, prev_stop):
            if _fold(frm) not in GENERIC_MEAL and _fold(prev_stop) not in GENERIC_MEAL:
                defects.append(Defect(
                    "from_mismatch", day,
                    f"Dzień {day}: transit from={frm!r} ale ostatni postój to {prev_stop!r}",
                    {"from": frm, "last": prev_stop, "to": to},
                ))
        if _fold(frm) in {
            "restauracja (obiad)", "restauracja (kolacja)", "restauracja",
        } and prev_stop and _fold(prev_stop) not in GENERIC_MEAL:
            defects.append(Defect(
                "meal_identity", day,
                f"Dzień {day}: hop z generycznego {frm!r} po {prev_stop!r}",
                {"from": frm, "last": prev_stop},
            ))

        if is_walk and km >= 0.5 and pace <= 2:
            defects.append(Defect(
                "dishonest_leg", day,
                f"Dzień {day}: {km:.3f} km pieszo w {pace} min ({frm} → {to})",
                {"km": km, "min": pace},
            ))
        elif is_walk and km >= 0.7 and pace > 0 and (km / (pace / 60.0)) > 8.0:
            defects.append(Defect(
                "dishonest_leg", day,
                f"Dzień {day}: {km:.3f} km pieszo w {pace} min ({frm} → {to})",
                {"km": km, "min": pace},
            ))
        if is_car and 0 < km < 0.80:
            defects.append(Defect(
                "urban_car", day,
                f"Dzień {day}: samochód na {km:.2f} km ({frm} → {to})",
                {"km": km},
            ))
        # FIX #324: 5.95 km by car in 4 min is 89 km/h through Wrocław.
        # A 65 km run to Niemcza at 65 km/h is just a road.
        if is_car and km >= 1.0 and pace and pace > 0:
            kmh = km / (pace / 60.0)
            ceiling = (
                CAR_HIGHWAY_MAX_KMH if km >= CAR_HIGHWAY_KM else CAR_MAX_KMH
            )
            if kmh > ceiling:
                defects.append(Defect(
                    "dishonest_leg", day,
                    f"Dzień {day}: {km:.2f} km autem w {pace} min "
                    f"({kmh:.0f} km/h, {frm} → {to})",
                    {"km": km, "min": pace, "kmh": kmh},
                ))
        if to:
            prev_stop = to

    # --- meal identity (label vs suggestion) ---
    for it in ordered:
        if not _is_meal(it):
            continue
        sug = _meal_name(it)
        label = (getattr(it, "label", None) or "").strip()
        loc = (getattr(it, "location_context", None) or "").strip()
        if not sug:
            continue
        if label and _fold(label) not in GENERIC_MEAL and not _names_match(label, sug):
            defects.append(Defect(
                "meal_identity", day,
                f"Dzień {day}: lunch/kolacja label={label!r} ≠ {sug!r}",
                {"label": label, "suggestion": sug},
            ))
        if loc and _fold(loc) not in GENERIC_MEAL and "centrum" not in _fold(loc):
            if not _names_match(loc, sug) and "park rozrywki" in _fold(loc):
                defects.append(Defect(
                    "meal_identity", day,
                    f"Dzień {day}: location_context={loc!r} przy posiłku {sug!r}",
                    {"location_context": loc, "suggestion": sug},
                ))

    # --- mixed satellite regions ---
    kinds = set()
    for it in ordered:
        if not _is_attr(it):
            continue
        k = _region(getattr(it, "name", "") or "")
        if k:
            kinds.add(k)
    if len(kinds) >= 2:
        defects.append(Defect(
            "mixed_regions", day,
            f"Dzień {day}: dwa regiony satelitarne w jednym dniu ({sorted(kinds)})",
            {"regions": sorted(kinds)},
        ))

    # --- dangling_hop: a ride that arrives nowhere ---
    # Client J1 D2: 18:50 Ogród Botaniczny → Pierogarnia Ze Smakiem, arrives
    # 19:00 and the day just ends. The kolacja itself is missing.
    for idx, it in enumerate(ordered):
        if not _is_transit(it):
            continue
        if any(_stop_name(x) for x in ordered[idx + 1:]):
            continue
        to = (getattr(it, "to_location", "") or "").strip()
        _, em = _clock(it)
        defects.append(Defect(
            "dangling_hop", day,
            f"Dzień {day}: przejazd do {to or '?'} kończy się o "
            f"{_fmt(em) if em is not None else '?'} i nic po nim nie ma",
            {"to": to},
        ))
        break

    # --- fragmented: a wall of 2–10 min technical slivers ---
    # Client J1 D2: 2 min walk, 10 min free time, 4 min of nothing, lunch,
    # 10 min, hop, 10 min. On the front end it reads as noise.
    segments: List[Tuple[int, int, str]] = []
    prev_end: Optional[int] = None
    for it in ordered:
        if _tv(it) in (ItemType.DAY_START.value, ItemType.DAY_END.value):
            continue
        sm, em = _clock(it)
        if sm is None or em is None:
            continue
        if prev_end is not None and 0 < sm - prev_end:
            segments.append((prev_end, sm, "gap"))
        segments.append((sm, em, _tv(it)))
        prev_end = max(prev_end or em, em)
    run = 0
    run_start: Optional[int] = None
    for s, e, kind in segments:
        span = e - s
        if 0 < span <= SLIVER_MAX_MIN:
            run += 1
            if run_start is None:
                run_start = s
            if run >= SLIVER_RUN:
                defects.append(Defect(
                    "fragmented", day,
                    f"Dzień {day}: {run} drobnych bloków pod rząd od "
                    f"{_fmt(run_start)} do {_fmt(e)} (techniczne mini-przerwy)",
                    {"start": run_start, "end": e, "count": run},
                ))
                run = 0
                run_start = None
        else:
            run = 0
            run_start = None

    # --- long_free_time: 155 min of "Popołudniowa przerwa" is a hole ---
    for it in ordered:
        if not _is_ft(it):
            continue
        dur = int(getattr(it, "duration_min", 0) or 0)
        if dur < LONG_FREE_TIME_MIN:
            continue
        sm, em = _clock(it)
        defects.append(Defect(
            "long_free_time", day,
            f"Dzień {day}: free_time {dur} min "
            f"({_fmt(sm) if sm is not None else '?'}–"
            f"{_fmt(em) if em is not None else '?'})",
            {"minutes": dur},
        ))

    # --- short_day: 12:20 close on a window that runs to 20:00 ---
    content_end: Optional[int] = None
    for it in ordered:
        if not (_is_attr(it) or _is_meal(it)):
            continue
        _, em = _clock(it)
        if em is not None:
            content_end = max(content_end or em, em)
    raw_window = (context or {}).get("day_end")
    try:
        window_end = time_to_minutes(raw_window) if raw_window else None
    except Exception:
        window_end = None
    if (
        content_end is not None
        and window_end is not None
        and window_end >= SHORT_DAY_WINDOW_MIN
        and content_end < SHORT_DAY_END_MIN
    ):
        defects.append(Defect(
            "short_day", day,
            f"Dzień {day}: ostatni punkt kończy się o {_fmt(content_end)} "
            f"przy oknie do {_fmt(window_end)}",
            {"content_end": content_end, "window_end": window_end},
        ))

    # --- no_return: satellite day that never drives back ---
    city = str((context or {}).get("requested_city") or "").strip()
    last_sat = None
    for idx, it in enumerate(ordered):
        if _is_attr(it) and _region(getattr(it, "name", "") or ""):
            last_sat = (idx, (getattr(it, "name", "") or "").strip())
    if last_sat and city:
        idx, sat_name = last_sat
        returned = False
        for x in ordered[idx + 1:]:
            if _is_transit(x):
                to = (getattr(x, "to_location", "") or "").strip()
                if to and (
                    _names_match(to, city) or "centrum" in _fold(to)
                ):
                    returned = True
                    break
            elif _stop_name(x) and not _region(_stop_name(x) or ""):
                returned = True
                break
        if not returned:
            defects.append(Defect(
                "no_return", day,
                f"Dzień {day}: brak powrotu do {city} po {sat_name}",
                {"satellite": sat_name, "city": city},
            ))

    # --- profile_conflict: Bungee for a solo relax / nature quiz ---
    style = _fold((context or {}).get("travel_style") or "")
    group = _fold((context or {}).get("group_type") or "")
    if style in _CALM_STYLES or group in _CALM_GROUPS:
        for it in ordered:
            if not _is_attr(it):
                continue
            nm = (getattr(it, "name", "") or "").strip()
            folded_nm = _fold(nm)
            if any(m in folded_nm for m in _ADRENALINE_MARKERS):
                defects.append(Defect(
                    "profile_conflict", day,
                    f"Dzień {day}: {nm} przy profilu "
                    f"{style or group!r} (adrenalina wbrew quizowi)",
                    {"name": nm, "style": style, "group": group},
                ))

    # --- empty_day ---
    n_attr = sum(1 for it in ordered if _is_attr(it))
    ft_min = sum(
        int(getattr(it, "duration_min", 0) or 0)
        for it in ordered if _is_ft(it)
    )
    if n_attr == 0:
        defects.append(Defect(
            "empty_day", day,
            f"Dzień {day}: 0 atrakcji, {ft_min} min free_time"
            + (f" (wyjazd {trip_days} dni)" if trip_days else ""),
            {"free_time_min": ft_min, "trip_days": trip_days},
        ))

    return defects


def audit_plan(
    days: Iterable[Any],
    *,
    context: Optional[Dict[str, Any]] = None,
) -> List[Defect]:
    days_l = list(days or [])
    n = len(days_l)
    out: List[Defect] = []
    for i, day in enumerate(days_l, start=1):
        items = getattr(day, "items", None) or []
        out.extend(audit_day(
            items,
            day=_day_num(day, i),
            context=context,
            trip_days=n,
        ))
    return out


def _fmt(m: int) -> str:
    return f"{int(m) // 60:02d}:{int(m) % 60:02d}"
