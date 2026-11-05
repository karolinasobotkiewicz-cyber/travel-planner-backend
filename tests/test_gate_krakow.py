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
                    selected = [str(m).lower() for m in (payload.get("transport_modes") or [])]
                    if (
                        ("public" in mode or "transit" in mode)
                        and selected
                        and not any("public" in m or "transit" in m for m in selected)
                    ):
                        # FIX #391: a car-only traveller never gets a bus/tram leg.
                        hits.append(
                            f"J{num} D{day.day} [offmode_transport] "
                            f"{getattr(it, 'from_location', '')} → "
                            f"{getattr(it, 'to_location', '')}"
                        )
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
                    known_free = (
                        "maczuga herkulesa" in folded
                        or ("plac" in folded and "bohater" in folded and "getta" in folded)
                    )
                    if known_free:
                        cost = int(getattr(it, "cost_estimate", 0) or 0)
                        ticket = getattr(it, "ticket_info", None)
                        normal = int(
                            getattr(ticket, "ticket_normal", 0) or 0
                        ) if ticket else 0
                        reduced = int(
                            getattr(ticket, "ticket_reduced", 0) or 0
                        ) if ticket else 0
                        if cost or normal or reduced:
                            hits.append(
                                f"J{num} D{day.day} [free_place_cost] "
                                f"{nm} {cost}/{normal}/{reduced} zł"
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
            if family_kn and len(car_lots) > 4:
                hits.append(
                    f"J{num} D{day.day} [family_lots] {len(car_lots)} parkings"
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
            content_valley = False
            transit_min = 0
            ojcow_visit = 0
            ojcow_drive = 0
            ojcow_stops = 0
            for it in day.items or []:
                kind = getattr(getattr(it, "type", None), "value", getattr(it, "type", ""))
                if kind == ItemType.ATTRACTION.value and _is_ojcow_stop_name(getattr(it, "name", "") or ""):
                    ojcow_stops += 1
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
                if (
                    content_valley
                    and kind in (
                        ItemType.ATTRACTION.value,
                        ItemType.LUNCH_BREAK.value,
                        ItemType.DINNER_BREAK.value,
                    )
                    and content_end is not None and st is not None
                    and st - content_end - transit_min >= 40
                ):
                    hits.append(
                        f"J{num} D{day.day} [valley_gap] {content_end}->{st}"
                    )
                if kind == ItemType.LUNCH_BREAK.value and st is not None and st > lunch_by + 30:
                    hits.append(
                        f"J{num} D{day.day} [late_group_lunch] {getattr(it, 'start_time', '')}"
                    )
                if (
                    kind == ItemType.LUNCH_BREAK.value
                    and st is not None and en is not None
                    and en - st > 75
                ):
                    hits.append(
                        f"J{num} D{day.day} [long_lunch] "
                        f"{getattr(it, 'start_time', '')}-"
                        f"{getattr(it, 'end_time', '')}"
                    )
                content_end = en if en is not None else st
                content_kind = kind
                content_valley = (
                    kind == ItemType.ATTRACTION.value
                    and _is_ojcow_stop_name(getattr(it, "name", "") or "")
                )
                transit_min = 0
            if ojcow_visit:
                rows = list(day.items or [])
                for oi, it in enumerate(rows):
                    kind_o = getattr(getattr(it, "type", None), "value", getattr(it, "type", ""))
                    if kind_o != ItemType.ATTRACTION.value or not _is_ojcow_stop_name(getattr(it, "name", "") or ""):
                        continue
                    for step in (-1, 1):
                        j = oi + step
                        while 0 <= j < len(rows):
                            other = rows[j]
                            kind_j = getattr(getattr(other, "type", None), "value", getattr(other, "type", ""))
                            if kind_j == ItemType.ATTRACTION.value:
                                break
                            if kind_j == ItemType.TRANSIT.value:
                                mode_j = str(getattr(getattr(other, "mode", None), "value", getattr(other, "mode", "")) or "")
                                if "car" in mode_j and "walk" not in mode_j:
                                    try:
                                        near_km = float(getattr(other, "distance_km", 0) or 0)
                                    except (TypeError, ValueError):
                                        near_km = 0.0
                                    blob_j = _fold_place_label(
                                        f"{getattr(other, 'from_location', '')} {getattr(other, 'to_location', '')}"
                                    )
                                    near_min = int(getattr(other, "duration_min", 0) or 0)
                                    already = near_km >= 20 or any(
                                        stem in blob_j for stem in ("ojcow", "pieskow", "maczuga")
                                    )
                                    if not already and near_min >= 20:
                                        ojcow_drive += near_min
                                    break
                            j += step
            if ojcow_visit and ojcow_drive > ojcow_visit:
                hits.append(
                    f"J{num} D{day.day} [far_ojcow] drive {ojcow_drive} min / visit {ojcow_visit} min"
                )
            if ojcow_stops < 2 and ojcow_drive >= 40 and ojcow_drive > ojcow_visit:
                hits.append(
                    f"J{num} D{day.day} [thin_ojcow] drive {ojcow_drive} min / visit {ojcow_visit} min"
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


def _fix386_run(items, **ctx):
    from app.domain.models.plan import DayPlan

    base = {
        "requested_city": "Kraków",
        "day_start": "09:00",
        "day_end": "20:00",
        "travel_style": "balanced",
        "group_type": "solo",
        "date": "2026-02-20",
        "poi_pool": [],
        "preferences": ["museum_heritage"],
        "has_car": True,
        "fix386_keep": True,
    }
    base.update(ctx)
    day = DayPlan(day=1, date=str(base.get("date"))[:10], items=items)
    out = PlanService(None)._seal_fix386_krakow_client([day], base)
    return out[0].items


def test_fix386_repairs_mailed_shapes():
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

    def _attr_count(items):
        return sum(
            1 for it in items
            if getattr(getattr(it, "type", None), "value", getattr(it, "type", "")) == ItemType.ATTRACTION.value
        )

    family = _fix386_run(
        [
            _car("09:00", "09:08", "Parking Galeria Krakowska (ul. Pawia 5)", "Parking ul. Szpitalna", 1.2),
            _walk("09:08", "09:14", "Parking ul. Szpitalna", "Zamek Królewski na Wawelu", 0.3),
            _fix383_attr("Zamek Królewski na Wawelu", "09:14", "10:14", 50.0540, 19.9350),
            _walk("10:14", "10:20", "Zamek Królewski na Wawelu", "Kładka Ojca Bernatka", 0.3),
            _fix383_attr("Kładka Ojca Bernatka", "10:20", "10:35", 50.0548, 19.9360),
            _walk("10:35", "10:41", "Kładka Ojca Bernatka", "Sukiennice", 0.3),
            _fix383_attr("Sukiennice", "10:41", "11:21", 50.0556, 19.9370),
            _car("11:21", "11:30", "Parking ul. Szpitalna", "Parking plac Na Groblach (pod Wawelem)", 1.4),
            _walk("11:30", "11:36", "Parking plac Na Groblach (pod Wawelem)", "Muzeum Etnograficzne", 0.3),
            _fix383_attr("Muzeum Etnograficzne", "11:36", "12:16", 50.0564, 19.9380),
            _walk("12:16", "12:22", "Muzeum Etnograficzne", "Planty Krakowskie", 0.3),
            _fix383_attr("Planty Krakowskie", "12:22", "13:02", 50.0572, 19.9390),
            _car("13:02", "13:12", "Parking plac Na Groblach (pod Wawelem)", "Parking Zabłocie (ul. Przemysłowa)", 2.4),
            _walk("13:12", "13:18", "Parking Zabłocie (ul. Przemysłowa)", "Rynek Główny", 0.3),
            _fix383_attr("Rynek Główny", "13:18", "13:58", 50.0580, 19.9400),
            _walk("13:58", "14:04", "Rynek Główny", "Kościół Mariacki", 0.25),
            _fix383_attr("Kościół Mariacki", "14:04", "14:44", 50.0586, 19.9408),
            _walk("14:44", "14:50", "Kościół Mariacki", "Barbakan", 0.25),
            _fix383_attr("Barbakan", "14:50", "15:20", 50.0592, 19.9416),
            _dinner("18:00", "19:00"),
        ],
        group_type="family_kids",
        preferences=["kids_attractions", "nature_landscape"],
        travel_style="balanced",
    )
    folded = _fold_place_label(_names(family))
    assert "bernatka" not in folded
    assert "etnografic" not in folded
    assert _attr_count(family) <= 5
    assert "Wawel" in _names(family)
    lots = {
        _fold_place_label(getattr(it, "to_location", "") or "")
        for it in family
        if getattr(getattr(it, "mode", None), "value", getattr(it, "mode", "")) == "car"
        and is_parking_label(getattr(it, "to_location", "") or "")
    }
    assert len(lots) <= 2

    lego = _fix386_run(
        [
            _fix383_attr("Bricks & Figs - muzeum klocków LEGO", "10:00", "11:30", 50.0490, 19.9620),
            _walk("11:30", "11:36", "Bricks & Figs - muzeum klocków LEGO", "Świat w Budowie - Wystawa klocków LEGO", 0.2),
            _fix383_attr("Świat w Budowie - Wystawa klocków LEGO", "11:36", "11:59", 50.0500, 19.9630),
            _walk("11:59", "12:05", "Świat w Budowie - Wystawa klocków LEGO", "Planty Krakowskie", 0.2),
            _fix383_attr("Planty Krakowskie", "12:05", "12:50", 50.0508, 19.9638),
            _dinner("18:00", "19:00"),
        ],
        group_type="family_kids",
        preferences=["kids_attractions", "nature_landscape"],
    )
    assert "swiat w budowie" not in _fold_place_label(_names(lego))
    assert "bricks" in _fold_place_label(_names(lego))

    lunch_items = _fix386_run(
        [
            _fix383_attr("Sukiennice", "12:00", "14:00", 50.0616, 19.9373),
            _walk("14:00", "14:10", "Sukiennice", "Wieża Ratuszowa", 0.2),
            _fix383_attr("Wieża Ratuszowa", "14:10", "15:10", 50.0617, 19.9364),
            _walk("15:10", "15:21", "Wieża Ratuszowa", "Lunch", 0.2),
            _lunch("15:21", "16:21"),
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
    dinner = next(
        it for it in lunch_items
        if getattr(getattr(it, "type", None), "value", getattr(it, "type", "")) == ItemType.DINNER_BREAK.value
    )
    assert time_to_minutes(lunch.start_time) <= 15 * 60 + 15
    assert lunch.end_time == "16:21"
    assert dinner.start_time == "18:30"
    assert "Ratuszowa" in _names(lunch_items)

    early = _fix386_run(
        [
            _fix383_attr("Sukiennice", "12:00", "14:00", 50.0616, 19.9373),
            _walk("14:00", "14:10", "Sukiennice", "Lunch", 0.2),
            _lunch("14:17", "15:00"),
            _dinner("18:00", "19:00"),
        ],
        group_type="couples",
        travel_style="relax",
        preferences=["local_food_experience", "relaxation"],
    )
    early_lunch = next(
        it for it in early
        if getattr(getattr(it, "type", None), "value", getattr(it, "type", "")) == ItemType.LUNCH_BREAK.value
    )
    assert early_lunch.start_time == "14:17"

    castle = _fix386_run(
        [
            _car("09:20", "09:50", "Parking ul. Szpitalna", "Parking ul. Krupnicza", 12.0),
            _fix383_attr("Zamek w Ojcowie", "09:55", "10:45", 50.221, 19.831),
            _car("10:45", "11:15", "Parking ul. Krupnicza", "Parking ul. Szpitalna", 12.0),
            _fix383_attr("Sukiennice", "12:30", "14:00", 50.0616, 19.9373),
            _dinner("18:00", "19:00"),
        ],
        group_type="couples",
        preferences=["nature_landscape", "local_food_experience", "museum_heritage"],
    )
    kept = next((it for it in castle if "Ojcowie" in (getattr(it, "name", "") or "")), None)
    if kept is not None:
        assert _span_minutes(kept) > 60
    else:
        assert "Sukiennice" in _names(castle)

    home = _fix386_run(
        [
            _car("09:00", "09:10", "Parking Galeria Krakowska (ul. Pawia 5)", "Parking ul. Szpitalna", 1.1),
            _walk("09:10", "09:16", "Parking ul. Szpitalna", "Sukiennice", 0.3),
            _fix383_attr("Sukiennice", "09:16", "11:00", 50.0670, 19.9455),
            _walk("11:00", "11:08", "Sukiennice", "Lunch", 0.2),
            _lunch("11:08", "11:50"),
            _walk("12:10", "12:25", "Lunch", "Parking plac Na Groblach (pod Wawelem)", 1.1),
            _car("12:25", "12:48", "Parking plac Na Groblach (pod Wawelem)", "Parking Zabłocie (ul. Przemysłowa)", 3.2),
            _walk("12:48", "12:56", "Parking Zabłocie (ul. Przemysłowa)", "Muzeum Sztuki Współczesnej MOCAK", 0.4),
            _fix383_attr("Muzeum Sztuki Współczesnej MOCAK", "13:10", "15:00", 50.0476, 19.9615),
            _dinner("18:00", "19:00"),
        ],
        group_type="couples",
        travel_style="balanced",
        preferences=["nature_landscape", "museum_heritage"],
    )
    mocak = next(it for it in home if "MOCAK" in (getattr(it, "name", "") or ""))
    assert mocak.start_time == "13:10"
    departures = [
        getattr(it, "from_location", "") or ""
        for it in home
        if getattr(getattr(it, "mode", None), "value", getattr(it, "mode", "")) == "car"
    ]
    assert not any("Groblach" in frm for frm in departures)
    assert any("Szpitalna" in frm for frm in departures)


def _span_minutes(it):
    return time_to_minutes(it.end_time) - time_to_minutes(it.start_time)


def _fix387_run(items, **ctx):
    from app.domain.models.plan import DayPlan

    base = {
        "requested_city": "Kraków",
        "day_start": "09:00",
        "day_end": "20:00",
        "travel_style": "balanced",
        "group_type": "couples",
        "date": "2026-02-22",
        "poi_pool": [],
        "preferences": ["nature_landscape", "museum_heritage"],
        "has_car": True,
        "fix387_keep": True,
    }
    base.update(ctx)
    day = DayPlan(day=1, date=str(base.get("date"))[:10], items=items)
    out = PlanService(None)._seal_fix387_krakow_client([day], base)
    return out[0].items


def test_fix387_repairs_mailed_shapes():
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

    def _lunch(start, end, label, lat, lng):
        sh, sm = (int(p) for p in start.split(":"))
        eh, em = (int(p) for p in end.split(":"))
        return LunchBreakItem(
            type=ItemType.LUNCH_BREAK,
            start_time=start,
            end_time=end,
            duration_min=(eh * 60 + em) - (sh * 60 + sm),
            label=label,
            suggestions=[{"id": "t", "name": label, "lat": lat, "lng": lng}],
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

    def _kind(it):
        return getattr(getattr(it, "type", None), "value", getattr(it, "type", ""))

    def _valley_idle(items):
        holes = []
        content_end = None
        content_valley = False
        transit = 0
        for it in items:
            if _kind(it) == ItemType.TRANSIT.value:
                transit += int(getattr(it, "duration_min", 0) or 0)
                continue
            if _kind(it) not in (
                ItemType.ATTRACTION.value, ItemType.LUNCH_BREAK.value, ItemType.DINNER_BREAK.value,
            ):
                continue
            try:
                start = time_to_minutes(it.start_time)
                end = time_to_minutes(it.end_time)
            except Exception:
                start = end = None
            if content_valley and content_end is not None and start is not None:
                holes.append(start - content_end - transit)
            content_end = end if end is not None else start
            content_valley = (
                _kind(it) == ItemType.ATTRACTION.value
                and _is_ojcow_stop_name(getattr(it, "name", "") or "")
            )
            transit = 0
        return holes

    gap = _fix387_run(
        [
            _fix383_attr("Zamek Pieskowa Skała", "13:00", "15:22", 50.2451641, 19.7788312),
            _dinner("17:00", "18:00"),
        ],
        group_type="family_kids",
        preferences=["kids_attractions", "nature_landscape"],
        travel_style="balanced",
    )
    pieskowa = next(it for it in gap if "Pieskowa" in (getattr(it, "name", "") or ""))
    dinner = next(it for it in gap if _kind(it) == ItemType.DINNER_BREAK.value)
    assert pieskowa.end_time == "15:22"
    assert dinner.start_time == "17:00"
    assert "Maczuga" in _names(gap)
    assert _valley_idle(gap)
    assert max(_valley_idle(gap)) < 40

    kept = _fix387_run(
        [
            _fix383_attr("Zamek Pieskowa Skała", "13:00", "15:22", 50.2451641, 19.7788312),
            _dinner("17:00", "18:00"),
        ],
        group_type="family_kids",
        preferences=["kids_attractions", "nature_landscape"],
        fix387_keep=False,
    )
    assert "Maczuga" in _names(kept)
    assert next(it for it in kept if "Pieskowa" in (getattr(it, "name", "") or "")).end_time == "15:22"

    zlota = "Parking Złota Góra (Ojcowski Park Narodowy)"
    castle = _fix387_run(
        [
            _car("09:00", "09:48", "Parking ul. Szpitalna", zlota, 22),
            _walk("09:48", "09:56", zlota, "Zamek w Ojcowie", 0.4),
            _fix383_attr("Zamek w Ojcowie", "09:56", "11:17", 50.2117047, 19.8300564),
            _walk("11:17", "11:25", "Zamek w Ojcowie", zlota, 0.4),
            _car("11:25", "12:13", zlota, "Parking ul. Szpitalna", 22),
            _walk("12:13", "12:20", "Parking ul. Szpitalna", "Sukiennice", 0.4),
            _fix383_attr("Sukiennice", "13:00", "14:30", 50.0617, 19.9373),
            _dinner("18:00", "19:00"),
        ],
        group_type="couples",
        preferences=["nature_landscape", "local_food_experience", "museum_heritage"],
        date="2026-02-23",
    )
    host = next(it for it in castle if getattr(it, "name", "") == "Zamek w Ojcowie")
    assert host.start_time == "09:56" and host.end_time == "11:17"
    folded = _fold_place_label(_names(castle))
    assert "maczuga" in folded or "lokietka" in folded or "ciemna" in folded or "pieskowa" in folded
    valley = [
        it for it in castle
        if _kind(it) == ItemType.ATTRACTION.value and _is_ojcow_stop_name(getattr(it, "name", "") or "")
    ]
    assert len(valley) >= 2
    valley_visit = sum(_span_minutes(it) for it in valley)
    valley_drive = 0
    for it in castle:
        if getattr(getattr(it, "mode", None), "value", getattr(it, "mode", "")) != "car":
            continue
        blob = _fold_place_label(
            f"{getattr(it, 'from_location', '')} {getattr(it, 'to_location', '')}"
        )
        km = float(getattr(it, "distance_km", 0) or 0)
        if km >= 20 or any(stem in blob for stem in ("ojcow", "pieskow", "maczuga")):
            valley_drive += int(getattr(it, "duration_min", 0) or 0)
    assert valley_visit > valley_drive
    castle_kept = _fix387_run(
        [
            _car("09:00", "09:48", "Parking ul. Szpitalna", zlota, 22),
            _walk("09:48", "09:56", zlota, "Zamek w Ojcowie", 0.4),
            _fix383_attr("Zamek w Ojcowie", "09:56", "11:17", 50.2117047, 19.8300564),
            _walk("11:17", "11:25", "Zamek w Ojcowie", zlota, 0.4),
            _car("11:25", "12:13", zlota, "Parking ul. Szpitalna", 22),
            _walk("12:13", "12:20", "Parking ul. Szpitalna", "Sukiennice", 0.4),
            _fix383_attr("Sukiennice", "13:00", "14:30", 50.0617, 19.9373),
            _dinner("18:00", "19:00"),
        ],
        group_type="couples",
        preferences=["nature_landscape", "local_food_experience", "museum_heritage"],
        date="2026-02-23",
        fix387_keep=False,
    )
    host_kept = next(it for it in castle_kept if getattr(it, "name", "") == "Zamek w Ojcowie")
    assert host_kept.start_time == "09:56" and host_kept.end_time == "11:17"
    assert len([
        it for it in castle_kept
        if _kind(it) == ItemType.ATTRACTION.value and _is_ojcow_stop_name(getattr(it, "name", "") or "")
    ]) >= 2

    home = _fix387_run(
        [
            _car("09:00", "09:10", "Parking Galeria Krakowska (ul. Pawia 5)", "Parking ul. Szpitalna", 1.1),
            _walk("09:10", "09:18", "Parking ul. Szpitalna", "Trattoria Mira", 0.35),
            _lunch("11:20", "12:00", "Trattoria Mira", 50.0638, 19.9415),
            _walk("12:00", "12:12", "Trattoria Mira", "Parking plac Na Groblach (pod Wawelem)", 1.1),
            _car("12:12", "12:30", "Parking plac Na Groblach (pod Wawelem)", "Parking Zabłocie (ul. Przemysłowa)", 3.0),
            _walk("12:30", "12:38", "Parking Zabłocie (ul. Przemysłowa)", "Muzeum Sztuki Współczesnej MOCAK", 0.4),
            _fix383_attr("Muzeum Sztuki Współczesnej MOCAK", "12:40", "14:00", 50.0492, 19.9608),
            _dinner("18:00", "19:00"),
        ],
        group_type="couples",
        travel_style="balanced",
    )
    mocak = next(it for it in home if "MOCAK" in (getattr(it, "name", "") or ""))
    assert mocak.start_time == "12:40"
    departures = [
        getattr(it, "from_location", "") or ""
        for it in home
        if getattr(getattr(it, "mode", None), "value", getattr(it, "mode", "")) == "car"
    ]
    assert not any("Groblach" in frm for frm in departures)
    assert any("Szpitalna" in frm for frm in departures)
    home_kept = _fix387_run(
        [
            _car("09:00", "09:10", "Parking Galeria Krakowska (ul. Pawia 5)", "Parking ul. Szpitalna", 1.1),
            _walk("09:10", "09:18", "Parking ul. Szpitalna", "Trattoria Mira", 0.35),
            _lunch("11:20", "12:00", "Trattoria Mira", 50.0638, 19.9415),
            _walk("12:00", "12:12", "Trattoria Mira", "Parking plac Na Groblach (pod Wawelem)", 1.1),
            _car("12:12", "12:30", "Parking plac Na Groblach (pod Wawelem)", "Parking Zabłocie (ul. Przemysłowa)", 3.0),
            _walk("12:30", "12:38", "Parking Zabłocie (ul. Przemysłowa)", "Muzeum Sztuki Współczesnej MOCAK", 0.4),
            _fix383_attr("Muzeum Sztuki Współczesnej MOCAK", "12:40", "14:00", 50.0492, 19.9608),
            _dinner("18:00", "19:00"),
        ],
        group_type="couples",
        travel_style="balanced",
        fix387_keep=False,
    )
    assert next(it for it in home_kept if "MOCAK" in (getattr(it, "name", "") or "")).start_time == "12:40"
    assert not any(
        "Groblach" in (getattr(it, "from_location", "") or "")
        for it in home_kept
        if getattr(getattr(it, "mode", None), "value", getattr(it, "mode", "")) == "car"
    )

    far_lunch = (50.0610, 19.9090)
    stranded = _fix387_run(
        [
            _car("09:00", "09:10", "Parking Galeria Krakowska (ul. Pawia 5)", "Parking ul. Szpitalna", 1.1),
            _walk("09:10", "09:40", "Parking ul. Szpitalna", "Restauracja Błonia", 2.6),
            _lunch("15:20", "15:50", "Restauracja Błonia", far_lunch[0], far_lunch[1]),
            _walk("15:50", "16:05", "Restauracja Błonia", "Parking plac Na Groblach (pod Wawelem)", 2.4),
            _car("16:05", "16:20", "Parking plac Na Groblach (pod Wawelem)", "Parking Zabłocie (ul. Przemysłowa)", 3.0),
            _walk("16:20", "16:28", "Parking Zabłocie (ul. Przemysłowa)", "Muzeum Sztuki Współczesnej MOCAK", 0.4),
            _fix383_attr("Muzeum Sztuki Współczesnej MOCAK", "16:28", "17:20", 50.0492, 19.9608),
            _dinner("18:00", "19:00"),
        ],
        group_type="couples",
        poi_pool=[{
            "name": "Podziemia Rynku w Krakowie",
            "lat": 50.0620,
            "lng": 19.9100,
            "time_max": 90,
        }],
    )
    dinner_far = next(it for it in stranded if _kind(it) == ItemType.DINNER_BREAK.value)
    assert dinner_far.start_time == "18:00"
    far_departures = [
        getattr(it, "from_location", "") or ""
        for it in stranded
        if getattr(getattr(it, "mode", None), "value", getattr(it, "mode", "")) == "car"
    ]
    assert not any("Groblach" in frm for frm in far_departures)
    assert "Podziemia" in _names(stranded)
    assert "MOCAK" not in _names(stranded)
    for it in stranded:
        if _kind(it) != ItemType.TRANSIT.value:
            continue
        if "walk" not in str(getattr(getattr(it, "mode", None), "value", "")):
            continue
        try:
            start = time_to_minutes(it.start_time)
        except Exception:
            continue
        if start >= 12 * 60:
            assert float(getattr(it, "distance_km", 0) or 0) <= 1.2
    stranded_kept = _fix387_run(
        [
            _car("09:00", "09:10", "Parking Galeria Krakowska (ul. Pawia 5)", "Parking ul. Szpitalna", 1.1),
            _walk("09:10", "09:40", "Parking ul. Szpitalna", "Restauracja Błonia", 2.6),
            _lunch("15:20", "15:50", "Restauracja Błonia", far_lunch[0], far_lunch[1]),
            _walk("15:50", "16:05", "Restauracja Błonia", "Parking plac Na Groblach (pod Wawelem)", 2.4),
            _car("16:05", "16:20", "Parking plac Na Groblach (pod Wawelem)", "Parking Zabłocie (ul. Przemysłowa)", 3.0),
            _walk("16:20", "16:28", "Parking Zabłocie (ul. Przemysłowa)", "Muzeum Sztuki Współczesnej MOCAK", 0.4),
            _fix383_attr("Muzeum Sztuki Współczesnej MOCAK", "16:28", "17:20", 50.0492, 19.9608),
            _dinner("18:00", "19:00"),
        ],
        group_type="couples",
        poi_pool=[{
            "name": "Podziemia Rynku w Krakowie",
            "lat": 50.0620,
            "lng": 19.9100,
            "time_max": 90,
        }],
        fix387_keep=False,
    )
    assert "Podziemia" in _names(stranded_kept)
    assert not any(
        "Groblach" in (getattr(it, "from_location", "") or "")
        for it in stranded_kept
        if getattr(getattr(it, "mode", None), "value", getattr(it, "mode", "")) == "car"
    )


def _fix388_run(items, **ctx):
    from app.domain.models.plan import DayPlan

    base = {
        "requested_city": "Kraków",
        "day_start": "09:00",
        "day_end": "20:00",
        "travel_style": "balanced",
        "group_type": "couples",
        "date": "2026-02-23",
        "poi_pool": [],
        "preferences": ["nature_landscape", "museum_heritage"],
        "has_car": True,
        "fix388_keep": True,
    }
    base.update(ctx)
    day = DayPlan(day=1, date=str(base.get("date"))[:10], items=items)
    out = PlanService(None)._seal_fix388_krakow_client([day], base)
    return out[0].items


def test_fix388_repairs_mailed_shapes():
    from app.domain.models.plan import DinnerBreakItem, LunchBreakItem, TransitItem, TransitMode
    from app.domain.planner.krakow_parking import parking_point
    from app.domain.planner.leg_physics import car_minutes
    from app.domain.planner.time_utils import minutes_to_time

    szpitalna = "Parking ul. Szpitalna"
    zablocie = "Parking Zabłocie (ul. Przemysłowa)"
    groblach = "Parking plac Na Groblach (pod Wawelem)"
    sz_pt = parking_point(szpitalna)
    zb_pt = parking_point(zablocie)
    gro_pt = parking_point(groblach)

    def _mt(minute):
        return minutes_to_time(minute)

    def _walk(start, end, frm, to, km):
        return TransitItem(
            type=ItemType.TRANSIT,
            start_time=start,
            end_time=end,
            duration_min=time_to_minutes(end) - time_to_minutes(start),
            mode=TransitMode.WALK,
            from_location=frm,
            to_location=to,
            distance_km=round(float(km), 3),
            routing_source="estimated_walk",
        )

    def _car(start, end, frm, to, km):
        row = _walk(start, end, frm, to, km)
        return row.model_copy(update={"mode": TransitMode.CAR, "routing_source": "estimated_car"})

    def _leg(cursor, frm, to, a, b, car=False):
        km = leg_km(a, b, "car" if car else "walk", city="Kraków")[0]
        mins = car_minutes(km) if car else walk_minutes(km, {})
        hop = (_car if car else _walk)(_mt(cursor), _mt(cursor + mins), frm, to, km)
        return hop, cursor + mins, km

    def _lunch(start, end, label, lat, lng):
        return LunchBreakItem(
            type=ItemType.LUNCH_BREAK,
            start_time=start,
            end_time=end,
            duration_min=time_to_minutes(end) - time_to_minutes(start),
            label=label,
            suggestions=[{"id": "t", "name": label, "lat": lat, "lng": lng}],
        )

    def _dinner(start, end):
        return DinnerBreakItem(
            type=ItemType.DINNER_BREAK,
            start_time=start,
            end_time=end,
            duration_min=time_to_minutes(end) - time_to_minutes(start),
            label="Kolacja",
        )

    def _kind(it):
        return getattr(getattr(it, "type", None), "value", getattr(it, "type", ""))

    def _names(items):
        return " ".join(getattr(it, "name", "") or "" for it in items)

    def _lego_count(items):
        stems = ("lego", "bricks", "klock", "swiat w budowie")
        return sum(
            1 for it in items
            if _kind(it) == ItemType.ATTRACTION.value
            and any(stem in _fold_place_label(getattr(it, "name", "") or "") for stem in stems)
        )

    def _cars_from(items):
        return [
            getattr(it, "from_location", "") or ""
            for it in items
            if getattr(getattr(it, "mode", None), "value", getattr(it, "mode", "")) == "car"
        ]

    bricks_pt = (50.0490, 19.9620)
    swiat_pt = (50.0670, 19.9380)
    planty_pt = (50.0632, 19.9412)
    assert leg_km(bricks_pt, swiat_pt, "walk", city="Kraków")[0] > 0.8

    def _lego_day():
        rows = []
        cursor = 9 * 60 + 10
        hop, cursor, _km = _leg(cursor, zablocie, "Bricks & Figs", zb_pt, bricks_pt)
        rows.append(hop)
        rows.append(_fix383_attr("Bricks & Figs", _mt(cursor), _mt(cursor + 90), *bricks_pt))
        cursor += 90
        hop, cursor, _km = _leg(cursor, "Bricks & Figs", zablocie, bricks_pt, zb_pt)
        rows.append(hop)
        hop, cursor, _km = _leg(cursor, zablocie, szpitalna, zb_pt, sz_pt, car=True)
        rows.append(hop)
        hop, cursor, _km = _leg(cursor, szpitalna, "Świat w Budowie", sz_pt, swiat_pt)
        rows.append(hop)
        rows.append(_fix383_attr("Świat w Budowie", _mt(cursor), _mt(cursor + 23), *swiat_pt))
        cursor += 23
        hop, cursor, _km = _leg(cursor, "Świat w Budowie", szpitalna, swiat_pt, sz_pt)
        rows.append(hop)
        hop, cursor, _km = _leg(cursor, szpitalna, "Planty Krakowskie", sz_pt, planty_pt)
        rows.append(hop)
        rows.append(_fix383_attr("Planty Krakowskie", _mt(cursor), _mt(cursor + 60), *planty_pt))
        rows.append(_dinner("18:30", "19:30"))
        return rows

    family = {
        "group_type": "family_kids",
        "preferences": ["kids_attractions", "nature_landscape"],
        "date": "2026-02-21",
    }
    lego = _fix388_run(_lego_day(), **family)
    kept_show = next(it for it in lego if getattr(it, "name", "") == "Bricks & Figs")
    assert kept_show.start_time == _lego_day()[1].start_time
    assert kept_show.end_time == _lego_day()[1].end_time
    assert "swiat w budowie" not in _fold_place_label(_names(lego))
    assert _lego_count(lego) == 1
    dinner = next(it for it in lego if _kind(it) == ItemType.DINNER_BREAK.value)
    assert time_to_minutes(dinner.start_time) >= 17 * 60
    assert any(zablocie in frm for frm in _cars_from(lego))
    lego_kept = _fix388_run(_lego_day(), fix388_keep=False, **family)
    assert _lego_count(lego_kept) == 1
    assert "swiat w budowie" not in _fold_place_label(_names(lego_kept))

    solo = _fix388_run([
        _fix383_attr("Bricks & Figs", "10:00", "11:30", *bricks_pt),
        _dinner("18:30", "19:30"),
    ], **family)
    assert next(it for it in solo if "Bricks" in (getattr(it, "name", "") or "")).start_time == "10:00"
    assert _lego_count(solo) == 1

    museum_pt = (50.0617, 19.9373)
    castle_pt = (50.0635, 19.9390)
    suk_pt = (50.0608, 19.9412)
    lunch_pt = (50.0620, 19.9400)
    lead, cursor, _km = _leg(9 * 60, szpitalna, "Muzeum Narodowe", sz_pt, museum_pt)
    museum_start = cursor
    museum_end = museum_start + 90
    to_castle, cursor, _km = _leg(museum_end, "Muzeum Narodowe", "Zamek w Ojcowie", museum_pt, castle_pt)
    castle_start = cursor
    to_suk_km = leg_km(castle_pt, suk_pt, "walk", city="Kraków")[0]
    to_lunch_km = leg_km(suk_pt, lunch_pt, "walk", city="Kraków")[0]
    to_suk_min = walk_minutes(to_suk_km, {})
    to_lunch_min = walk_minutes(to_lunch_km, {})
    lunch_start = 16 * 60 + 12
    suk_end = lunch_start - to_lunch_min
    suk_start = suk_end - 90
    castle_end = suk_start - to_suk_min
    lunch_rows = [
        lead,
        _fix383_attr("Muzeum Narodowe", _mt(museum_start), _mt(museum_end), *museum_pt),
        to_castle,
        _fix383_attr("Zamek w Ojcowie", _mt(castle_start), _mt(castle_end), *castle_pt),
        _walk(_mt(castle_end), _mt(castle_end + to_suk_min), "Zamek w Ojcowie", "Sukiennice", to_suk_km),
        _fix383_attr("Sukiennice", _mt(suk_start), _mt(suk_end), *suk_pt),
        _walk(_mt(suk_end), _mt(lunch_start), "Sukiennice", "Trattoria Mira", to_lunch_km),
        _lunch(_mt(lunch_start), "17:12", "Trattoria Mira", *lunch_pt),
        _dinner("17:30", "18:30"),
    ]
    castle_span = castle_end - castle_start
    pulled = _fix388_run(lunch_rows)
    castle = next(it for it in pulled if getattr(it, "name", "") == "Zamek w Ojcowie")
    meal = next(it for it in pulled if _kind(it) == ItemType.LUNCH_BREAK.value)
    suk = next(it for it in pulled if getattr(it, "name", "") == "Sukiennice")
    museum = next(it for it in pulled if getattr(it, "name", "") == "Muzeum Narodowe")
    assert _span_minutes(castle) == castle_span
    assert time_to_minutes(meal.start_time) <= 15 * 60
    assert meal.end_time == "17:12"
    assert _span_minutes(suk) == 45
    assert _span_minutes(museum) < 90
    assert next(it for it in pulled if _kind(it) == ItemType.DINNER_BREAK.value).start_time == "17:30"
    pulled_kept = _fix388_run(lunch_rows, fix388_keep=False)
    assert time_to_minutes(
        next(it for it in pulled_kept if _kind(it) == ItemType.LUNCH_BREAK.value).start_time
    ) <= 15 * 60

    wieza_pt = (50.0617, 19.9373)
    mid_pt = (50.0640, 19.9395)
    near_pt = (50.0630, 19.9388)
    drop_rows = []
    hop, cursor, _km = _leg(9 * 60, szpitalna, "Wieża Ratuszowa", sz_pt, wieza_pt)
    drop_rows.append(hop)
    drop_rows.append(_fix383_attr("Wieża Ratuszowa", _mt(cursor), _mt(cursor + 40), *wieza_pt))
    cursor += 40
    hop, cursor, _km = _leg(cursor, "Wieża Ratuszowa", "Muzeum Narodowe", wieza_pt, mid_pt)
    drop_rows.append(hop)
    drop_rows.append(_fix383_attr("Muzeum Narodowe", _mt(cursor), _mt(cursor + 60), *mid_pt))
    cursor += 60
    hop, cursor, _km = _leg(cursor, "Muzeum Narodowe", "Trattoria Mira", mid_pt, near_pt)
    drop_rows.append(hop)
    drop_rows.append(_lunch("16:12", "17:12", "Trattoria Mira", *near_pt))
    drop_rows.append(_dinner("17:30", "18:30"))
    dropped = _fix388_run(drop_rows)
    dropped_meal = next(it for it in dropped if _kind(it) == ItemType.LUNCH_BREAK.value)
    assert time_to_minutes(dropped_meal.start_time) <= 15 * 60
    assert dropped_meal.end_time == "17:12"
    assert "Muzeum Narodowe" not in _names(dropped)
    assert "Wieża Ratuszowa" in _names(dropped)
    assert _span_minutes(next(it for it in dropped if "Wieża" in (getattr(it, "name", "") or ""))) == 40

    def _home(lunch_end, mocak_start, mocak_end, meal_at, meal_pin, dinner_at):
        rows = []
        cursor = 9 * 60
        hop, cursor, _km = _leg(cursor, szpitalna, zablocie, sz_pt, zb_pt, car=True)
        rows.append(hop)
        hop, cursor, _km = _leg(cursor, zablocie, szpitalna, zb_pt, sz_pt, car=True)
        rows.append(hop)
        hop, cursor, _km = _leg(cursor, szpitalna, meal_at, sz_pt, meal_pin)
        rows.append(hop)
        rows.append(_lunch(_mt(cursor), _mt(lunch_end), meal_at, *meal_pin))
        hop, _ignored, _km = _leg(lunch_end, meal_at, groblach, meal_pin, gro_pt)
        rows.append(hop)
        drive_start = time_to_minutes(hop.end_time)
        hop, _ignored, _km = _leg(drive_start, groblach, zablocie, gro_pt, zb_pt, car=True)
        rows.append(hop)
        walk_start = time_to_minutes(hop.end_time)
        hop, _ignored, _km = _leg(walk_start, zablocie, "Muzeum Sztuki Współczesnej MOCAK", zb_pt, (50.0492, 19.9608))
        rows.append(hop)
        rows.append(_fix383_attr(
            "Muzeum Sztuki Współczesnej MOCAK", _mt(mocak_start), _mt(mocak_end), 50.0492, 19.9608,
        ))
        rows.append(_dinner(_mt(dinner_at), _mt(dinner_at + 60)))
        return rows

    near = (50.0630, 19.9410)
    home = _fix388_run(_home(12 * 60, 13 * 60 + 30, 15 * 60, "Trattoria Mira", near, 18 * 60))
    mocak = next(it for it in home if "MOCAK" in (getattr(it, "name", "") or ""))
    assert time_to_minutes(mocak.start_time) < 13 * 60 + 30
    assert not any("Groblach" in frm for frm in _cars_from(home))
    assert any("Szpitalna" in frm for frm in _cars_from(home))
    assert next(it for it in home if _kind(it) == ItemType.DINNER_BREAK.value).start_time == "18:00"
    home_kept = _fix388_run(
        _home(12 * 60, 13 * 60 + 30, 15 * 60, "Trattoria Mira", near, 18 * 60),
        fix388_keep=False,
    )
    assert not any("Groblach" in frm for frm in _cars_from(home_kept))
    assert "MOCAK" in _names(home_kept)

    far = (50.0610, 19.9090)
    stranded = _fix388_run(
        _home(15 * 60 + 50, 16 * 60 + 28, 17 * 60 + 20, "Restauracja Błonia", far, 17 * 60 + 30),
        poi_pool=[{
            "name": "Podziemia Rynku w Krakowie",
            "lat": 50.0620,
            "lng": 19.9100,
            "time_max": 90,
        }],
    )
    assert next(it for it in stranded if _kind(it) == ItemType.DINNER_BREAK.value).start_time == "17:30"
    assert not any("Groblach" in frm for frm in _cars_from(stranded))
    assert "Podziemia" in _names(stranded)
    assert "MOCAK" not in _names(stranded)
    for it in stranded:
        if _kind(it) != ItemType.TRANSIT.value:
            continue
        if "walk" not in str(getattr(getattr(it, "mode", None), "value", "")):
            continue
        if time_to_minutes(it.start_time) >= 12 * 60:
            assert float(getattr(it, "distance_km", 0) or 0) <= 1.2
    stranded_kept = _fix388_run(
        _home(15 * 60 + 50, 16 * 60 + 28, 17 * 60 + 20, "Restauracja Błonia", far, 17 * 60 + 30),
        poi_pool=[{
            "name": "Podziemia Rynku w Krakowie",
            "lat": 50.0620,
            "lng": 19.9100,
            "time_max": 90,
        }],
        fix388_keep=False,
    )
    assert "Podziemia" in _names(stranded_kept)
    assert not any("Groblach" in frm for frm in _cars_from(stranded_kept))


def _fix389_run(items, **ctx):
    from app.domain.models.plan import DayPlan

    base = {
        "requested_city": "Kraków",
        "day_start": "09:00",
        "day_end": "20:00",
        "travel_style": "balanced",
        "group_type": "couples",
        "date": "2026-02-23",
        "preferences": ["nature_landscape", "museum_heritage"],
        "has_car": True,
    }
    base.update(ctx)
    day = DayPlan(day=1, date=str(base["date"])[:10], items=items)
    return PlanService(None)._seal_fix389_krakow_client([day], base)[0].items


def test_fix389_enforces_final_krakow_postconditions():
    from app.domain.models.plan import (
        DayPlan,
        DinnerBreakItem,
        LunchBreakItem,
        TicketInfo,
        TransitItem,
        TransitMode,
    )

    def _hop(start, end, mode, frm, to, km):
        return TransitItem(
            type=ItemType.TRANSIT,
            start_time=start,
            end_time=end,
            duration_min=time_to_minutes(end) - time_to_minutes(start),
            mode=mode,
            from_location=frm,
            to_location=to,
            distance_km=km,
            routing_source=f"estimated_{getattr(mode, 'value', mode)}",
        )

    def _lunch(start, end, name, lat, lng):
        return LunchBreakItem(
            type=ItemType.LUNCH_BREAK,
            start_time=start,
            end_time=end,
            duration_min=time_to_minutes(end) - time_to_minutes(start),
            label=name,
            suggestions=[{
                "id": "fix389",
                "name": name,
                "lat": lat,
                "lng": lng,
            }],
        )

    def _dinner(start, end):
        return DinnerBreakItem(
            type=ItemType.DINNER_BREAK,
            start_time=start,
            end_time=end,
            duration_min=time_to_minutes(end) - time_to_minutes(start),
            label="Kolacja",
        )

    def _kind(it):
        return getattr(getattr(it, "type", None), "value", getattr(it, "type", ""))

    def _names(items):
        return [
            getattr(it, "name", "") or ""
            for it in items
            if _kind(it) == ItemType.ATTRACTION.value
        ]

    # The exact #388 regression: moving only the start made a 145-minute meal.
    maczuga = _fix383_attr(
        "Maczuga Herkulesa", "17:02", "18:02", 50.2429068, 19.7829619,
    ).model_copy(update={
        "cost_estimate": 44,
        "ticket_info": TicketInfo(ticket_normal=22, ticket_reduced=11),
    })
    square = _fix383_attr(
        "Plac Bohaterów Getta", "18:12", "18:42", 50.0469, 19.9547,
    ).model_copy(update={
        "cost_estimate": 39,
        "ticket_info": TicketInfo(ticket_normal=19, ticket_reduced=10),
    })
    meal_rows = [
        _fix383_attr("Sukiennice", "12:57", "14:17", 50.0617, 19.9373),
        _hop(
            "14:17", "14:27", TransitMode.WALK,
            "Sukiennice", "Trattoria Mira", 0.55,
        ),
        _lunch("14:27", "16:52", "Trattoria Mira", 50.0620, 19.9400),
        _hop(
            "16:52", "17:02", TransitMode.PUBLIC_TRANSPORT,
            "Trattoria Mira", "Maczuga Herkulesa", 24.0,
        ),
        maczuga,
        _hop(
            "18:02", "18:12", TransitMode.PUBLIC_TRANSPORT,
            "Maczuga Herkulesa", "Plac Bohaterów Getta", 24.0,
        ),
        square,
        _dinner("19:00", "20:00"),
    ]
    fixed_meal = _fix389_run(meal_rows, transport_modes=["car", "public_transport"])
    lunch = next(it for it in fixed_meal if _kind(it) == ItemType.LUNCH_BREAK.value)
    assert lunch.start_time == "14:27"
    assert lunch.end_time == "15:07"
    assert _span_minutes(lunch) == 40
    assert next(
        it for it in fixed_meal if getattr(it, "name", "") == "Maczuga Herkulesa"
    ).start_time == "15:17"
    for name in ("Maczuga Herkulesa", "Plac Bohaterów Getta"):
        item = next(it for it in fixed_meal if getattr(it, "name", "") == name)
        assert item.cost_estimate == 0
        assert item.ticket_info.ticket_normal == 0
        assert item.ticket_info.ticket_reduced == 0
    dinner = next(it for it in fixed_meal if _kind(it) == ItemType.DINNER_BREAK.value)
    assert time_to_minutes(dinner.start_time) >= max(
        17 * 60, time_to_minutes(lunch.end_time) + 180,
    )

    # A second LEGO must leave even when neither neighbouring stop exposes a
    # usable served-lot chain.
    lego_rows = [
        _fix383_attr("Bricks & Figs", "10:00", "11:30", 50.0490, 19.9620),
        _hop(
            "11:30", "12:00", TransitMode.PUBLIC_TRANSPORT,
            "Bricks & Figs", "Świat w Budowie", 3.5,
        ),
        _fix383_attr("Świat w Budowie", "12:00", "12:23", 50.0670, 19.9380),
        _hop(
            "12:23", "12:33", TransitMode.WALK,
            "Świat w Budowie", "Planty Krakowskie", 0.6,
        ),
        _fix383_attr("Planty Krakowskie", "12:33", "13:33", 50.0632, 19.9412),
        _dinner("18:00", "19:00"),
    ]
    fixed_lego = _fix389_run(
        lego_rows,
        group_type="family_kids",
        preferences=["kids_attractions", "nature_landscape"],
        date="2026-02-21",
        transport_modes=["car", "public_transport"],
    )
    folded_names = [_fold_place_label(name) for name in _names(fixed_lego)]
    bricks = [
        name for name in folded_names
        if any(stem in name for stem in ("lego", "bricks", "klock", "swiat w budowie"))
    ]
    assert bricks == ["bricks & figs"]
    assert not any("swiat w budowie" in name for name in folded_names)

    # The short LEGO is the final attraction.  Its inbound walk must leave
    # together with the visit; a generic dinner has no coordinates to bridge.
    terminal_lego = _fix389_run(
        [
            _fix383_attr(
                "Bricks & Figs", "15:00", "16:20", 50.0490, 19.9620,
            ),
            _hop(
                "16:20", "16:30", TransitMode.WALK,
                "Bricks & Figs", "Świat w Budowie", 0.6,
            ),
            _fix383_attr(
                "Świat w Budowie", "16:30", "16:53", 50.0670, 19.9380,
            ),
            _dinner("18:30", "19:30"),
        ],
        group_type="family_kids",
        preferences=["kids_attractions", "nature_landscape"],
        date="2026-02-21",
    )
    assert "Świat w Budowie" not in _names(terminal_lego)
    assert not any(
        "swiat w budowie" in _fold_place_label(
            getattr(it, "to_location", "") or ""
        )
        for it in terminal_lego
        if _kind(it) == ItemType.TRANSIT.value
    )
    assert next(
        it for it in terminal_lego if _kind(it) == ItemType.DINNER_BREAK.value
    ).start_time == "17:00"

    # The car is at Szpitalna while people are far away.  With public
    # transport selected the illegal Groblach departure becomes one transit
    # connection; car-only plans are covered by the FIX #391 test.
    teleport_rows = [
        _hop(
            "09:00", "09:12", TransitMode.CAR,
            "Kraków", "Parking ul. Szpitalna", 3.0,
        ),
        _hop(
            "09:12", "09:55", TransitMode.WALK,
            "Parking ul. Szpitalna", "Restauracja Błonia", 3.176,
        ),
        _lunch("14:50", "15:30", "Restauracja Błonia", 50.0610, 19.9090),
        _hop(
            "15:30", "15:45", TransitMode.WALK,
            "Restauracja Błonia", "Parking plac Na Groblach (pod Wawelem)", 2.4,
        ),
        _hop(
            "15:45", "16:03", TransitMode.CAR,
            "Parking plac Na Groblach (pod Wawelem)",
            "Parking Zabłocie (ul. Przemysłowa)", 3.0,
        ),
        _hop(
            "16:03", "16:11", TransitMode.WALK,
            "Parking Zabłocie (ul. Przemysłowa)",
            "Muzeum Sztuki Współczesnej MOCAK", 0.4,
        ),
        _fix383_attr(
            "Muzeum Sztuki Współczesnej MOCAK",
            "16:11", "17:11", 50.0492, 19.9608,
        ),
        _dinner("18:00", "19:00"),
    ]
    fixed_car = _fix389_run(teleport_rows, transport_modes=["car", "public_transport"])
    assert not any(
        "Groblach" in (getattr(it, "from_location", "") or "")
        for it in fixed_car
        if getattr(getattr(it, "mode", None), "value", getattr(it, "mode", ""))
        == "car"
    )
    assert any(
        getattr(getattr(it, "mode", None), "value", getattr(it, "mode", ""))
        == "public_transport"
        and "Restauracja Błonia" in (getattr(it, "from_location", "") or "")
        and "MOCAK" in (getattr(it, "to_location", "") or "")
        for it in fixed_car
    )
    car_codes = {
        defect.code
        for defect in audit_plan([DayPlan(
            day=1, date="2026-02-23", items=fixed_car,
        )], context={
            "requested_city": "Kraków",
            "day_start": "09:00",
            "day_end": "20:00",
            "audit_car_model": True,
        })
    }
    assert not ({"car_teleport", "car_position_mismatch"} & car_codes)

    # Exact missed variant: the car is known only from the day's opening walk
    # out of Szpitalna; there is no earlier car leg to initialise the ledger.
    parked_from_start = _fix389_run([
        _hop(
            "09:00", "09:10", TransitMode.WALK,
            "Parking ul. Szpitalna", "MNK Sukiennice", 0.64,
        ),
        _fix383_attr("MNK Sukiennice", "09:10", "10:30", 50.0617, 19.9373),
        _hop(
            "10:30", "10:50", TransitMode.WALK,
            "MNK Sukiennice", "Restauracja Błonia", 2.2,
        ),
        _lunch("14:50", "15:30", "Restauracja Błonia", 50.0610, 19.9090),
        _hop(
            "15:30", "15:45", TransitMode.WALK,
            "Restauracja Błonia", "Parking plac Na Groblach (pod Wawelem)", 2.4,
        ),
        _hop(
            "15:45", "16:03", TransitMode.CAR,
            "Parking plac Na Groblach (pod Wawelem)",
            "Parking Zabłocie (ul. Przemysłowa)", 3.0,
        ),
        _hop(
            "16:03", "16:11", TransitMode.WALK,
            "Parking Zabłocie (ul. Przemysłowa)",
            "Muzeum Sztuki Współczesnej MOCAK", 0.4,
        ),
        _fix383_attr(
            "Muzeum Sztuki Współczesnej MOCAK",
            "16:11", "17:11", 50.0492, 19.9608,
        ),
        _dinner("18:00", "19:00"),
    ], transport_modes=["car", "public_transport"])
    assert not any(
        "Groblach" in (getattr(it, "from_location", "") or "")
        for it in parked_from_start
        if getattr(getattr(it, "mode", None), "value", getattr(it, "mode", ""))
        == "car"
    )
    assert any(
        getattr(getattr(it, "mode", None), "value", getattr(it, "mode", ""))
        == "public_transport"
        and "Restauracja Błonia" in (getattr(it, "from_location", "") or "")
        and "MOCAK" in (getattr(it, "to_location", "") or "")
        for it in parked_from_start
    )


def _fix391_hop(start, end, mode, frm, to, km):
    from app.domain.models.plan import TransitItem

    return TransitItem(
        type=ItemType.TRANSIT,
        start_time=start,
        end_time=end,
        duration_min=time_to_minutes(end) - time_to_minutes(start),
        mode=mode,
        from_location=frm,
        to_location=to,
        distance_km=km,
        routing_source=f"estimated_{getattr(mode, 'value', mode)}",
    )


def _fix391_dinner(start="17:00", end="18:00"):
    from app.domain.models.plan import DinnerBreakItem

    return DinnerBreakItem(
        type=ItemType.DINNER_BREAK,
        start_time=start,
        end_time=end,
        duration_min=time_to_minutes(end) - time_to_minutes(start),
        label="Kolacja",
    )


def _fix391_ctx(**extra):
    base = {
        "requested_city": "Kraków",
        "day_start": "09:00",
        "day_end": "20:00",
        "travel_style": "balanced",
        "group_type": "couples",
        "date": "2026-02-23",
        "preferences": ["nature_landscape", "museum_heritage"],
        "has_car": True,
        "transport_modes": ["car"],
    }
    base.update(extra)
    return base


def _fix391_seal(day_items, **extra):
    from app.domain.models.plan import DayPlan

    ctx = _fix391_ctx(**extra)
    start = _date.fromisoformat(ctx["date"])
    days = [
        DayPlan(day=i + 1, date=str(start + _td(days=i)), items=items)
        for i, items in enumerate(day_items)
    ]
    return PlanService(None)._seal_fix389_krakow_client(days, ctx), ctx


def _fix391_mode(it):
    return getattr(getattr(it, "mode", None), "value", getattr(it, "mode", "")) or ""


def _fix391_kind(it):
    return getattr(getattr(it, "type", None), "value", getattr(it, "type", ""))


def _fix391_names(items):
    return [
        getattr(it, "name", "") or ""
        for it in items
        if _fix391_kind(it) == ItemType.ATTRACTION.value
    ]


def _fix391_hard_codes(days, ctx):
    return {
        d.code
        for d in audit_plan(days, context={**ctx, "audit_car_model": True})
    } & {"car_teleport", "car_position_mismatch", "missing_hop", "from_mismatch"}


def _fix391_valley(items):
    """The gate's thin_ojcow numbers: (valley stops, valley drive, valley visit)."""
    stops = visit = drive = 0
    for it in items:
        kind = _fix391_kind(it)
        if kind == ItemType.ATTRACTION.value and _is_ojcow_stop_name(it.name or ""):
            stops += 1
            visit += _span_minutes(it)
        if kind == ItemType.TRANSIT.value and _fix391_mode(it) == "car":
            blob = _fold_place_label(f"{it.from_location} {it.to_location}")
            if float(it.distance_km or 0) >= 20 or any(
                s in blob for s in ("ojcow", "pieskow", "maczuga")
            ):
                drive += int(it.duration_min or 0)
    return stops, drive, visit


def test_fix391_car_only_never_gets_public_transport():
    from app.domain.models.plan import TransitMode

    # J8 D4: the car stands at Szpitalna, the travellers are at the Cathedral,
    # and Plac Bohaterów Getta was reached by public transport on a car-only trip.
    far_car = [
        _fix391_hop("09:00", "09:12", TransitMode.WALK, "Parking ul. Szpitalna", "MNK Sukiennice", 0.64),
        _fix383_attr("MNK Sukiennice", "09:12", "10:45", 50.0617, 19.9373),
        _fix391_hop("10:45", "11:00", TransitMode.WALK, "MNK Sukiennice", "Katedra Wawelska", 1.0),
        _fix383_attr("Katedra Wawelska", "11:00", "11:45", 50.0544, 19.9355),
        _fix391_hop("11:45", "12:05", TransitMode.PUBLIC_TRANSPORT, "Katedra Wawelska", "Plac Bohaterów Getta", 2.2),
        _fix383_attr("Plac Bohaterów Getta", "12:05", "12:35", 50.0469, 19.9547),
        _fix391_dinner(),
    ]
    days, ctx = _fix391_seal([far_car])
    items = days[0].items
    assert not any("public" in _fix391_mode(it) for it in items)
    assert not _fix391_hard_codes(days, ctx)

    # Same leg, but the car is at Groblach under Wawel: drive instead.
    near_car = [
        _fix391_hop("09:00", "09:09", TransitMode.CAR, "Kraków", "Parking plac Na Groblach (pod Wawelem)", 1.931),
        _fix391_hop("09:09", "09:15", TransitMode.WALK, "Parking plac Na Groblach (pod Wawelem)", "Katedra Wawelska", 0.384),
        _fix383_attr("Katedra Wawelska", "09:15", "10:45", 50.0544, 19.9355),
        _fix391_hop("10:45", "11:05", TransitMode.PUBLIC_TRANSPORT, "Katedra Wawelska", "Plac Bohaterów Getta", 2.2),
        _fix383_attr("Plac Bohaterów Getta", "11:05", "11:35", 50.0469, 19.9547),
        _fix391_dinner(),
    ]
    days, ctx = _fix391_seal([near_car])
    items = days[0].items
    assert not any("public" in _fix391_mode(it) for it in items)
    assert "Plac Bohaterów Getta" in _fix391_names(items)
    assert any(
        _fix391_mode(it) == "car" and "Groblach" in it.from_location
        for it in items[2:]
    )
    assert not _fix391_hard_codes(days, ctx)

    # Public transport stays legal when the traveller selected it.
    days, _ctx = _fix391_seal([near_car], transport_modes=["car", "public_transport"])
    assert "Plac Bohaterów Getta" in _fix391_names(days[0].items)


def test_fix391_no_place_repeats_across_days():
    from app.domain.models.plan import TransitMode

    def _skalki_day(start_lot_leg):
        return [
            start_lot_leg,
            _fix391_hop("09:16", "09:28", TransitMode.WALK, "Parking Dębniki (ul. Tyniecka)", "Skałki Twardowskiego", 0.85),
            _fix383_attr("Skałki Twardowskiego", "09:28", "11:34", 50.0386, 19.9095),
            _fix391_hop("11:34", "11:46", TransitMode.WALK, "Skałki Twardowskiego", "Parking Dębniki (ul. Tyniecka)", 0.85),
            _fix391_hop("11:46", "12:02", TransitMode.CAR, "Parking Dębniki (ul. Tyniecka)", "Parking Podgórze (ul. Na Zjeździe)", 4.742),
            _fix391_hop("12:02", "12:04", TransitMode.WALK, "Parking Podgórze (ul. Na Zjeździe)", "Plac Bohaterów Getta", 0.128),
            _fix383_attr("Plac Bohaterów Getta", "12:04", "12:35", 50.0469, 19.9547),
            _fix391_dinner(),
        ]

    lead = _fix391_hop("09:00", "09:16", TransitMode.CAR, "Kraków", "Parking Dębniki (ul. Tyniecka)", 4.733)
    day1 = [
        lead,
        _fix391_hop("09:16", "09:28", TransitMode.WALK, "Parking Dębniki (ul. Tyniecka)", "Skałki Twardowskiego", 0.85),
        _fix383_attr("Skałki Twardowskiego", "09:28", "11:34", 50.0386, 19.9095),
        _fix391_dinner(),
    ]
    days, ctx = _fix391_seal([day1, _fix391_dinner_only(), _skalki_day(lead)])
    seen = []
    for day in days:
        for name in _fix391_names(day.items):
            folded = _fold_place_label(name)
            assert folded not in seen, f"D{day.day} repeats {name}"
            seen.append(folded)
    assert "Skałki Twardowskiego" in _fix391_names(days[0].items)
    assert "Skałki Twardowskiego" not in _fix391_names(days[2].items)
    assert "Plac Bohaterów Getta" in _fix391_names(days[2].items)
    first = days[2].items[0]
    assert _fix391_kind(first) == ItemType.TRANSIT.value
    assert first.start_time == "09:00"
    assert not _fix391_hard_codes([days[2]], ctx)


def _fix391_dinner_only():
    return [_fix391_dinner()]


_FIX392_POOL = [
    {"name": "Muzeum Inżynierii i Techniki", "lat": 50.0507, "lng": 19.9478, "time_max": 120, "ticket_normal": 25},
    {"name": "Synagoga Stara", "lat": 50.0518, "lng": 19.9490, "time_max": 60, "ticket_normal": 20},
    {"name": "Muzeum Lotnictwa Polskiego", "lat": 50.0722, "lng": 19.9905, "time_max": 120, "ticket_normal": 30},
]


def _fix392_tail_ok(day, ctx):
    """No hole before dinner and the travellers end the day with their car."""
    items = list(day.items)
    dinner_i = next(
        i for i, it in enumerate(items) if _fix391_kind(it) == ItemType.DINNER_BREAK.value
    )
    last = None
    for it in items[:dinner_i]:
        end = getattr(it, "end_time", None)
        if end:
            last = time_to_minutes(end)
    gap = time_to_minutes(items[dinner_i].start_time) - last
    assert gap < 45, f"D{day.day}: {gap} min hole before dinner"
    car_at = people = None
    for it in items[:dinner_i]:
        kind = _fix391_kind(it)
        if kind == ItemType.TRANSIT.value:
            if _fix391_mode(it) == "car":
                car_at = it.to_location
            people = it.to_location
            if car_at is None and is_parking_label(it.from_location or ""):
                car_at = it.from_location
        elif kind == ItemType.ATTRACTION.value:
            people = it.name
    assert car_at, f"D{day.day}: the car vanished"
    assert not _fix391_hard_codes([day], ctx)
    return people, car_at


def test_fix392_removed_stop_never_cuts_the_day():
    from app.domain.models.plan import TransitMode

    family = {
        "group_type": "family_kids",
        "preferences": ["kids_attractions", "museum_heritage"],
        "date": "2026-02-20",
        "poi_pool": _FIX392_POOL,
    }

    # J1 D2: Park Lotników at 16:14, then a branch to the second LEGO show.
    # Removing the show used to delete the walk back to the car as well.
    day2 = [
        _fix391_hop("13:00", "13:15", TransitMode.CAR, "Kraków", "Parking Zabłocie (ul. Przemysłowa)", 3.1),
        _fix391_hop("13:15", "13:22", TransitMode.WALK, "Parking Zabłocie (ul. Przemysłowa)", "Bricks & Figs - muzeum klocków LEGO", 0.52),
        _fix383_attr("Bricks & Figs - muzeum klocków LEGO", "13:22", "14:22", 50.0490, 19.9620),
        _fix391_hop("14:22", "14:29", TransitMode.WALK, "Bricks & Figs - muzeum klocków LEGO", "Parking Zabłocie (ul. Przemysłowa)", 0.52),
        _fix391_hop("14:29", "14:44", TransitMode.CAR, "Parking Zabłocie (ul. Przemysłowa)", "Parking Czyżyny (al. Pokoju)", 5.0),
        _fix391_hop("14:44", "14:52", TransitMode.WALK, "Parking Czyżyny (al. Pokoju)", "Park Lotników Polskich", 0.549),
        _fix383_attr("Park Lotników Polskich", "14:52", "16:14", 50.0712, 19.9932),
        _fix391_hop("16:14", "16:22", TransitMode.WALK, "Park Lotników Polskich", "Parking Czyżyny (al. Pokoju)", 0.549),
        _fix391_hop("16:22", "16:40", TransitMode.CAR, "Parking Czyżyny (al. Pokoju)", "Parking Galeria Krakowska (ul. Pawia 5)", 6.0),
        _fix391_hop("16:40", "16:48", TransitMode.WALK, "Parking Galeria Krakowska (ul. Pawia 5)", "Świat w Budowie", 0.6),
        _fix383_attr("Świat w Budowie", "16:48", "17:11", 50.0670, 19.9380),
        _fix391_dinner("17:15", "18:00"),
    ]
    days, ctx = _fix391_seal([day2], **family)
    names = _fix391_names(days[0].items)
    assert "Świat w Budowie" not in names
    assert "Park Lotników Polskich" in names
    _fix392_tail_ok(days[0], ctx)

    # J1 D1: Muzeum Etnograficzne ends 14:35; the next stop repeats an
    # earlier day and leaves.  The afternoon must not stay empty until 17:00.
    earlier = [
        _fix391_hop("09:00", "09:20", TransitMode.CAR, "Kraków", "Parking pl. Paula McCartneya (pod Kopcem)", 5.0),
        _fix391_hop("09:20", "09:22", TransitMode.WALK, "Parking pl. Paula McCartneya (pod Kopcem)", "Kopiec Kościuszki", 0.088),
        _fix383_attr("Kopiec Kościuszki", "09:22", "11:00", 50.0548, 19.8933),
        _fix391_hop("11:00", "11:02", TransitMode.WALK, "Kopiec Kościuszki", "Parking pl. Paula McCartneya (pod Kopcem)", 0.088),
        _fix391_hop("11:02", "11:20", TransitMode.CAR, "Parking pl. Paula McCartneya (pod Kopcem)", "Parking przy Muzeum (al. 3 Maja)", 3.8),
        _fix391_hop("11:20", "11:22", TransitMode.WALK, "Parking przy Muzeum (al. 3 Maja)", "Muzeum Narodowe w Krakowie", 0.099),
        _fix383_attr("Muzeum Narodowe w Krakowie", "11:22", "16:20", 50.0604, 19.9235),
        _fix391_dinner(),
    ]
    day1 = [
        _fix391_hop("12:40", "12:50", TransitMode.CAR, "Kraków", "Parking plac Wolnica", 2.0),
        _fix391_hop("12:50", "12:55", TransitMode.WALK, "Parking plac Wolnica", "Muzeum Etnograficzne im. Seweryna Udzieli", 0.25),
        _fix383_attr("Muzeum Etnograficzne im. Seweryna Udzieli", "12:55", "14:35", 50.0505, 19.9437),
        _fix391_hop("14:35", "14:39", TransitMode.WALK, "Muzeum Etnograficzne im. Seweryna Udzieli", "Parking plac Wolnica", 0.25),
        _fix391_hop("14:39", "14:59", TransitMode.CAR, "Parking plac Wolnica", "Parking pl. Paula McCartneya (pod Kopcem)", 5.0),
        _fix391_hop("14:59", "15:01", TransitMode.WALK, "Parking pl. Paula McCartneya (pod Kopcem)", "Kopiec Kościuszki", 0.088),
        _fix383_attr("Kopiec Kościuszki", "15:01", "16:40", 50.0548, 19.8933),
        _fix391_dinner(),
    ]
    days, ctx = _fix391_seal([earlier, day1], **{**family, "date": "2026-02-19"})
    names = _fix391_names(days[1].items)
    assert "Kopiec Kościuszki" not in names
    assert "Muzeum Etnograficzne im. Seweryna Udzieli" in names
    assert len(names) >= 2, names
    _fix392_tail_ok(days[1], ctx)
    filled = [it for it in days[1].items if getattr(it, "poi_id", "") == "fix392"]
    assert filled and all(it.cost_estimate == 25 or it.cost_estimate == 20 for it in filled)

    # Without any open place nearby the freed time is not handed out as a
    # hole: the day keeps a valid shape and the car is still with the family.
    days, ctx = _fix391_seal([day2], **{**family, "poi_pool": []})
    assert "Świat w Budowie" not in _fix391_names(days[0].items)
    assert not _fix391_hard_codes(days, ctx)

    # The generator itself can leave the afternoon empty.  No stop is
    # removed; the hole after 14:35 still has to be filled.
    hollow = [
        _fix391_hop("12:40", "12:50", TransitMode.CAR, "Kraków", "Parking plac Wolnica", 2.0),
        _fix391_hop("12:50", "12:55", TransitMode.WALK, "Parking plac Wolnica", "Muzeum Etnograficzne im. Seweryna Udzieli", 0.25),
        _fix383_attr("Muzeum Etnograficzne im. Seweryna Udzieli", "12:55", "14:35", 50.0505, 19.9437),
        _fix391_dinner(),
    ]
    days, ctx = _fix391_seal([hollow], **family)
    assert "Muzeum Etnograficzne im. Seweryna Udzieli" in _fix391_names(days[0].items)
    assert len(_fix391_names(days[0].items)) >= 2, _fix391_names(days[0].items)
    _fix392_tail_ok(days[0], ctx)


def test_fix393_drive_between_two_parkings():
    from app.domain.models.plan import TransitMode

    # J1 D2: the car is at plac Wolnica and the next walk already leaves
    # from the lot under Kopiec. The drive between the lots is missing.
    rows = [
        _fix391_hop("12:40", "12:50", TransitMode.CAR, "Kraków", "Parking plac Wolnica", 2.0),
        _fix391_hop("12:50", "12:55", TransitMode.WALK, "Parking plac Wolnica", "Muzeum Etnograficzne im. Seweryna Udzieli", 0.25),
        _fix383_attr("Muzeum Etnograficzne im. Seweryna Udzieli", "12:55", "14:35", 50.0505, 19.9437),
        _fix391_hop("14:35", "14:39", TransitMode.WALK, "Muzeum Etnograficzne im. Seweryna Udzieli", "Parking plac Wolnica", 0.25),
        _fix391_hop("14:39", "14:41", TransitMode.WALK, "Parking pl. Paula McCartneya (pod Kopcem)", "Kopiec Kościuszki", 0.088),
        _fix383_attr("Kopiec Kościuszki", "14:41", "16:20", 50.0548, 19.8933),
        _fix391_dinner(),
    ]
    days, ctx = _fix391_seal([rows], group_type="family_kids", preferences=["kids_attractions"], date="2026-02-21")
    items = days[0].items
    assert any(
        _fix391_mode(it) == "car"
        and "Wolnica" in (it.from_location or "")
        and "Kopcem" in (it.to_location or "")
        for it in items
    ), [(it.from_location, it.to_location, _fix391_mode(it)) for it in items if _fix391_kind(it) == "transit"]
    assert "Kopiec Kościuszki" in _fix391_names(items)
    assert not any("public" in _fix391_mode(it) for it in items)
    assert not _fix391_hard_codes(days, ctx)


def test_fix391_thin_valley_trip_gets_a_second_stop():
    from app.domain.models.plan import TransitMode

    # J1 D3: ~55 min each way to Pieskowa Skała for the castle alone.
    pieskowa = [
        _fix391_hop("09:00", "09:55", TransitMode.CAR, "Kraków", "Parking pod Zamkiem w Pieskowej Skale", 32.0),
        _fix391_hop("09:55", "09:58", TransitMode.WALK, "Parking pod Zamkiem w Pieskowej Skale", "Zamek Pieskowa Skała", 0.12),
        _fix383_attr("Zamek Pieskowa Skała", "10:00", "11:30", 50.2451641, 19.7788312),
        _fix391_hop("11:30", "11:33", TransitMode.WALK, "Zamek Pieskowa Skała", "Parking pod Zamkiem w Pieskowej Skale", 0.12),
        _fix391_hop("11:33", "12:28", TransitMode.CAR, "Parking pod Zamkiem w Pieskowej Skale", "Parking przy Muzeum (al. 3 Maja)", 32.0),
        _fix391_hop("12:28", "12:30", TransitMode.WALK, "Parking przy Muzeum (al. 3 Maja)", "Muzeum Narodowe w Krakowie", 0.099),
        _fix383_attr("Muzeum Narodowe w Krakowie", "12:30", "14:00", 50.0604, 19.9235),
        _fix391_dinner(),
    ]
    # J8 D6: ~99 min of driving for an 81-minute visit at the Ojców castle.
    ojcow = [
        _fix391_hop("09:00", "09:50", TransitMode.CAR, "Kraków", "Parking Złota Góra (Ojcowski Park Narodowy)", 25.0),
        _fix391_hop("09:50", "09:58", TransitMode.WALK, "Parking Złota Góra (Ojcowski Park Narodowy)", "Zamek w Ojcowie", 0.6),
        _fix383_attr("Zamek w Ojcowie", "10:00", "11:21", 50.2117047, 19.8300564),
        _fix391_hop("11:21", "11:29", TransitMode.WALK, "Zamek w Ojcowie", "Parking Złota Góra (Ojcowski Park Narodowy)", 0.6),
        _fix391_hop("11:29", "12:18", TransitMode.CAR, "Parking Złota Góra (Ojcowski Park Narodowy)", "Parking przy Muzeum (al. 3 Maja)", 25.0),
        _fix391_hop("12:18", "12:20", TransitMode.WALK, "Parking przy Muzeum (al. 3 Maja)", "Muzeum Narodowe w Krakowie", 0.099),
        _fix383_attr("Muzeum Narodowe w Krakowie", "12:20", "13:40", 50.0604, 19.9235),
        _fix391_dinner(),
    ]
    cases = (
        (pieskowa, {"group_type": "family_kids", "preferences": ["kids_attractions", "nature_landscape"], "date": "2026-02-22"}),
        (ojcow, {"date": "2026-02-25"}),
    )
    for rows, extra in cases:
        days, ctx = _fix391_seal([rows], **extra)
        items = days[0].items
        stops, drive, visit = _fix391_valley(items)
        assert stops >= 2, _fix391_names(items)
        assert not (drive >= 40 and drive > visit), (drive, visit)
        maczuga = next(it for it in items if getattr(it, "name", "") == "Maczuga Herkulesa")
        assert maczuga.cost_estimate == 0
        assert maczuga.ticket_info.ticket_normal == 0
        assert 30 <= _span_minutes(maczuga) <= 60
        assert not any("public" in _fix391_mode(it) for it in items)
        assert not _fix391_hard_codes(days, ctx), [
            (it.start_time, _fix391_mode(it), getattr(it, "from_location", None), getattr(it, "to_location", None), getattr(it, "name", None))
            for it in items
        ]
        lots = {
            it.to_location for it in items
            if _fix391_kind(it) == ItemType.TRANSIT.value and _fix391_mode(it) == "car"
        }
        assert len(lots) <= 4
        assert len(_fix391_names(items)) <= 5
        assert next(
            it for it in items if _fix391_kind(it) == ItemType.DINNER_BREAK.value
        ).start_time >= "17:00"
