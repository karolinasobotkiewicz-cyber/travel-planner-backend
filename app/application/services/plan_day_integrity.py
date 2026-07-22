"""FIX #237 — day timeline / transit / meal integrity helpers."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.domain.models.plan import ItemType, RestaurantSuggestion
from app.domain.planner.engine import _tiered_nearby_restaurants
from app.domain.planner.time_utils import minutes_to_time, time_to_minutes
from app.domain.validators import validate_and_heal_timeline, validate_timeline_integrity


def _type_val(item: Any) -> str:
    t = getattr(item, "type", None)
    if hasattr(t, "value"):
        return str(t.value)
    return str(t or "")


def _is_attraction(item: Any) -> bool:
    return _type_val(item) == ItemType.ATTRACTION.value


def _last_attraction_before(items: List[Any], idx: int) -> Optional[Any]:
    for j in range(idx - 1, -1, -1):
        if _is_attraction(items[j]):
            return items[j]
    return None


def _poi_dict_from_attraction(attr: Any, poi_coords: Dict[str, dict]) -> dict:
    name = getattr(attr, "name", "") or ""
    base = dict(poi_coords.get(name) or {})
    if not base.get("lat") and getattr(attr, "lat", None):
        base["lat"] = attr.lat
        base["lng"] = attr.lng
        base["name"] = name
    return base


def drop_negative_duration_items(items: List[Any], day_num: int = 1) -> List[Any]:
    """Remove or fix items where end_time <= start_time."""
    out: List[Any] = []
    for it in items:
        st = getattr(it, "start_time", None)
        en = getattr(it, "end_time", None)
        if not st or not en:
            out.append(it)
            continue
        if time_to_minutes(en) <= time_to_minutes(st):
            print(f"[FIX #237] Day {day_num}: dropped item with non-positive duration {st}-{en}")
            continue
        out.append(it)
    return out


def fix_transit_meal_overlaps(items: List[Any], day_num: int = 1) -> List[Any]:
    """
    Transit must not overlap lunch/dinner — shift transit earlier into slack or
    push meal later (never shrink meal below 30 min).
    """
    if len(items) < 2:
        return items
    working = list(items)
    for _pass in range(3):
        changed = False
        for i, it in enumerate(working):
            if _type_val(it) not in (ItemType.TRANSIT.value,):
                continue
            t_st = time_to_minutes(getattr(it, "start_time", "00:00"))
            t_en = time_to_minutes(getattr(it, "end_time", "00:00"))
            for j in range(i + 1, min(i + 4, len(working))):
                nxt = working[j]
                if _type_val(nxt) not in (
                    ItemType.LUNCH_BREAK.value,
                    ItemType.DINNER_BREAK.value,
                ):
                    continue
                m_st = time_to_minutes(getattr(nxt, "start_time", "00:00"))
                m_en = time_to_minutes(getattr(nxt, "end_time", "00:00"))
                if t_en <= m_st or t_st >= m_en:
                    break
                # overlap transit with meal
                dur = max(3, t_en - t_st)
                prev_en = None
                if i > 0:
                    prev_en = time_to_minutes(getattr(working[i - 1], "end_time", "00:00"))
                new_start = m_st - dur
                if prev_en is not None:
                    new_start = max(new_start, prev_en)
                new_end = new_start + dur
                if new_end <= m_st and new_end > new_start:
                    it.start_time = minutes_to_time(new_start)
                    it.end_time = minutes_to_time(new_end)
                    it.duration_min = new_end - new_start
                    changed = True
                    print(
                        f"[FIX #237] Day {day_num}: shifted transit before meal "
                        f"to {it.start_time}-{it.end_time}"
                    )
                elif m_en - m_st >= 35:
                    shift = t_en - m_st
                    nxt.start_time = minutes_to_time(m_st + shift)
                    nxt.end_time = minutes_to_time(m_en + shift)
                    nxt.duration_min = m_en - m_st
                    changed = True
                    print(f"[FIX #237] Day {day_num}: pushed meal after transit overlap")
                break
        if not changed:
            break
    return working


def ensure_meal_suggestions(
    items: List[Any],
    poi_coords: Dict[str, dict],
    context: dict,
    *,
    parse_suggestion_fn,
    filter_fn,
) -> List[Any]:
    """Fill empty lunch/dinner suggestions from tiered nearby restaurants."""
    restaurants = context.get("restaurants_available") or []
    if not restaurants:
        return items
    out: List[Any] = []
    meal_types = {
        ItemType.LUNCH_BREAK.value: "lunch",
        ItemType.DINNER_BREAK.value: "dinner",
    }
    for idx, it in enumerate(items):
        t = _type_val(it)
        if t not in meal_types:
            out.append(it)
            continue
        meal_type = meal_types[t]
        raw_sug = getattr(it, "suggestions", None) or []
        filtered = filter_fn(raw_sug) if raw_sug else []
        if filtered:
            out.append(it)
            continue
        prev = _last_attraction_before(items, idx)
        if not prev:
            out.append(it)
            continue
        last_poi = _poi_dict_from_attraction(prev, poi_coords)
        if not last_poi.get("lat"):
            out.append(it)
            continue
        nearby = _tiered_nearby_restaurants(restaurants, last_poi, context, limit=3)
        if not nearby:
            out.append(it)
            continue
        suggestions: List[RestaurantSuggestion] = [
            parse_suggestion_fn(r, meal_type) for r in nearby
        ]
        suggestions = filter_fn(suggestions)
        if not suggestions:
            out.append(it)
            continue
        try:
            out.append(it.model_copy(update={"suggestions": suggestions}))
        except Exception:
            out.append(it)
        print(
            f"[FIX #237] Filled {meal_type} suggestions near "
            f"{getattr(prev, 'name', '?')}: {[s.name for s in suggestions]}"
        )
    return out


def assert_transit_endpoints_match_pois(
    items: List[Any],
    poi_coords: Dict[str, dict],
    day_num: int = 1,
) -> List[Any]:
    """Drop transits whose endpoints are not scheduled attractions (already in #200)."""
    names = {
        getattr(it, "name", "")
        for it in items
        if _is_attraction(it) and getattr(it, "name", "")
    }
    out = []
    for it in items:
        if _type_val(it) != ItemType.TRANSIT.value:
            out.append(it)
            continue
        fr = getattr(it, "from_location", "") or ""
        to = getattr(it, "to_location", "") or ""
        if fr and fr not in names and fr not in ("Zakopane (Hotel)",):
            print(f"[FIX #237] Day {day_num}: removed transit bad origin {fr}->{to}")
            continue
        if to and to not in names:
            print(f"[FIX #237] Day {day_num}: removed transit bad dest {fr}->{to}")
            continue
        fp, tp = poi_coords.get(fr), poi_coords.get(to)
        if fr in names and to in names and (not fp or not tp):
            print(f"[FIX #237] Day {day_num}: removed transit missing POI coords {fr}->{to}")
            continue
        out.append(it)
    return out


def run_timeline_integrity_pass(
    items: List[Any],
    day_num: int = 1,
) -> tuple[List[Any], List[str]]:
    items = drop_negative_duration_items(items, day_num)
    items = fix_transit_meal_overlaps(items, day_num)
    items, warnings = validate_and_heal_timeline(items, day_number=day_num, raise_on_failure=False)
    overlaps = validate_timeline_integrity(items)
    if overlaps:
        warnings.append(f"Day {day_num}: {len(overlaps)} overlaps after heal")
    return items, warnings
