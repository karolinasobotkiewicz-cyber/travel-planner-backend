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

from app.application.services.plan_service import PlanService
from app.domain.models.trip_input import TripInput
from app.domain.validators.client_invariants import audit_plan
from app.infrastructure.repositories.poi_repository import POIRepository

_HERE = Path(__file__).resolve().parent
_JSON_DIR = _HERE.parents[1] / "json_miasta" / "Kraków"
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
            if d.code in WATCH:
                hits.append(f"J{num} D{d.day} [{d.code}] {d.message}")

    assert not hits, (
        "Kraków car/physics defects still in the client JSONs:\n"
        + "\n".join(hits)
    )
