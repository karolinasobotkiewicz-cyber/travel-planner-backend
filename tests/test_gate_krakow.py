"""FIX #349/#350: Kraków client-mail gate over the ten JSONs.

Fails car teleports, idle mornings, winter-dusk parks, stacked walking
parks, long holes, and the #348 hop-clock seals they sit on.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
from datetime import date as _date, timedelta as _td
from pathlib import Path

import pytest

from app.application.services.plan_service import (
    PlanService, _fold_place_label, krakow_client_limits,
    _place_names_match, _is_wieliczka_stop_name, _is_ojcow_stop_name,
)
from app.domain.planner.krakow_parking import is_parking_label
from app.domain.models.trip_input import TripInput
from app.domain.models.plan import ItemType
from app.domain.planner.engine import visit_duration_hard_cap
from app.domain.planner.leg_physics import leg_km, walk_minutes
from app.domain.planner.time_utils import time_to_minutes
from app.domain.validators.client_invariants import audit_plan
from app.infrastructure.repositories.poi_repository import POIRepository
from app.infrastructure.routing.haversine import haversine_km
from tests.mail_gate_checks import WATCH, GAP_MIN, collect_day_mail_hits

_HERE = Path(__file__).resolve().parent
_JSON_DIR = _HERE.parents[1] / "json_miasta" / "Kraków"
_EXCEL = _HERE.parents[0] / "data" / "zakopane.xlsx"

@pytest.mark.slow
def test_krakow_client_mail_defects_are_gone():
    if not _JSON_DIR.exists() or not _EXCEL.exists():
        pytest.skip("Kraków fixtures are not present in this checkout")
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
        ctx = {
            "day_start": window.get("start") or "09:00",
            "day_end": window.get("end"),
            "requested_city": "Kraków",
            "has_car": True,
            "travel_style": payload.get("travel_style"),
            "group_type": (payload.get("group") or {}).get("type"),
            "children_age": (payload.get("group") or {}).get("children_age"),
            "preferences": payload.get("preferences") or [],
            # FIX #369 P1: legs must agree with their pins (no constants).
            "audit_leg_distances": True,
            # FIX #369 P2: the car stands at a real parking all day.
            "audit_car_model": True,
        }
        start = payload.get("trip_length") or {}
        if start.get("start_date"):
            ctx["date"] = start.get("start_date")
        for d in audit_plan(plan.days, context=ctx):
            if d.code == "anonymous_gap":
                sm = (d.meta or {}).get("start")
                em = (d.meta or {}).get("end")
                if sm is None or em is None or em - sm < GAP_MIN:
                    continue
                hits.append(f"J{num} D{d.day} [{d.code}] {d.message}")
                continue
            if d.code in WATCH or d.code in (
                "distance_vs_coords_mismatch",
                "generic_car_return",
                "car_position_mismatch",
            ):
                hits.append(f"J{num} D{d.day} [{d.code}] {d.message}")
        hop, day_budget, lunch_by, max_before = krakow_client_limits({
            "travel_style": payload.get("travel_style"),
            "group_type": (payload.get("group") or {}).get("type"),
        })
        seen_places: list[str] = []
        shapes: list[tuple] = []
        seen_mine = False
        for day in plan.days:
            hits.extend(collect_day_mail_hits(
                num=num, day=day, payload=payload, city="Kraków",
            ))
            occupied = []
            for it in day.items or []:
                kind = getattr(getattr(it, "type", None), "value", getattr(it, "type", ""))
                if kind == ItemType.ATTRACTION.value:
                    folded = _fold_place_label(getattr(it, "name", "") or "")
                    if folded:
                        for prev in seen_places:
                            if prev == folded or (
                                len(prev) >= 10 and len(folded) >= 10
                                and (prev in folded or folded in prev)
                            ):
                                hits.append(
                                    f"J{num} D{day.day} [repeat_place] "
                                    f"{getattr(it, 'name', '')}"
                                )
                                break
                        seen_places.append(folded)
                    lat, lng = getattr(it, "lat", None), getattr(it, "lng", None)
                    try:
                        st = time_to_minutes(getattr(it, "start_time", None) or "")
                        en = time_to_minutes(getattr(it, "end_time", None) or "")
                    except Exception:
                        st = en = None
                    if lat is not None and lng is not None and st is not None and en is not None:
                        occupied.append((st, en, float(lat), float(lng), "attr"))
                elif kind in (ItemType.LUNCH_BREAK.value, ItemType.DINNER_BREAK.value):
                    try:
                        st = time_to_minutes(getattr(it, "start_time", None) or "")
                        en = time_to_minutes(getattr(it, "end_time", None) or "")
                    except Exception:
                        continue
                    occupied.append((st, en, None, None, "meal"))
                elif kind == ItemType.TRANSIT.value:
                    mode = str(getattr(getattr(it, "mode", None), "value", getattr(it, "mode", "")) or "")
                    if "walk" not in mode:
                        continue
                    try:
                        km = float(getattr(it, "distance_km", 0) or 0)
                    except (TypeError, ValueError):
                        km = 0.0
                    frm = getattr(it, "from_location", "") or ""
                    dest = getattr(it, "to_location", "") or ""
                    if km > hop:
                        hits.append(
                            f"J{num} D{day.day} [long_walk] {frm} → {dest} {km:.2f} km"
                        )
                    if km >= 0.4:
                        try:
                            wst = time_to_minutes(getattr(it, "start_time", None) or "")
                            wen = time_to_minutes(getattr(it, "end_time", None) or "")
                            wdur = wen - wst
                        except Exception:
                            wdur = int(getattr(it, "duration_min", 0) or 0)
                        honest = walk_minutes(km, {
                            "travel_style": payload.get("travel_style"),
                            "group_type": (payload.get("group") or {}).get("type"),
                        })
                        if wdur > honest + 12:
                            hits.append(
                                f"J{num} D{day.day} [slow_walk] {frm} → {dest} "
                                f"{km:.2f} km / {wdur} min"
                            )
            attrs = [row for row in occupied if row[4] == "attr"]
            for i in range(len(attrs)):
                for j in range(i + 1, len(attrs)):
                    if any(attrs[i + 1:j]):
                        dist = haversine_km(attrs[i][2], attrs[i][3], attrs[j][2], attrs[j][3])
                        if dist > 0.7:
                            continue
                        far = False
                        for mid in attrs[i + 1:j]:
                            if (
                                haversine_km(attrs[i][2], attrs[i][3], mid[2], mid[3]) > 1.2
                                and haversine_km(attrs[j][2], attrs[j][3], mid[2], mid[3]) > 1.2
                            ):
                                far = True
                                break
                        if far:
                            hits.append(
                                f"J{num} D{day.day} [split_pair] {dist:.2f} km"
                            )
                            break
            for (s1, e1, _a, _b, _k), (s2, e2, _c, _d, _m) in zip(occupied, occupied[1:]):
                if s2 - e1 > 90:
                    hits.append(
                        f"J{num} D{day.day} [dead_span] {e1}->{s2} ({s2 - e1} min)"
                    )
            walk_sum = 0.0
            lunch_start = None
            before_lunch = 0
            for it in day.items or []:
                kind = getattr(getattr(it, "type", None), "value", getattr(it, "type", ""))
                if kind == ItemType.TRANSIT.value:
                    mode = str(getattr(getattr(it, "mode", None), "value", getattr(it, "mode", "")) or "")
                    if "walk" in mode:
                        try:
                            walk_sum += float(getattr(it, "distance_km", 0) or 0)
                        except (TypeError, ValueError):
                            pass
                elif kind == ItemType.LUNCH_BREAK.value:
                    try:
                        lunch_start = time_to_minutes(getattr(it, "start_time", None) or "")
                        lunch_end = time_to_minutes(getattr(it, "end_time", None) or "")
                        if lunch_end - lunch_start > 75:
                            hits.append(
                                f"J{num} D{day.day} [long_lunch] "
                                f"{lunch_end - lunch_start} min"
                            )
                    except Exception:
                        lunch_start = None
                elif kind == ItemType.ATTRACTION.value:
                    nm = _fold_place_label(getattr(it, "name", "") or "")
                    try:
                        dur = time_to_minutes(getattr(it, "end_time", None) or "") - time_to_minutes(
                            getattr(it, "start_time", None) or ""
                        )
                    except Exception:
                        dur = int(getattr(it, "duration_min", 0) or 0)
                    cap = visit_duration_hard_cap({"name": getattr(it, "name", "") or ""})
                    if ("muzeum" in nm or "podziemia" in nm) and dur < 60 and (cap is None or cap >= 60):
                        hits.append(
                            f"J{num} D{day.day} [short_museum] "
                            f"{getattr(it, 'name', '')} {dur} min"
                        )
                    low = (getattr(it, "name", "") or "").lower()
                    if cap is None and any(k in low for k in ("pomnik", "brama", "kładka", "kladka")):
                        cap = 30
                    if cap is not None and dur > cap + 5:
                        hits.append(
                            f"J{num} D{day.day} [long_visit] "
                            f"{getattr(it, 'name', '')} {dur} min > {cap}"
                        )
                    if lunch_start is None:
                        before_lunch += 1
            if walk_sum > day_budget + 0.05:
                hits.append(
                    f"J{num} D{day.day} [day_walk] {walk_sum:.2f} km"
                )
            try:
                win_end = time_to_minutes(
                    (payload.get("daily_time_window") or {}).get("end") or ""
                )
            except Exception:
                win_end = None
            if win_end is not None and win_end <= 16 * 60 + 30:
                last_attr_end = None
                dinner_after = False
                for it in day.items or []:
                    kind = getattr(getattr(it, "type", None), "value", getattr(it, "type", ""))
                    if kind == ItemType.ATTRACTION.value:
                        try:
                            last_attr_end = time_to_minutes(getattr(it, "end_time", None) or "")
                        except Exception:
                            pass
                    elif kind == ItemType.DINNER_BREAK.value and last_attr_end is not None:
                        dinner_after = True
                if (
                    last_attr_end is not None
                    and not dinner_after
                    and win_end - last_attr_end >= 70
                ):
                    hits.append(
                        f"J{num} D{day.day} [short_afternoon] "
                        f"{last_attr_end // 60:02d}:{last_attr_end % 60:02d}"
                    )
            if lunch_start is not None and lunch_start > lunch_by + 15:
                grace = False
                if lunch_start <= lunch_by + 20:
                    prev_ll = None
                    last_ll = None
                    for it in day.items or []:
                        kind = getattr(getattr(it, "type", None), "value", getattr(it, "type", ""))
                        if kind == ItemType.LUNCH_BREAK.value:
                            break
                        if kind != ItemType.ATTRACTION.value:
                            continue
                        lat, lng = getattr(it, "lat", None), getattr(it, "lng", None)
                        if lat is None or lng is None:
                            continue
                        prev_ll, last_ll = last_ll, (float(lat), float(lng))
                    if prev_ll and last_ll and haversine_km(
                        prev_ll[0], prev_ll[1], last_ll[0], last_ll[1],
                    ) <= 0.7:
                        grace = True
                if not grace:
                    hits.append(
                        f"J{num} D{day.day} [late_lunch] {lunch_start // 60:02d}:{lunch_start % 60:02d}"
                    )
            if (
                before_lunch > max_before
                and lunch_start is not None
                and lunch_start > lunch_by + 15
            ):
                coords = []
                for it in day.items or []:
                    kind = getattr(getattr(it, "type", None), "value", getattr(it, "type", ""))
                    if kind == ItemType.LUNCH_BREAK.value:
                        break
                    if kind != ItemType.ATTRACTION.value:
                        continue
                    lat, lng = getattr(it, "lat", None), getattr(it, "lng", None)
                    if lat is None or lng is None:
                        continue
                    coords.append((float(lat), float(lng)))
                clustered = len(coords) >= before_lunch and all(
                    haversine_km(coords[i - 1][0], coords[i - 1][1], coords[i][0], coords[i][1]) <= 0.7
                    for i in range(max_before, len(coords))
                )
                if not clustered:
                    hits.append(
                        f"J{num} D{day.day} [lunch_after] {before_lunch} atrakcji"
                    )
            note = (getattr(day, "note", None) or "").lower()
            if "krótszy dzień" in note or "wolne popołudnie" in note:
                for it in day.items or []:
                    kind = getattr(getattr(it, "type", None), "value", getattr(it, "type", ""))
                    if kind != ItemType.ATTRACTION.value:
                        continue
                    try:
                        en = time_to_minutes(getattr(it, "end_time", None) or "")
                    except Exception:
                        continue
                        if en >= 16 * 60:
                            hits.append(
                                f"J{num} D{day.day} [false_short_day] {getattr(day, 'note', '')}"
                            )
                            break
            names = []
            timed = []
            for it in day.items or []:
                kind = getattr(getattr(it, "type", None), "value", getattr(it, "type", ""))
                try:
                    st = time_to_minutes(getattr(it, "start_time", None) or "")
                    en = time_to_minutes(getattr(it, "end_time", None) or "")
                except Exception:
                    st = en = None
                lat, lng = getattr(it, "lat", None), getattr(it, "lng", None)
                if kind == ItemType.ATTRACTION.value:
                    names.append(getattr(it, "name", "") or "")
                    if lat is not None and lng is not None and st is not None:
                        timed.append(("attr", st, en, float(lat), float(lng), getattr(it, "name", "")))
                elif kind in (ItemType.LUNCH_BREAK.value, ItemType.DINNER_BREAK.value):
                    meal_pt = None
                    for sug in (getattr(it, "suggestions", None) or [])[:1]:
                        slat = getattr(sug, "lat", None) if not isinstance(sug, dict) else sug.get("lat")
                        slng = getattr(sug, "lng", None) if not isinstance(sug, dict) else sug.get("lng")
                        try:
                            if slat is not None and slng is not None and abs(float(slat)) > 0.01:
                                meal_pt = (float(slat), float(slng))
                        except (TypeError, ValueError):
                            meal_pt = None
                    label = ""
                    for sug in (getattr(it, "suggestions", None) or [])[:1]:
                        label = getattr(sug, "name", None) or (sug.get("name") if isinstance(sug, dict) else "") or ""
                    timed.append(("meal", st, en, meal_pt, label or getattr(it, "label", "") or ""))
                elif kind == ItemType.TRANSIT.value:
                    timed.append((
                        "transit", st, en,
                        str(getattr(getattr(it, "mode", None), "value", getattr(it, "mode", "")) or ""),
                        float(getattr(it, "distance_km", 0) or 0),
                        getattr(it, "to_location", "") or "",
                    ))
            last_place = None
            for i, row in enumerate(timed):
                if row[0] != "meal" or row[1] is None:
                    if row[0] == "attr":
                        last_place = row
                    continue
                prev_end = None
                travel = 0
                prev_attr = None
                for earlier in timed[:i]:
                    if earlier[0] in ("attr", "meal") and earlier[2] is not None:
                        prev_end = earlier[2]
                        travel = 0
                        prev_attr = earlier if earlier[0] == "attr" else None
                    elif (
                        earlier[0] == "transit"
                        and prev_end is not None
                        and earlier[1] is not None
                        and earlier[1] >= prev_end
                    ):
                        travel += max(0, (earlier[2] or earlier[1]) - earlier[1])
                if prev_end is not None and row[1] - prev_end - travel > 20:
                    hits.append(
                        f"J{num} D{day.day} [meal_wait] {row[1] - prev_end} min"
                    )
                if prev_attr is not None and row[0] == "meal":
                    for leg in timed[:i]:
                        if leg[0] != "transit" or "walk" not in str(leg[3]):
                            continue
                        if leg[1] is None or leg[1] < prev_attr[1]:
                            continue
                        declared = leg[4]
                        dest = _fold_place_label(str(leg[5]))
                        meal_name = _fold_place_label(str(row[4]))
                        if declared >= 0.15 or not dest or not meal_name:
                            continue
                        if dest not in meal_name and meal_name not in dest:
                            continue
                        real = None
                        if row[3] is not None:
                            real = haversine_km(prev_attr[3], prev_attr[4], row[3][0], row[3][1])
                        drove = any(
                            earlier[0] == "transit" and "car" in str(earlier[3])
                            and earlier[1] is not None and prev_attr[2] is not None
                            and earlier[1] >= prev_attr[2]
                            for earlier in timed[:i]
                        )
                        if drove:
                            continue
                        if real is None or real > 0.40:
                            hits.append(
                                f"J{num} D{day.day} [short_meal_hop] {declared:.2f} km vs {real}"
                            )
            for i, row in enumerate(timed):
                if row[0] != "attr":
                    continue
                between = []
                for later in timed[i + 1:]:
                    if later[0] != "attr":
                        between.append(later)
                        continue
                    if any(mid[0] == "meal" for mid in between) and haversine_km(
                        row[3], row[4], later[3], later[4],
                    ) <= 0.7:
                        later_dur = 60
                        if later[1] is not None and later[2] is not None and later[2] > later[1]:
                            later_dur = later[2] - later[1]
                        limit = lunch_by
                        if row[2] is not None and row[2] + later_dur + 25 <= limit:
                            hits.append(
                                f"J{num} D{day.day} [meal_split] {row[5]} / {later[5]}"
                            )
                    break
            lots: list[str] = []
            prev_attr = None
            hopped = False
            city_seen = False
            hub = (50.0647, 19.9450)
            for i, row in enumerate(timed):
                if row[0] == "transit":
                    hopped = True
                    mode = str(row[3])
                    if "car" in mode:
                        dest = _fold_place_label(str(row[5]))
                        if dest and dest in lots and (not lots or lots[-1] != dest):
                            hits.append(
                                f"J{num} D{day.day} [parking_return] {row[5]}"
                            )
                        if dest and (not lots or lots[-1] != dest):
                            lots.append(dest)
                        km = float(row[4] or 0)
                        drive_min = (
                            row[2] - row[1]
                            if row[1] is not None and row[2] is not None and row[2] > row[1]
                            else int(km * 2)
                        )
                        nxt = next((later for later in timed[i + 1:] if later[0] == "attr"), None)
                        nxt_dur = 0
                        if nxt is not None and nxt[1] is not None and nxt[2] is not None and nxt[2] > nxt[1]:
                            nxt_dur = nxt[2] - nxt[1]
                        if city_seen and km >= 20 and drive_min * 2 > nxt_dur + 15:
                            hits.append(
                                f"J{num} D{day.day} [far_tail] {km:.0f} km / {nxt_dur} min"
                            )
                elif row[0] == "attr":
                    if haversine_km(row[3], row[4], hub[0], hub[1]) <= 8:
                        city_seen = True
                    if (
                        prev_attr is not None
                        and not hopped
                        and prev_attr[2] is not None
                        and row[1] is not None
                        and row[1] - prev_attr[2] <= 2
                        and haversine_km(prev_attr[3], prev_attr[4], row[3], row[4]) > 0.15
                    ):
                        hits.append(
                            f"J{num} D{day.day} [glued] {prev_attr[5]} / {row[5]}"
                        )
                    prev_attr = row
                    hopped = False
            month = None
            raw_date = (payload.get("trip_length") or {}).get("start_date")
            if raw_date:
                try:
                    month = int(str(raw_date)[5:7])
                except (TypeError, ValueError):
                    month = None
            sat_kinds = set()
            known_lots: set[str] = set()
            attr_count = 0
            for it in day.items or []:
                kind = getattr(getattr(it, "type", None), "value", getattr(it, "type", ""))
                if kind == ItemType.ATTRACTION.value:
                    attr_count += 1
                    nm = getattr(it, "name", "") or ""
                    folded = _fold_place_label(nm)
                    if month in (11, 12, 1, 2, 3) and "ogrod doswiadczen" in folded:
                        hits.append(
                            f"J{num} D{day.day} [out_of_season] {nm}"
                        )
                    if _is_wieliczka_stop_name(nm):
                        sat_kinds.add("wieliczka")
                    elif _is_ojcow_stop_name(nm):
                        sat_kinds.add("ojcow")
                    day_date = getattr(day, "date", None)
                    weekday = None
                    if day_date:
                        try:
                            weekday = _date.fromisoformat(str(day_date)[:10]).weekday()
                        except ValueError:
                            weekday = None
                    if weekday is None and raw_date:
                        try:
                            weekday = (
                                _date.fromisoformat(str(raw_date)[:10])
                                + _td(days=int(day.day) - 1)
                            ).weekday()
                        except (TypeError, ValueError):
                            weekday = None
                    if weekday == 0 and any(
                        stem in folded
                        for stem in ("etnografic", "archeologic", "muzeum narodowe", "mocak")
                    ):
                        hits.append(f"J{num} D{day.day} [closed_monday] {nm}")
                    if "armii krajowej" in folded:
                        try:
                            st = time_to_minutes(getattr(it, "start_time", None) or "")
                            en = time_to_minutes(getattr(it, "end_time", None) or "")
                        except Exception:
                            st = en = None
                        if st is None or en is None or st > 16 * 60 or en > 17 * 60:
                            hits.append(
                                f"J{num} D{day.day} [after_close] {nm} "
                                f"{getattr(it, 'start_time', '')}-{getattr(it, 'end_time', '')}"
                            )
                    if "kopalnia" in folded and "rynek" not in folded:
                        try:
                            st = time_to_minutes(getattr(it, "start_time", None) or "")
                        except Exception:
                            st = None
                        if st is not None and st >= 18 * 60:
                            hits.append(
                                f"J{num} D{day.day} [after_close] {nm} {getattr(it, 'start_time', '')}"
                            )
                    if "wawel" in folded and "smok" not in folded:
                        try:
                            st = time_to_minutes(getattr(it, "start_time", None) or "")
                            en = time_to_minutes(getattr(it, "end_time", None) or "")
                        except Exception:
                            st = en = None
                        if st is None or en is None or st > 16 * 60 or en > 17 * 60:
                            hits.append(
                                f"J{num} D{day.day} [after_close] {nm} "
                                f"{getattr(it, 'start_time', '')}-{getattr(it, 'end_time', '')}"
                            )
                    if "pieskow" in folded:
                        try:
                            st = time_to_minutes(getattr(it, "start_time", None) or "")
                            en = time_to_minutes(getattr(it, "end_time", None) or "")
                        except Exception:
                            st = en = None
                        if st is None or en is None or st >= 16 * 60 or en > 17 * 60:
                            hits.append(
                                f"J{num} D{day.day} [after_close] {nm} "
                                f"{getattr(it, 'start_time', '')}-{getattr(it, 'end_time', '')}"
                            )
                    if "bohater" in folded and "getta" in folded:
                        cost = int(getattr(it, "cost_estimate", 0) or 0)
                        ticket = getattr(it, "ticket_info", None)
                        normal = int(getattr(ticket, "ticket_normal", 0) or 0) if ticket else 0
                        if cost > 0 or normal > 0:
                            hits.append(
                                f"J{num} D{day.day} [square_cost] {nm} {cost}/{normal} zł"
                            )
                        try:
                            dur = time_to_minutes(getattr(it, "end_time", None) or "") - time_to_minutes(
                                getattr(it, "start_time", None) or ""
                            )
                        except Exception:
                            dur = int(getattr(it, "duration_min", 0) or 0)
                        if dur > 45:
                            hits.append(
                                f"J{num} D{day.day} [square_long] {nm} {dur} min"
                            )
                        gtxt = str((payload.get("group") or {}).get("type") or "").lower()
                        ptxt = " ".join(str(p) for p in (payload.get("preferences") or [])).lower()
                        if ("kid" in gtxt or "family" in gtxt) and ("kid" in ptxt or "nature" in ptxt):
                            hits.append(f"J{num} D{day.day} [offpref_square] {nm}")
                    if "pixel" in folded:
                        gtxt = str((payload.get("group") or {}).get("type") or "").lower()
                        if "kid" not in gtxt and "family" not in gtxt:
                            hits.append(f"J{num} D{day.day} [offpref_pixel] {nm}")
                    if "podziemia rynku" in folded:
                        try:
                            st = time_to_minutes(getattr(it, "start_time", None) or "")
                        except Exception:
                            st = None
                        if st is not None and st < 10 * 60:
                            hits.append(
                                f"J{num} D{day.day} [before_open] {nm} {getattr(it, 'start_time', '')}"
                            )
                    if "muzeum narodowe" in folded and "sukiennic" not in folded:
                        try:
                            en = time_to_minutes(getattr(it, "end_time", None) or "")
                        except Exception:
                            en = None
                        if en is not None and en > 18 * 60:
                            hits.append(
                                f"J{num} D{day.day} [after_close] {nm} {getattr(it, 'end_time', '')}"
                            )
                elif kind == ItemType.TRANSIT.value:
                    frm = getattr(it, "from_location", "") or ""
                    to = getattr(it, "to_location", "") or ""
                    src = str(getattr(it, "routing_source", "") or "").lower()
                    mode = str(getattr(getattr(it, "mode", None), "value", getattr(it, "mode", "")) or "")
                    if is_parking_label(frm):
                        known_lots.add(_fold_place_label(frm))
                    if (
                        src == "return_to_car"
                        and is_parking_label(to)
                        and _fold_place_label(to) not in known_lots
                    ):
                        hits.append(
                            f"J{num} D{day.day} [car_spawn] {frm} → {to}"
                        )
                    if "car" in mode and "walk" not in mode and is_parking_label(to):
                        known_lots.add(_fold_place_label(to))
            gtxt384 = str((payload.get("group") or {}).get("type") or "").lower()
            ptxt384 = " ".join(str(p) for p in (payload.get("preferences") or [])).lower()
            family_kn = ("kid" in gtxt384 or "family" in gtxt384) and (
                "kid" in ptxt384 or "nature" in ptxt384
            )
            if family_kn and attr_count > 5:
                hits.append(
                    f"J{num} D{day.day} [family_pace] {attr_count} attractions"
                )
            bricks = []
            car_lots: list[str] = []
            prev_attr_pt = None
            for it in day.items or []:
                kind = getattr(getattr(it, "type", None), "value", getattr(it, "type", ""))
                if kind == ItemType.ATTRACTION.value:
                    nm = getattr(it, "name", "") or ""
                    folded = _fold_place_label(nm)
                    if any(stem in folded for stem in ("lego", "bricks", "klock", "swiat w budowie")):
                        bricks.append(nm)
                        if family_kn:
                            try:
                                brick_dur = (
                                    time_to_minutes(getattr(it, "end_time", None) or "")
                                    - time_to_minutes(getattr(it, "start_time", None) or "")
                                )
                            except Exception:
                                brick_dur = None
                            if brick_dur is not None and brick_dur < 30:
                                hits.append(
                                    f"J{num} D{day.day} [short_bricks] {nm} {brick_dur} min"
                                )
                    if family_kn and "etnografic" in folded:
                        hits.append(f"J{num} D{day.day} [family_filler] {nm}")
                    if family_kn and "smok" not in folded and any(
                        stem in folded for stem in ("kladka", "brama", "pomnik")
                    ):
                        hits.append(f"J{num} D{day.day} [family_filler] {nm}")
                    day_date = getattr(day, "date", None)
                    weekday = None
                    if day_date:
                        try:
                            weekday = _date.fromisoformat(str(day_date)[:10]).weekday()
                        except ValueError:
                            weekday = None
                    if weekday is None and raw_date:
                        try:
                            weekday = (
                                _date.fromisoformat(str(raw_date)[:10])
                                + _td(days=int(day.day) - 1)
                            ).weekday()
                        except (TypeError, ValueError):
                            weekday = None
                    if "geologiczn" in folded and weekday == 6:
                        hits.append(f"J{num} D{day.day} [closed_sunday] {nm}")
                    if "obwarzan" in folded and weekday is not None and weekday <= 4:
                        try:
                            st = time_to_minutes(getattr(it, "start_time", None) or "")
                            en = time_to_minutes(getattr(it, "end_time", None) or "")
                            dur = en - st
                        except Exception:
                            st = en = dur = None
                        if en is not None and (en > 16 * 60 or (dur is not None and dur > 65)):
                            hits.append(
                                f"J{num} D{day.day} [after_close] {nm} "
                                f"{getattr(it, 'start_time', '')}-{getattr(it, 'end_time', '')}"
                            )
                    prev_attr_pt = (
                        getattr(it, "lat", None),
                        getattr(it, "lng", None),
                        nm,
                    )
                elif kind == ItemType.TRANSIT.value:
                    mode = str(getattr(getattr(it, "mode", None), "value", getattr(it, "mode", "")) or "")
                    dest = getattr(it, "to_location", "") or ""
                    if "car" in mode and "walk" not in mode and is_parking_label(dest):
                        folded_lot = _fold_place_label(dest)
                        if folded_lot and folded_lot not in car_lots:
                            car_lots.append(folded_lot)
                    if (
                        "walk" in mode
                        and is_parking_label(dest)
                        and prev_attr_pt is not None
                    ):
                        nxt_i = (day.items or []).index(it) + 1
                        nxt = (day.items or [])[nxt_i] if nxt_i < len(day.items or []) else None
                        if nxt is None:
                            continue
                        nxt_mode = str(
                            getattr(getattr(nxt, "mode", None), "value", getattr(nxt, "mode", "")) or ""
                        )
                        if "walk" not in nxt_mode:
                            continue
                        if not _place_names_match(getattr(nxt, "from_location", "") or "", dest):
                            continue
                        right = (day.items or [])[nxt_i + 1] if nxt_i + 1 < len(day.items or []) else None
                        right_kind = getattr(
                            getattr(right, "type", None), "value", getattr(right, "type", ""),
                        ) if right is not None else ""
                        if right_kind != ItemType.ATTRACTION.value:
                            continue
                        if not _place_names_match(
                            getattr(nxt, "to_location", "") or "",
                            getattr(right, "name", "") or "",
                        ):
                            continue
                        try:
                            dist = float(leg_km(
                                (float(prev_attr_pt[0]), float(prev_attr_pt[1])),
                                (float(right.lat), float(right.lng)),
                                "walk",
                                city="Kraków",
                            )[0])
                        except (TypeError, ValueError):
                            continue
                        if 0.05 < dist <= hop:
                            hits.append(
                                f"J{num} D{day.day} [parking_loop] "
                                f"{prev_attr_pt[2]} → {getattr(right, 'name', '')}"
                            )
            if len(bricks) >= 2:
                hits.append(
                    f"J{num} D{day.day} [double_bricks] {bricks}"
                )
            couple_kn = "couple" in gtxt384
            if bricks and not family_kn:
                attr_names = []
                for it in day.items or []:
                    kind = getattr(getattr(it, "type", None), "value", getattr(it, "type", ""))
                    if kind == ItemType.ATTRACTION.value:
                        attr_names.append(_fold_place_label(getattr(it, "name", "") or ""))
                for nm in bricks:
                    folded_nm = _fold_place_label(nm)
                    beside = False
                    if folded_nm in attr_names:
                        pos = attr_names.index(folded_nm)
                        for neighbor in (pos - 1, pos + 1):
                            if 0 <= neighbor < len(attr_names) and "mocak" in attr_names[neighbor]:
                                beside = True
                    if couple_kn or beside:
                        hits.append(f"J{num} D{day.day} [offpref_bricks] {nm}")
            content_end = None
            content_kind = None
            transit_min = 0
            ojcow_visit = 0
            ojcow_drive = 0
            for it in day.items or []:
                kind = getattr(getattr(it, "type", None), "value", getattr(it, "type", ""))
                if kind == ItemType.ATTRACTION.value and _is_ojcow_stop_name(getattr(it, "name", "") or ""):
                    try:
                        ojcow_visit += (
                            time_to_minutes(getattr(it, "end_time", None) or "")
                            - time_to_minutes(getattr(it, "start_time", None) or "")
                        )
                    except Exception:
                        ojcow_visit += int(getattr(it, "duration_min", 0) or 0)
                if kind == ItemType.TRANSIT.value:
                    mode = str(getattr(getattr(it, "mode", None), "value", getattr(it, "mode", "")) or "")
                    if "car" in mode and "walk" not in mode:
                        blob = _fold_place_label(
                            f"{getattr(it, 'from_location', '')} {getattr(it, 'to_location', '')}"
                        )
                        try:
                            car_km = float(getattr(it, "distance_km", 0) or 0)
                        except (TypeError, ValueError):
                            car_km = 0.0
                        if car_km >= 20 or any(stem in blob for stem in ("ojcow", "pieskow", "maczuga")):
                            ojcow_drive += int(getattr(it, "duration_min", 0) or 0)
                    transit_min += int(getattr(it, "duration_min", 0) or 0)
                    continue
                if kind not in (ItemType.ATTRACTION.value, ItemType.LUNCH_BREAK.value, ItemType.DINNER_BREAK.value):
                    continue
                try:
                    st = time_to_minutes(getattr(it, "start_time", None) or "")
                    en = time_to_minutes(getattr(it, "end_time", None) or "")
                except Exception:
                    st = en = None
                if (
                    content_kind == ItemType.ATTRACTION.value
                    and kind == ItemType.ATTRACTION.value
                    and content_end is not None and st is not None
                    and st - content_end - transit_min >= 40
                ):
                    hits.append(
                        f"J{num} D{day.day} [idle_gap] {content_end}->{st}"
                    )
                if kind == ItemType.LUNCH_BREAK.value and st is not None and st > lunch_by + 30:
                    hits.append(
                        f"J{num} D{day.day} [late_group_lunch] {getattr(it, 'start_time', '')}"
                    )
                content_end = en if en is not None else st
                content_kind = kind
                transit_min = 0
            if ojcow_visit and ojcow_drive > ojcow_visit:
                hits.append(
                    f"J{num} D{day.day} [far_ojcow] drive {ojcow_drive} min / visit {ojcow_visit} min"
                )
            if len(sat_kinds) >= 2:
                hits.append(
                    f"J{num} D{day.day} [second_satellite] {sorted(sat_kinds)}"
                )
            real = False
            only_short_rynek = True
            has_rynek = False
            long_drive = False
            for it in day.items or []:
                kind = getattr(getattr(it, "type", None), "value", getattr(it, "type", ""))
                if kind == ItemType.ATTRACTION.value:
                    nm = getattr(it, "name", "") or ""
                    if _is_ojcow_stop_name(nm) or (
                        _is_wieliczka_stop_name(nm) and "rynek" not in _fold_place_label(nm)
                    ):
                        real = True
                    if _is_wieliczka_stop_name(nm):
                        folded = _fold_place_label(nm)
                        if "rynek" in folded:
                            has_rynek = True
                            try:
                                dur = time_to_minutes(getattr(it, "end_time", None) or "") - time_to_minutes(
                                    getattr(it, "start_time", None) or ""
                                )
                            except Exception:
                                dur = 0
                            if dur >= 55:
                                only_short_rynek = False
                        else:
                            only_short_rynek = False
                elif kind == ItemType.TRANSIT.value:
                    mode = str(getattr(getattr(it, "mode", None), "value", getattr(it, "mode", "")) or "")
                    if "car" in mode and "walk" not in mode:
                        try:
                            km = float(getattr(it, "distance_km", 0) or 0)
                        except (TypeError, ValueError):
                            km = 0
                        try:
                            drive = time_to_minutes(getattr(it, "end_time", None) or "") - time_to_minutes(
                                getattr(it, "start_time", None) or ""
                            )
                        except Exception:
                            drive = 0
                        if km >= 10 or drive >= 30:
                            long_drive = True
            mine_today = any(
                _is_wieliczka_stop_name(getattr(it, "name", "") or "")
                and "rynek" not in _fold_place_label(getattr(it, "name", "") or "")
                for it in (day.items or [])
                if getattr(getattr(it, "type", None), "value", getattr(it, "type", ""))
                == ItemType.ATTRACTION.value
            )
            if has_rynek and only_short_rynek and long_drive:
                hits.append(f"J{num} D{day.day} [short_return] Wieliczka rynek")
            if mine_today:
                seen_mine = True
            shapes.append((int(day.day), real, not sat_kinds))
            group_now = str((payload.get("group") or {}).get("type") or "").lower()
            if "senior" in group_now:
                for it in day.items or []:
                    kind = getattr(getattr(it, "type", None), "value", getattr(it, "type", ""))
                    if kind != ItemType.ATTRACTION.value:
                        continue
                    folded = _fold_place_label(getattr(it, "name", "") or "")
                    if any(k in folded for k in ("bricks", "lego", "klock")):
                        hits.append(
                            f"J{num} D{day.day} [kids_for_seniors] {getattr(it, 'name', '')}"
                        )
            group = str((payload.get("group") or {}).get("type") or "").lower()
            pref_txt = " ".join(str(p) for p in (payload.get("preferences") or []))
            if (
                attr_count >= 5
                and ("kid" in group or "family" in group)
                and ("kids" in pref_txt or "nature" in pref_txt)
            ):
                for it in day.items or []:
                    kind = getattr(getattr(it, "type", None), "value", getattr(it, "type", ""))
                    if kind != ItemType.ATTRACTION.value:
                        continue
                    folded = _fold_place_label(getattr(it, "name", "") or "")
                    if "mocak" not in folded and "etnografic" not in folded:
                        continue
                    try:
                        dur = time_to_minutes(getattr(it, "end_time", None) or "") - time_to_minutes(
                            getattr(it, "start_time", None) or ""
                        )
                    except Exception:
                        dur = int(getattr(it, "duration_min", 0) or 0)
                    if dur >= 90:
                        hits.append(
                            f"J{num} D{day.day} [offpref_museum] "
                            f"{getattr(it, 'name', '')} {dur} min"
                        )

            def _meal_generic(text: str) -> bool:
                folded = _fold_place_label(text)
                if not folded:
                    return True
                return any(
                    k in folded
                    for k in ("przerw", "lunch", "kolacj", "posil", "obiad", "centrum")
                )

            prev_name = ""
            prev_idx = None
            ordered_items = list(day.items or [])
            for idx, it in enumerate(ordered_items):
                kind = getattr(getattr(it, "type", None), "value", getattr(it, "type", ""))
                if kind == ItemType.ATTRACTION.value:
                    prev_name = getattr(it, "name", "") or ""
                    prev_idx = idx
                    continue
                if kind not in (ItemType.LUNCH_BREAK.value, ItemType.DINNER_BREAK.value):
                    continue
                sug = ""
                for s in (getattr(it, "suggestions", None) or [])[:1]:
                    sug = (
                        s.get("name") if isinstance(s, dict)
                        else getattr(s, "name", "")
                    ) or ""
                label = getattr(it, "label", "") or ""
                loc = getattr(it, "location_context", "") or ""
                if sug:
                    if not _place_names_match(label, sug):
                        hits.append(
                            f"J{num} D{day.day} [meal_identity] {label!r} ≠ {sug!r}"
                        )
                    if loc and not _meal_generic(loc) and not _place_names_match(loc, sug):
                        hits.append(
                            f"J{num} D{day.day} [meal_identity] ctx {loc!r} ≠ {sug!r}"
                        )
                claimed = sug or (
                    label if not _meal_generic(label) else ""
                ) or (loc if not _meal_generic(loc) else "")
                body = prev_name
                arrived = False
                if prev_idx is not None:
                    for leg in ordered_items[prev_idx + 1:idx]:
                        leg_kind = getattr(getattr(leg, "type", None), "value", getattr(leg, "type", ""))
                        if leg_kind != ItemType.TRANSIT.value:
                            continue
                        dest = getattr(leg, "to_location", "") or ""
                        if claimed and _place_names_match(dest, claimed):
                            arrived = True
                        if dest and not _meal_generic(dest) and not is_parking_label(dest):
                            body = dest
                if claimed and body and not _place_names_match(claimed, body) and not arrived:
                    hits.append(
                        f"J{num} D{day.day} [meal_stranded] {claimed!r} przy {body!r}"
                    )
                if kind == ItemType.DINNER_BREAK.value:
                    for text in (label, loc, sug):
                        if not text or _meal_generic(text):
                            continue
                        if any(_place_names_match(text, attr) for attr in names):
                            hits.append(
                                f"J{num} D{day.day} [dinner_as_stop] {text!r}"
                            )
                            break
            title = getattr(day, "title", None) or ""
            body = title.split(" — ")[0]
            body = body.replace(" i więcej", "")
            pieces = []
            for chunk in body.split(","):
                for piece in chunk.split(" i "):
                    piece = piece.strip()
                    if piece and not piece.lower().startswith("dzień") and "spokoj" not in piece.lower():
                        pieces.append(piece)
            folded_names = [_fold_place_label(n) for n in names if n]
            for piece in pieces:
                folded = _fold_place_label(piece)
                if not folded:
                    continue
                if any(
                    folded == have or (
                        len(folded) >= 6 and len(have) >= 6
                        and (folded in have or have in folded)
                    )
                    for have in folded_names
                ):
                    continue
                hits.append(f"J{num} D{day.day} [title_miss] {piece}")
        if shapes and shapes[0][1] and any(row[2] for row in shapes[1:]):
            hits.append(f"J{num} D{shapes[0][0]} [day1_out] first day leaves Kraków")
        if len(shapes) >= 3 and shapes[1][1] and any(row[2] for row in shapes[2:]):
            hits.append(f"J{num} D{shapes[1][0]} [day2_out] second day leaves Kraków")

    if hits:
        Path(__file__).with_name("_gate379_hits.txt").write_text(
            "\n".join(hits), encoding="utf-8",
        )
    assert not hits, (
        "Kraków car/physics defects still in the client JSONs:\n"
        + "\n".join(hits)
    )


def _fix383_parking():
    from app.domain.models.plan import ParkingInfo, ParkingType

    return ParkingInfo(
        name="Parking",
        address="Kraków",
        parking_type=ParkingType.PAID,
        cost=None,
        walk_time_min=5,
        lat=50.06,
        lng=19.94,
    )


def _fix383_attr(name, start, end, lat, lng):
    from app.domain.models.plan import AttractionItem, TicketInfo

    sh, sm = (int(p) for p in start.split(":"))
    eh, em = (int(p) for p in end.split(":"))
    return AttractionItem(
        type=ItemType.ATTRACTION,
        poi_id="t",
        name=name,
        description_short=name,
        start_time=start,
        end_time=end,
        duration_min=(eh * 60 + em) - (sh * 60 + sm),
        lat=lat,
        lng=lng,
        address="Kraków",
        city="Kraków",
        cost_estimate=0,
        ticket_info=TicketInfo(ticket_normal=0, ticket_reduced=0),
        parking=_fix383_parking(),
    )


def _fix383_run(items, **ctx):
    from app.domain.models.plan import DayPlan

    base = {
        "requested_city": "Kraków",
        "day_start": "09:00",
        "day_end": "19:00",
        "travel_style": "balanced",
        "group_type": "solo",
        "date": "2026-02-20",
        "poi_pool": [],
        "preferences": ["history_mystery"],
    }
    base.update(ctx)
    day = DayPlan(day=1, date=str(base.get("date"))[:10], items=items)
    out = PlanService(None)._seal_fix383_krakow_client([day], base)
    return out[0].items


def test_fix383_repairs_mailed_shapes():
    from app.domain.models.plan import DinnerBreakItem, LunchBreakItem, TransitItem, TransitMode

    def _walk(start, end, frm, to, km):
        sh, sm = (int(p) for p in start.split(":"))
        eh, em = (int(p) for p in end.split(":"))
        return TransitItem(
            type=ItemType.TRANSIT,
            start_time=start,
            end_time=end,
            duration_min=(eh * 60 + em) - (sh * 60 + sm),
            mode=TransitMode.WALK,
            from_location=frm,
            to_location=to,
            distance_km=km,
            routing_source="estimated_walk",
        )

    def _car(start, end, frm, to, km):
        row = _walk(start, end, frm, to, km)
        return row.model_copy(update={"mode": TransitMode.CAR})

    def _dinner(start, end, label):
        sh, sm = (int(p) for p in start.split(":"))
        eh, em = (int(p) for p in end.split(":"))
        return DinnerBreakItem(
            type=ItemType.DINNER_BREAK,
            start_time=start,
            end_time=end,
            duration_min=(eh * 60 + em) - (sh * 60 + sm),
            label=label,
        )

    morning = _fix383_run(
        [
            _walk("09:00", "10:00", "Parking ul. Szpitalna", "Podziemia Rynku", 0.58),
            _fix383_attr("Podziemia Rynku", "10:00", "11:15", 50.0617, 19.9373),
        ],
        poi_pool=[{
            "name": "Teatr Groteska",
            "lat": 50.0648,
            "lng": 19.9435,
            "address": "Kraków",
            "city": "Kraków",
        }],
    )
    pod = next(it for it in morning if getattr(it, "name", "") == "Podziemia Rynku")
    hop = next(
        it for it in morning
        if getattr(it, "to_location", "") == "Podziemia Rynku"
    )
    assert pod.start_time == "10:00"
    assert hop.end_time == "10:00"
    assert int(hop.duration_min) <= walk_minutes(0.58) + 1
    first = time_to_minutes(morning[0].start_time)
    assert first <= 9 * 60 + 39

    lunch_items = _fix383_run([
        _fix383_attr("Sukiennice", "10:00", "11:30", 50.0616, 19.9373),
        LunchBreakItem(
            type=ItemType.LUNCH_BREAK,
            start_time="13:41",
            end_time="17:52",
            duration_min=251,
            label="Lunch / przerwa regeneracyjna",
        ),
        _dinner("18:30", "19:30", "Kolacja"),
    ])
    lunch = next(it for it in lunch_items if getattr(it, "type", None) == ItemType.LUNCH_BREAK)
    assert lunch.start_time == "13:41"
    assert time_to_minutes(lunch.end_time) - time_to_minutes(lunch.start_time) == 60

    wawel_items = _fix383_run([
        _fix383_attr("Smok Wawelski", "14:00", "14:20", 50.0547, 19.9338),
        _fix383_attr("Sukiennice", "15:00", "16:40", 50.0616, 19.9373),
        _walk("16:40", "16:51", "Sukiennice", "Zamek Królewski na Wawelu", 0.7),
        _fix383_attr("Zamek Królewski na Wawelu", "16:51", "18:37", 50.0540, 19.9354),
        _dinner("19:00", "19:45", "Kolacja"),
    ])
    names = [getattr(it, "name", "") for it in wawel_items]
    assert "Zamek Królewski na Wawelu" not in names
    assert "Smok Wawelski" in names

    castle_items = _fix383_run([
        _fix383_attr("Sukiennice", "15:00", "16:10", 50.0616, 19.9373),
        _car("16:10", "17:06", "Parking ul. Szpitalna", "Parking pod Zamkiem w Pieskowej Skale", 28.0),
        _fix383_attr("Zamek w Pieskowej Skale", "17:24", "19:27", 50.2443, 19.7801),
        _dinner("19:30", "20:00", "Kolacja"),
    ], day_end="20:00")
    castle_names = " ".join(getattr(it, "name", "") or "" for it in castle_items)
    castle_hops = " ".join(
        f"{getattr(it, 'from_location', '')} {getattr(it, 'to_location', '')}"
        for it in castle_items
    )
    assert "Pieskow" not in castle_names and "pieskow" not in castle_names.lower()
    assert "pieskow" not in _fold_place_label(castle_hops)
    assert "Sukiennice" in castle_names

    kept = _fix383_run([
        _car("09:10", "10:06", "Parking ul. Szpitalna", "Parking pod Zamkiem w Pieskowej Skale", 28.0),
        _fix383_attr("Zamek w Pieskowej Skale", "10:10", "12:00", 50.2443, 19.7801),
    ])
    assert any(getattr(it, "name", "") == "Zamek w Pieskowej Skale" for it in kept)

    garden_items = _fix383_run(
        [
            _fix383_attr("Ogród Doświadczeń", "11:00", "12:30", 50.064, 19.94),
            _fix383_attr("Sukiennice", "13:30", "15:00", 50.0616, 19.9373),
        ],
        date="2026-02-23",
    )
    assert not any("Doświadczeń" in (getattr(it, "name", "") or "") for it in garden_items)
    assert any(getattr(it, "name", "") == "Sukiennice" for it in garden_items)

    named = _fix383_run([
        _fix383_attr("Sukiennice", "15:00", "16:20", 50.0616, 19.9373),
        _dinner("18:00", "19:00", "Muzeum Narodowe w Krakowie"),
    ])
    dinner = next(it for it in named if getattr(it, "type", None) == ItemType.DINNER_BREAK)
    assert dinner.label == "Kolacja"

    park_items = _fix383_run(
        [
            _fix383_attr("Park Lotników", "14:47", "16:02", 50.0790, 19.9910),
            _dinner("17:00", "18:00", "Kolacja"),
        ],
        group_type="family_kids",
        preferences=["kids_attractions", "nature_landscape"],
        poi_pool=[{
            "name": "Muzeum Lotnictwa Polskiego",
            "lat": 50.0794,
            "lng": 19.9920,
            "address": "Kraków",
            "city": "Kraków",
        }],
    )
    dinner = next(it for it in park_items if getattr(it, "type", None) == ItemType.DINNER_BREAK)
    ends = [
        time_to_minutes(it.end_time)
        for it in park_items
        if getattr(it, "name", None)
    ]
    assert any(getattr(it, "name", "") == "Park Lotników" for it in park_items)
    assert time_to_minutes(dinner.start_time) - max(ends) <= 20


def _fix384_run(items, **ctx):
    from app.domain.models.plan import DayPlan

    base = {
        "requested_city": "Kraków",
        "day_start": "09:00",
        "day_end": "19:00",
        "travel_style": "balanced",
        "group_type": "solo",
        "date": "2026-02-20",
        "poi_pool": [],
        "preferences": ["history_mystery"],
        "has_car": True,
        "fix384_keep": True,
    }
    base.update(ctx)
    day = DayPlan(day=1, date=str(base.get("date"))[:10], items=items)
    out = PlanService(None)._seal_fix384_krakow_client([day], base)
    return out[0].items


def test_fix384_repairs_mailed_shapes():
    from app.domain.models.plan import DinnerBreakItem, LunchBreakItem, TransitItem, TransitMode

    def _walk(start, end, frm, to, km):
        sh, sm = (int(p) for p in start.split(":"))
        eh, em = (int(p) for p in end.split(":"))
        return TransitItem(
            type=ItemType.TRANSIT,
            start_time=start,
            end_time=end,
            duration_min=(eh * 60 + em) - (sh * 60 + sm),
            mode=TransitMode.WALK,
            from_location=frm,
            to_location=to,
            distance_km=km,
            routing_source="estimated_walk",
        )

    def _car(start, end, frm, to, km):
        row = _walk(start, end, frm, to, km)
        return row.model_copy(update={"mode": TransitMode.CAR, "routing_source": "estimated_car"})

    def _lunch(start, end):
        sh, sm = (int(p) for p in start.split(":"))
        eh, em = (int(p) for p in end.split(":"))
        return LunchBreakItem(
            type=ItemType.LUNCH_BREAK,
            start_time=start,
            end_time=end,
            duration_min=(eh * 60 + em) - (sh * 60 + sm),
            label="Lunch",
        )

    def _dinner(start, end):
        sh, sm = (int(p) for p in start.split(":"))
        eh, em = (int(p) for p in end.split(":"))
        return DinnerBreakItem(
            type=ItemType.DINNER_BREAK,
            start_time=start,
            end_time=end,
            duration_min=(eh * 60 + em) - (sh * 60 + sm),
            label="Kolacja",
        )

    def _names(items):
        return " ".join(getattr(it, "name", "") or "" for it in items)

    family = _fix384_run(
        [
            _fix383_attr("Smok Wawelski", "09:20", "09:35", 50.053, 19.933),
            _fix383_attr("Bricks & Figs - muzeum klocków LEGO", "10:00", "11:30", 50.062, 19.940),
            _fix383_attr("Świat w Budowie - Wystawa klocków LEGO", "11:40", "12:03", 50.063, 19.941),
            _fix383_attr("Muzeum Etnograficzne im. Seweryna Udzieli", "12:20", "13:10", 50.050, 19.945),
            _fix383_attr("Kładka Ojca Bernatka", "13:20", "13:40", 50.048, 19.950),
            _fix383_attr("Sukiennice", "14:00", "15:00", 50.0616, 19.9373),
            _dinner("18:00", "19:00"),
        ],
        group_type="family_kids",
        preferences=["kids_attractions", "nature_landscape"],
        travel_style="balanced",
    )
    folded = _fold_place_label(_names(family))
    assert "etnografic" not in folded
    assert "kladka" not in folded and "bernat" not in folded
    assert "swiat w budowie" not in folded
    assert "bricks" in folded
    assert "smok" in folded and "sukiennic" in folded
    assert sum(1 for it in family if getattr(it, "type", None) == ItemType.ATTRACTION) <= 5

    sunday = _fix384_run(
        [
            _fix383_attr("Muzeum Geologiczne w Krakowie", "11:00", "12:30", 50.054, 19.935),
            _fix383_attr("Sukiennice", "13:00", "14:30", 50.0616, 19.9373),
            _dinner("18:00", "19:00"),
        ],
        date="2026-02-22",
        poi_pool=[{
            "name": "Muzeum Geologiczne w Krakowie",
            "lat": 50.054,
            "lng": 19.935,
            "opening_hours_seasonal": [{
                "date_from": "01-01",
                "date_to": "12-31",
                "mon": "10:00-15:00",
                "tue": "10:00-15:00",
                "wed": "10:00-15:00",
                "thu": "10:00-15:00",
                "fri": "10:00-15:00",
                "sat": "10:00-14:00",
                "sun": "closed",
            }],
        }],
    )
    assert "Geologiczne" not in _names(sunday)
    assert "Sukiennice" in _names(sunday)

    monday = _fix384_run(
        [
            _fix383_attr("Muzeum Obwarzanka", "14:29", "16:34", 50.062, 19.940),
            _fix383_attr("Sukiennice", "16:45", "17:45", 50.0616, 19.9373),
            _dinner("19:00", "19:45"),
        ],
        date="2026-02-23",
        poi_pool=[{
            "name": "Muzeum Obwarzanka",
            "lat": 50.062,
            "lng": 19.940,
            "opening_hours_seasonal": [{
                "date_from": "01-01",
                "date_to": "12-31",
                "mon": "09:00-16:00",
                "tue": "09:00-16:00",
                "wed": "09:00-16:00",
                "thu": "09:00-16:00",
                "fri": "09:00-16:00",
                "sat": "10:00-17:00",
                "sun": "10:00-17:00",
            }],
        }],
    )
    obwarzanek = next(it for it in monday if "Obwarzan" in (getattr(it, "name", "") or ""))
    start = time_to_minutes(obwarzanek.start_time)
    end = time_to_minutes(obwarzanek.end_time)
    assert end <= 16 * 60
    assert 60 <= end - start <= 65
    assert "Sukiennice" in _names(monday)

    lunch_items = _fix384_run(
        [
            _fix383_attr("Sukiennice", "13:00", "14:00", 50.0616, 19.9373),
            _fix383_attr("Kładka Ojca Bernatka", "14:40", "15:05", 50.048, 19.950),
            _lunch("15:21", "16:21"),
            _fix383_attr("Podziemia Rynku", "16:40", "17:50", 50.0617, 19.9373),
            _dinner("19:40", "20:20"),
        ],
        group_type="friends",
        travel_style="adventure",
        preferences=["underground", "history_mystery"],
    )
    lunch = next(it for it in lunch_items if getattr(it, "type", None) == ItemType.LUNCH_BREAK)
    assert time_to_minutes(lunch.start_time) <= 15 * 60
    assert "Sukiennice" in _names(lunch_items)

    loop = _fix384_run(
        [
            _fix383_attr("Plac Jana Matejki", "09:20", "10:00", 50.0640, 19.9430),
            _walk("10:00", "10:12", "Plac Jana Matejki", "Parking ul. Szpitalna", 0.4),
            _walk("10:12", "10:24", "Parking ul. Szpitalna", "Podziemia Rynku", 0.5),
            _fix383_attr("Podziemia Rynku", "10:24", "11:30", 50.0617, 19.9373),
            _dinner("18:00", "19:00"),
        ],
        group_type="couples",
        travel_style="balanced",
    )
    hops = [
        (getattr(it, "from_location", ""), getattr(it, "to_location", ""))
        for it in loop
        if getattr(it, "type", None) == ItemType.TRANSIT
    ]
    assert not any(is_parking_label(dest) and is_parking_label(frm) is False and "Szpitalna" in dest for frm, dest in hops)
    assert any("Matejki" in frm and "Podziemia" in dest for frm, dest in hops)

    lead = _fix384_run(
        [
            _walk("09:10", "09:25", "Parking Czyżyny (al. Pokoju)", "Muzeum Lotnictwa Polskiego", 0.6),
            _fix383_attr("Muzeum Lotnictwa Polskiego", "09:25", "11:00", 50.0794, 19.9920),
            _dinner("18:00", "19:00"),
        ],
    )
    cars = [
        it for it in lead
        if getattr(it, "type", None) == ItemType.TRANSIT
        and "car" in str(getattr(getattr(it, "mode", None), "value", getattr(it, "mode", "")) or "")
    ]
    assert cars and "Czyżyny" in (cars[0].to_location or "")
    assert float(cars[0].distance_km or 0) >= 0.80

    dropped = _fix384_run(
        [
            _car("09:30", "11:06", "Parking ul. Szpitalna", "Parking pod Zamkiem w Pieskowej Skale", 40.0),
            _fix383_attr("Zamek Pieskowa Skała", "11:10", "12:10", 50.2443, 19.7801),
            _car("12:10", "13:46", "Parking pod Zamkiem w Pieskowej Skale", "Parking ul. Szpitalna", 40.0),
            _fix383_attr("Sukiennice", "14:10", "15:30", 50.0616, 19.9373),
            _dinner("18:00", "19:00"),
        ],
    )
    dropped_names = _names(dropped).lower()
    dropped_hops = " ".join(
        f"{getattr(it, 'from_location', '')} {getattr(it, 'to_location', '')}" for it in dropped
    ).lower()
    assert "pieskow" not in dropped_names and "pieskow" not in _fold_place_label(dropped_hops)
    assert "Sukiennice" in _names(dropped)

    kept = _fix384_run(
        [
            _car("09:10", "09:40", "Parking ul. Szpitalna", "Parking pod Zamkiem w Pieskowej Skale", 12.0),
            _fix383_attr("Zamek Pieskowa Skała", "09:45", "11:30", 50.2443, 19.7801),
            _dinner("18:00", "19:00"),
        ],
    )
    assert any(getattr(it, "name", "") == "Zamek Pieskowa Skała" for it in kept)


def _fix385_run(items, **ctx):
    from app.domain.models.plan import DayPlan

    base = {
        "requested_city": "Kraków",
        "day_start": "09:00",
        "day_end": "19:00",
        "travel_style": "balanced",
        "group_type": "solo",
        "date": "2026-02-20",
        "poi_pool": [],
        "preferences": ["museum_heritage"],
        "has_car": True,
        "fix385_keep": True,
    }
    base.update(ctx)
    day = DayPlan(day=1, date=str(base.get("date"))[:10], items=items)
    out = PlanService(None)._seal_fix385_krakow_client([day], base)
    return out[0].items


def test_fix385_repairs_mailed_shapes():
    from app.domain.models.plan import DinnerBreakItem, LunchBreakItem, TransitItem, TransitMode

    def _walk(start, end, frm, to, km):
        sh, sm = (int(p) for p in start.split(":"))
        eh, em = (int(p) for p in end.split(":"))
        return TransitItem(
            type=ItemType.TRANSIT,
            start_time=start,
            end_time=end,
            duration_min=(eh * 60 + em) - (sh * 60 + sm),
            mode=TransitMode.WALK,
            from_location=frm,
            to_location=to,
            distance_km=km,
            routing_source="estimated_walk",
        )

    def _car(start, end, frm, to, km):
        row = _walk(start, end, frm, to, km)
        return row.model_copy(update={"mode": TransitMode.CAR, "routing_source": "estimated_car"})

    def _lunch(start, end):
        sh, sm = (int(p) for p in start.split(":"))
        eh, em = (int(p) for p in end.split(":"))
        return LunchBreakItem(
            type=ItemType.LUNCH_BREAK,
            start_time=start,
            end_time=end,
            duration_min=(eh * 60 + em) - (sh * 60 + sm),
            label="Lunch",
        )

    def _dinner(start, end):
        sh, sm = (int(p) for p in start.split(":"))
        eh, em = (int(p) for p in end.split(":"))
        return DinnerBreakItem(
            type=ItemType.DINNER_BREAK,
            start_time=start,
            end_time=end,
            duration_min=(eh * 60 + em) - (sh * 60 + sm),
            label="Kolacja",
        )

    def _names(items):
        return " ".join(getattr(it, "name", "") or "" for it in items)

    family = _fix385_run(
        [
            _fix383_attr("Bricks & Figs - muzeum klocków LEGO", "10:00", "11:30", 50.049, 19.962),
            _walk("11:30", "11:40", "Bricks & Figs - muzeum klocków LEGO", "Świat w Budowie - Wystawa klocków LEGO", 0.3),
            _fix383_attr("Świat w Budowie - Wystawa klocków LEGO", "11:40", "12:03", 50.050, 19.963),
            _dinner("18:00", "19:00"),
        ],
        group_type="family_kids",
        preferences=["kids_attractions", "nature_landscape"],
    )
    folded = _fold_place_label(_names(family))
    assert "swiat w budowie" not in folded
    assert "bricks" in folded

    sunday = _fix385_run(
        [
            _fix383_attr("Muzeum Geologiczne w Krakowie", "11:00", "12:30", 50.064, 19.922),
            _fix383_attr("Pałac Krzysztofory", "13:14", "14:30", 50.0627, 19.9366),
            _dinner("18:00", "19:00"),
        ],
        date="2026-02-22",
        poi_pool=[{
            "name": "Muzeum Geologiczne w Krakowie",
            "lat": 50.064,
            "lng": 19.922,
            "opening_hours_seasonal": [{
                "date_from": "01-01",
                "date_to": "12-31",
                "mon": "10:00-15:00",
                "tue": "10:00-15:00",
                "wed": "10:00-15:00",
                "thu": "10:00-15:00",
                "fri": "10:00-15:00",
                "sat": "10:00-14:00",
                "sun": "closed",
            }],
        }],
    )
    assert "Geologiczne" not in _names(sunday)
    assert "Krzysztofory" in _names(sunday)

    loop = _fix385_run(
        [
            _walk("10:00", "10:08", "Parking ul. Szpitalna", "plac Jana Matejki", 0.4),
            _fix383_attr("plac Jana Matejki", "10:08", "11:00", 50.0618, 19.9430),
            _walk("11:00", "11:08", "plac Jana Matejki", "Parking ul. Szpitalna", 0.4),
            _walk("11:08", "11:20", "Parking ul. Szpitalna", "Podziemia Rynku", 0.5),
            _fix383_attr("Podziemia Rynku", "11:20", "12:30", 50.0616, 19.9378),
            _dinner("18:00", "19:00"),
        ],
        group_type="friends",
        travel_style="adventure",
        preferences=["underground", "history_mystery"],
    )
    hops = [
        (getattr(it, "from_location", ""), getattr(it, "to_location", ""))
        for it in loop
        if getattr(getattr(it, "type", None), "value", getattr(it, "type", "")) == ItemType.TRANSIT.value
    ]
    assert not any(is_parking_label(to or "") and _place_names_match(frm or "", "plac Jana Matejki") for frm, to in hops)
    assert any("Podziemia" in (to or "") for _frm, to in hops)

    parks = _fix385_run(
        [
            _fix383_attr("Błonia Krakowskie", "11:00", "11:50", 50.0605, 19.9095),
            _walk("11:50", "11:54", "Błonia Krakowskie", "Parking ul. Piastowska 18", 0.2),
            _car("11:54", "12:02", "Parking ul. Piastowska 18", "Parking przy Muzeum (al. 3 Maja)", 1.2),
            _walk("12:02", "12:08", "Parking przy Muzeum (al. 3 Maja)", "Park im. Henryka Jordana", 0.3),
            _fix383_attr("Park im. Henryka Jordana", "12:08", "13:20", 50.0628, 19.9148),
            _dinner("18:00", "19:00"),
        ],
        travel_style="relax",
        group_type="solo",
        preferences=["nature_landscape", "relaxation"],
    )
    assert not any(
        getattr(getattr(it, "mode", None), "value", getattr(it, "mode", "")) == "car"
        for it in parks
    )
    assert "Jordana" in _names(parks) and "Błonia" in _names(parks)

    lunch_items = _fix385_run(
        [
            _fix383_attr("Sukiennice", "12:00", "14:00", 50.0616, 19.9373),
            _walk("14:00", "14:10", "Sukiennice", "Wieża Ratuszowa", 0.2),
            _fix383_attr("Wieża Ratuszowa", "14:10", "15:10", 50.0617, 19.9364),
            _walk("15:10", "15:21", "Wieża Ratuszowa", "Lunch", 0.2),
            _lunch("15:21", "16:01"),
            _dinner("18:30", "19:15"),
        ],
        group_type="friends",
        travel_style="adventure",
        preferences=["underground", "history_mystery"],
    )
    lunch = next(
        it for it in lunch_items
        if getattr(getattr(it, "type", None), "value", getattr(it, "type", "")) == ItemType.LUNCH_BREAK.value
    )
    assert time_to_minutes(lunch.start_time) <= 15 * 60
    assert "Ratuszowa" not in _names(lunch_items)

    bricks = _fix385_run(
        [
            _fix383_attr("Muzeum Sztuki Współczesnej MOCAK", "14:30", "16:00", 50.047, 19.961),
            _walk("16:00", "16:06", "Muzeum Sztuki Współczesnej MOCAK", "Bricks & Figs - muzeum klocków LEGO", 0.44),
            _fix383_attr("Bricks & Figs - muzeum klocków LEGO", "16:06", "17:20", 50.049, 19.962),
            _dinner("17:40", "18:25"),
        ],
        group_type="couples",
        preferences=["nature_landscape", "local_food_experience", "museum_heritage"],
    )
    assert "bricks" not in _fold_place_label(_names(bricks))
    assert "MOCAK" in _names(bricks)

    idle = _fix385_run(
        [
            _fix383_attr("Sukiennice", "14:00", "15:31", 50.0616, 19.9373),
            _walk("15:31", "15:33", "Sukiennice", "plac Jana Matejki", 0.15),
            _fix383_attr("plac Jana Matejki", "16:14", "17:00", 50.0618, 19.9430),
            _dinner("18:00", "19:00"),
        ],
    )
    matejko = next(it for it in idle if "Matejki" in (getattr(it, "name", "") or ""))
    assert time_to_minutes(matejko.start_time) <= 15 * 60 + 40

    castle = _fix385_run(
        [
            _car("09:00", "09:48", "Parking ul. Szpitalna", "Parking pod Zamkiem w Pieskowej Skale", 28.0),
            _fix383_attr("Zamek w Ojcowie", "09:55", "11:16", 50.221, 19.831),
            _car("11:16", "12:04", "Parking pod Zamkiem w Pieskowej Skale", "Parking ul. Szpitalna", 28.0),
            _fix383_attr("MNK Sukiennice", "14:10", "15:30", 50.0616, 19.9373),
            _dinner("18:00", "19:00"),
        ],
    )
    assert "Ojcowie" not in _names(castle) and "Pieskow" not in _names(castle)
    assert "Sukiennice" in _names(castle)
