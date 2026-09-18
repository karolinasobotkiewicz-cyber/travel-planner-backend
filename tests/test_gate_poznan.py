"""FIX #351: Poznań client-mail gate over the ten JSONs."""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path

import pytest

from app.application.services.plan_service import PlanService, _fold_place_label, _timeline_satellite_kind
from app.domain.models.trip_input import TripInput
from app.domain.models.plan import ItemType
from app.domain.validators.client_invariants import audit_plan, _tv
from app.infrastructure.repositories.poi_repository import POIRepository
from app.domain.planner.time_utils import time_to_minutes

_HERE = Path(__file__).resolve().parent
_JSON_DIR = _HERE.parents[1] / "json_miasta" / "Poznań"
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


@pytest.mark.slow
def test_poznan_client_mail_defects_are_gone():
    if not _JSON_DIR.exists() or not _EXCEL.exists():
        pytest.skip("Poznań fixtures are not present in this checkout")
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
        ctx = {
            "day_start": window.get("start") or "09:00",
            "day_end": window.get("end"),
            "requested_city": "Poznań",
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
            last_en = None
            seen: set[str] = set()
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
                if tv == ItemType.LUNCH_BREAK.value:
                    has_lunch = True
                if tv == ItemType.ATTRACTION.value:
                    nm = getattr(it, "name", "") or ""
                    seen.add(_fold_place_label(nm))
                    dur = int(getattr(it, "duration_min", 0) or 0)
                    folded = _fold_place_label(nm)
                    if kids and dur and dur < 40 and (
                        "pixel xl" in folded or "makiet" in folded
                    ):
                        hits.append(
                            f"J{num} D{day.day} [short_kids] {nm} {dur} min"
                        )
                    pk = getattr(it, "parking", None)
                    plat = getattr(pk, "lat", None) if pk else None
                    plng = getattr(pk, "lng", None) if pk else None
                    alat = getattr(it, "lat", None)
                    alng = getattr(it, "lng", None)
                    if (
                        "stare zoo" in folded
                        and plat not in (None, 0, 0.0)
                        and alat not in (None, 0, 0.0)
                    ):
                        from app.infrastructure.routing.haversine import haversine_km
                        km = haversine_km(
                            float(alat), float(alng), float(plat), float(plng),
                        )
                        if km > 0.40:
                            hits.append(
                                f"J{num} D{day.day} [zoo_parking] "
                                f"{km:.2f} km from gate"
                            )
                if tv == ItemType.TRANSIT.value:
                    frm = (getattr(it, "from_location", "") or "").strip()
                    ff = _fold_place_label(frm)
                    if (
                        ff
                        and len(ff) >= 12
                        and "poznań" not in ff
                        and "poznan" not in ff
                        and "centrum" not in ff
                        and not any(ff in a or a in ff for a in seen)
                        and "muzeum" in ff
                    ):
                        hits.append(
                            f"J{num} D{day.day} [ghost_from] {frm}"
                        )
                    dest = (getattr(it, "to_location", "") or "").strip()
                    if dest:
                        seen.add(_fold_place_label(dest))
            if (
                win_end >= 18 * 60
                and has_lunch
                and not has_dinner
                and last_en is not None
                and last_en <= 16 * 60 + 30
            ):
                hits.append(f"J{num} D{day.day} [no_dinner]")
            attrs = [
                it for it in (day.items or [])
                if _tv(it) == ItemType.ATTRACTION.value
            ]
            led = [
                getattr(it, "name", "") or ""
                for it in attrs
                if _timeline_satellite_kind(getattr(it, "name", "") or "") == "lednica"
            ]
            if led and len(attrs) < 2:
                hits.append(
                    f"J{num} D{day.day} [lednica_only] {led[0]}"
                )
            if kids:
                names = [getattr(it, "name", "") or "" for it in attrs]
                folded = [_fold_place_label(n) for n in names]
                saw_zoo = any("stare zoo" in f for f in folded)
                kids_n = sum(
                    1 for f in folded
                    if any(k in f for k in (
                        "pixel xl", "makiet", "zoo", "termy malta",
                        "historyland", "palmarnia", "rogalow", "enigma",
                    ))
                )
                adult_after = False
                zoo_seen = False
                for f in folded:
                    if "stare zoo" in f:
                        zoo_seen = True
                        continue
                    if zoo_seen and any(k in f for k in (
                        "ratusz", "stary rynek", "plac wolnosci",
                        "park mickiewicza", "park szelagowski",
                    )):
                        adult_after = True
                if saw_zoo and adult_after and kids_n < 2:
                    hits.append(
                        f"J{num} D{day.day} [kids_adult_afternoon]"
                    )
            ft_labels = []
            for it in day.items or []:
                if _tv(it) != ItemType.FREE_TIME.value:
                    continue
                raw = getattr(it, "start_time", None)
                if not raw:
                    continue
                try:
                    if time_to_minutes(raw) < 18 * 60:
                        continue
                except Exception:
                    continue
                ft_labels.append((getattr(it, "label", "") or "").strip())
            if len(ft_labels) >= 2 and ft_labels[0] == ft_labels[1] and ft_labels[0]:
                hits.append(
                    f"J{num} D{day.day} [dup_evening_ft] {ft_labels[0]!r}"
                )

    assert not hits, (
        "Poznań client-mail defects still in the JSON fixtures:\n"
        + "\n".join(hits)
    )
