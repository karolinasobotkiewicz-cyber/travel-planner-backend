"""FIX #352: Katowice client-mail gate over the ten JSONs."""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path

import pytest

from app.application.services.plan_service import PlanService, _fold_place_label
from app.domain.models.trip_input import TripInput
from app.domain.models.plan import ItemType
from app.domain.validators.client_invariants import audit_plan, _tv
from app.infrastructure.repositories.poi_repository import POIRepository
from app.domain.planner.time_utils import time_to_minutes

_HERE = Path(__file__).resolve().parent
_JSON_DIR = _HERE.parents[1] / "json_miasta" / "Katowice"
_EXCEL = _HERE.parents[0] / "data" / "zakopane.xlsx"

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
)
GAP_MIN = 45
SPORT = (
    "cybermagi", "wspin", "gokart", "skate", "park linow", "gojump",
    "bowling", "sport", "fitnes", "basen", "aqua", "rower",
)
UNDER = ("guido", "luiza", "kopaln", "podziem", "carboneum", "sztoln", "adit")


@pytest.mark.slow
def test_katowice_client_mail_defects_are_gone():
    if not _JSON_DIR.exists() or not _EXCEL.exists():
        pytest.skip("Katowice fixtures are not present in this checkout")
    os.environ.setdefault("ORS_ENABLED", "false")
    svc = PlanService(POIRepository(str(_EXCEL)))

    hits: list[str] = []
    for num in range(1, 11):
        path = _JSON_DIR / f"test-{num:02d}.json"
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            plan = svc.generate_plan(TripInput(**payload))
        window = payload.get("daily_time_window") or {}
        group = payload.get("group") or {}
        prefs = [str(p).lower() for p in (payload.get("preferences") or [])]
        ctx = {
            "day_start": window.get("start") or "09:00",
            "day_end": window.get("end"),
            "requested_city": "Katowice",
            "has_car": True,
            "travel_style": payload.get("travel_style"),
            "group_type": group.get("type"),
            "children_age": group.get("children_age"),
            "preferences": payload.get("preferences") or [],
            "date": (payload.get("trip_length") or {}).get("start_date"),
        }
        kids = "kids" in str(group.get("type") or "").lower() or bool(
            group.get("children_age")
        )
        try:
            win_end = time_to_minutes(window.get("end") or "20:00")
        except Exception:
            win_end = 20 * 60
        try:
            win_start = time_to_minutes(window.get("start") or "09:00")
        except Exception:
            win_start = 9 * 60
        limit = float((payload.get("budget") or {}).get("daily_limit") or 0)
        sport_hit = False
        under_hit = False
        for d in audit_plan(plan.days, context=ctx):
            if d.code == "anonymous_gap":
                sm = (d.meta or {}).get("start")
                em = (d.meta or {}).get("end")
                if sm is None or em is None or em - sm < GAP_MIN:
                    continue
                hits.append(f"J{num} D{d.day} [{d.code}] {d.message}")
                continue
            if d.code in WATCH:
                hits.append(f"J{num} D{d.day} [{d.code}] {d.message}")
        for day in plan.days:
            has_dinner = False
            has_lunch = False
            dinner_named = False
            last_en = None
            seen: set[str] = set()
            n_attr = 0
            day_cost = 0.0
            car_km = 0.0
            inbound_end = None
            inbound_to = ""
            for it in day.items or []:
                tv = _tv(it)
                raw = getattr(it, "end_time", None) or getattr(it, "time", None)
                if raw:
                    try:
                        last_en = time_to_minutes(raw)
                    except Exception:
                        pass
                if tv == ItemType.DINNER_BREAK.value:
                    has_dinner = True
                    sugg = getattr(it, "suggestions", None) or []
                    label = (getattr(it, "label", "") or "").strip().lower()
                    if sugg or (
                        label
                        and label not in ("kolacja", "dinner", "posiłek", "posilek")
                    ):
                        dinner_named = True
                    try:
                        dst = time_to_minutes(getattr(it, "start_time", None) or "")
                        if dst >= 22 * 60:
                            hits.append(
                                f"J{num} D{day.day} [late_dinner] {it.start_time}"
                            )
                    except Exception:
                        pass
                if tv == ItemType.LUNCH_BREAK.value:
                    has_lunch = True
                if tv == ItemType.ATTRACTION.value:
                    n_attr += 1
                    nm = getattr(it, "name", "") or ""
                    folded = _fold_place_label(nm)
                    seen.add(folded)
                    try:
                        day_cost += float(getattr(it, "cost_estimate", 0) or 0)
                    except (TypeError, ValueError):
                        pass
                    if kids and "browar" in folded:
                        hits.append(f"J{num} D{day.day} [kids_alcohol] {nm}")
                    city = (getattr(it, "city", "") or "").strip().lower()
                    if "szyb wilson" in folded and "chorz" in city:
                        hits.append(
                            f"J{num} D{day.day} [wilson_city] {city}"
                        )
                    if any(k in folded for k in SPORT):
                        sport_hit = True
                    if any(k in folded for k in UNDER):
                        under_hit = True
                    try:
                        st = time_to_minutes(getattr(it, "start_time", None) or "")
                    except Exception:
                        st = None
                    if (
                        inbound_end is not None
                        and st is not None
                        and st - inbound_end >= GAP_MIN
                        and inbound_to
                        and (
                            inbound_to in folded
                            or folded in inbound_to
                            or _fold_place_label(inbound_to) in folded
                        )
                    ):
                        hits.append(
                            f"J{num} D{day.day} [inbound_gap] "
                            f"{inbound_end}→{st} before {nm}"
                        )
                    inbound_end = None
                    inbound_to = ""
                if tv == ItemType.TRANSIT.value:
                    frm = (getattr(it, "from_location", "") or "").strip()
                    dest = (getattr(it, "to_location", "") or "").strip()
                    mode = str(
                        getattr(
                            getattr(it, "mode", None), "value",
                            getattr(it, "mode", ""),
                        ) or ""
                    ).lower()
                    try:
                        km = float(getattr(it, "distance_km", 0) or 0)
                    except (TypeError, ValueError):
                        km = 0.0
                    if "car" in mode:
                        car_km += km
                        if km >= 80:
                            hits.append(
                                f"J{num} D{day.day} [insane_hop] "
                                f"{frm} → {dest} {km:.0f} km"
                            )
                    try:
                        inbound_end = time_to_minutes(
                            getattr(it, "end_time", None) or ""
                        )
                        inbound_to = dest
                    except Exception:
                        inbound_end = None
                        inbound_to = ""
                    ff = _fold_place_label(frm)
                    if (
                        ff
                        and len(ff) >= 12
                        and "katowic" not in ff
                        and "centrum" not in ff
                        and "chorz" not in ff
                        and not any(ff in a or a in ff for a in seen)
                        and ("muzeum" in ff or "park" in ff)
                    ):
                        hits.append(f"J{num} D{day.day} [ghost_from] {frm}")
                    if dest:
                        seen.add(_fold_place_label(dest))
            if n_attr == 0:
                hits.append(f"J{num} D{day.day} [empty_day]")
            if (
                win_end - win_start >= 5 * 60
                and n_attr >= 1
                and not has_lunch
            ):
                hits.append(f"J{num} D{day.day} [no_lunch]")
            if (
                win_end >= 18 * 60
                and n_attr >= 1
                and not has_dinner
                and last_en is not None
                and last_en <= 16 * 60 + 30
            ):
                hits.append(f"J{num} D{day.day} [no_dinner]")
            if has_dinner and not dinner_named:
                hits.append(f"J{num} D{day.day} [generic_dinner]")
            if limit and day_cost > limit * 1.05:
                hits.append(
                    f"J{num} D{day.day} [over_budget] "
                    f"{day_cost:.0f} > {limit:.0f}"
                )
            if kids and car_km >= 80:
                hits.append(
                    f"J{num} D{day.day} [kids_drive] {car_km:.0f} km"
                )
        if num == 3 and "active_sport" in prefs and not sport_hit:
            hits.append("J3 [no_active_sport]")
        if num == 7 and "underground" in prefs and not under_hit:
            hits.append("J7 [no_underground]")

    assert not hits, (
        "Katowice client-mail defects still in the JSON fixtures:\n"
        + "\n".join(hits)
    )
