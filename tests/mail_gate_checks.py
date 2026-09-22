"""FIX #353: extra client-mail checks shared by KRK / KAT / POZ gates."""
from __future__ import annotations

from typing import Any, Dict, List

from app.application.services.plan_service import (
    _fold_place_label, _is_hub_place_label, _place_names_match,
)
from app.domain.models.plan import ItemType
from app.domain.planner.time_utils import time_to_minutes
from app.domain.validators.client_invariants import _tv

WATCH = (
    "car_teleport",
    "phantom_lead",
    "self_hop",
    "missing_hop",
    "idle_start",
    "late_start",
    "after_dark_outdoor",
    "park_stack",
    "long_free_time",
    "after_day_end",
    "from_mismatch",
    "dishonest_leg",
    "overlap",
    "dangling_hop",
)
GAP_MIN = 45


def collect_day_mail_hits(
    *,
    num: int,
    day: Any,
    payload: Dict[str, Any],
    city: str,
) -> List[str]:
    hits: list[str] = []
    window = payload.get("daily_time_window") or {}
    try:
        win_end = time_to_minutes(window.get("end") or "20:00")
    except Exception:
        win_end = 20 * 60
    has_dinner = False
    has_lunch = False
    lunch_en = None
    dinner_st = None
    dinner_dur = 0
    n_attr = 0
    last_en = None
    saw_car = False
    for it in day.items or []:
        tv = _tv(it)
        raw = getattr(it, "end_time", None) or getattr(it, "time", None)
        if raw:
            try:
                last_en = time_to_minutes(raw)
            except Exception:
                pass
        if tv == ItemType.ATTRACTION.value:
            n_attr += 1
            pid = str(getattr(it, "poi_id", "") or "").lower()
            why = [
                str(x).lower()
                for x in (getattr(it, "why_selected", None) or [])
            ]
            if "mail_dangling" in pid or any("mail_visit" in w for w in why):
                hits.append(
                    f"J{num} D{day.day} [tech_fill] {getattr(it, 'name', '')}"
                )
        if tv == ItemType.LUNCH_BREAK.value:
            has_lunch = True
            try:
                st = time_to_minutes(getattr(it, "start_time", None) or "")
                en = time_to_minutes(getattr(it, "end_time", None) or "")
            except Exception:
                st, en = None, None
            if st is not None and st >= 15 * 60 + 30:
                hits.append(f"J{num} D{day.day} [late_lunch] {it.start_time}")
            if st is not None and en is not None:
                lunch_en = en
                if en - st < 30:
                    hits.append(
                        f"J{num} D{day.day} [short_lunch] {en - st} min"
                    )
        if tv == ItemType.DINNER_BREAK.value:
            has_dinner = True
            try:
                dinner_st = time_to_minutes(getattr(it, "start_time", None) or "")
                den = time_to_minutes(getattr(it, "end_time", None) or "")
                dinner_dur = den - dinner_st if den and dinner_st else int(
                    getattr(it, "duration_min", 0) or 0
                )
            except Exception:
                dinner_st = None
            if dinner_dur and dinner_dur < 30:
                hits.append(
                    f"J{num} D{day.day} [short_dinner] {dinner_dur} min"
                )
            if dinner_st is not None and dinner_st < 17 * 60:
                hits.append(
                    f"J{num} D{day.day} [early_dinner] {it.start_time}"
                )
            if (
                lunch_en is not None
                and dinner_st is not None
                and dinner_st - lunch_en < 180
            ):
                hits.append(
                    f"J{num} D{day.day} [early_dinner] "
                    f"{dinner_st - lunch_en} min after lunch"
                )
        if tv == ItemType.FREE_TIME.value:
            label = (getattr(it, "label", "") or "").strip().lower()
            try:
                st = time_to_minutes(getattr(it, "start_time", None) or "")
            except Exception:
                st = None
            if (
                "kolacji" in label
                and st is not None
                and (dinner_st is None or st < dinner_st)
            ):
                hits.append(
                    f"J{num} D{day.day} [ft_before_dinner] {it.start_time}"
                )
        if tv == ItemType.TRANSIT.value:
            mode = str(
                getattr(
                    getattr(it, "mode", None), "value", getattr(it, "mode", ""),
                ) or ""
            ).lower()
            dest = (getattr(it, "to_location", "") or "").strip()
            src = str(getattr(it, "routing_source", "") or "").lower()
            if "car" in mode:
                saw_car = True
            if (
                "return_to_car" in src
                and dest
                and saw_car
                and (
                    _is_hub_place_label(dest)
                    or _place_names_match(dest, city)
                )
            ):
                hits.append(
                    f"J{num} D{day.day} [hub_return] {dest}"
                )
            pid = str(getattr(it, "poi_id", "") or "").lower()
            if "mail_dangling" in pid:
                hits.append(f"J{num} D{day.day} [tech_fill] {dest}")
    if (
        win_end >= 18 * 60
        and n_attr >= 1
        and not has_dinner
    ):
        hits.append(f"J{num} D{day.day} [no_dinner]")
    if (
        win_end - time_to_minutes(window.get("start") or "09:00") >= 5 * 60
        and n_attr >= 1
        and not has_lunch
    ):
        hits.append(f"J{num} D{day.day} [no_lunch]")
    return hits
