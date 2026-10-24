"""FIX #349/#350: Kraków client-mail gate over the ten JSONs.

Fails car teleports, idle mornings, winter-dusk parks, stacked walking
parks, long holes, and the #348 hop-clock seals they sit on.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
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
            if len(sat_kinds) >= 2:
                hits.append(
                    f"J{num} D{day.day} [second_satellite] {sorted(sat_kinds)}"
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

    if hits:
        Path(__file__).with_name("_gate379_hits.txt").write_text(
            "\n".join(hits), encoding="utf-8",
        )
    assert not hits, (
        "Kraków car/physics defects still in the client JSONs:\n"
        + "\n".join(hits)
    )
