"""FIX #317 — live Wrocław JSON 1–10 against the client invariant auditor.

generate_plan once per file. P0 hops/physics/gaps/meals and P1 region/empty
must all stay clean after the guardian last word.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.application.services.plan_service import PlanService
from app.domain.models.trip_input import TripInput
from app.domain.validators.client_invariants import audit_plan
from app.infrastructure.repositories.poi_repository import POIRepository

_ALL = (
    "anonymous_gap",
    "missing_hop",
    # FIX #325: a ride whose stop was stripped is a ride to nowhere.
    "dangling_hop",
    # FIX #326: one break and one ride between stops, never a sliver wall.
    "fragmented",
    # FIX #328: one place, one day — no POI twice in the same trip.
    "trip_repeat",
    "dishonest_leg",
    "urban_car",
    "overlap",
    "after_day_end",
    "meal_identity",
    "mixed_regions",
    "empty_day",
)

_HERE = Path(__file__).resolve()
_JSON_DIR = _HERE.parents[2] / "json_miasta" / "Wrocław"
_EXCEL = _HERE.parents[1] / "data" / "zakopane.xlsx"

_JSON_IDS = [f"{i:02d}" for i in range(1, 11)]


def _json_path(num: str) -> Path:
    return _JSON_DIR / f"test-{num}.json"


def _generate(num: str):
    path = _json_path(num)
    if not path.exists():
        pytest.skip(f"missing {path}")
    if not _EXCEL.exists():
        pytest.skip(f"missing POI excel {_EXCEL}")
    os.environ["ORS_ENABLED"] = "false"
    payload = json.loads(path.read_text(encoding="utf-8"))
    trip = TripInput(**payload)
    svc = PlanService(POIRepository(str(_EXCEL)))
    return svc.generate_plan(trip), payload


@pytest.mark.parametrize("num", _JSON_IDS)
def test_wroclaw_json_client_invariants(num):
    plan, payload = _generate(num)
    # FIX #324: window and profile decide short_day and profile_conflict.
    ctx = {
        "day_start": "09:00",
        "day_end": (payload.get("daily_time_window") or {}).get("end"),
        "requested_city": "Wrocław",
        "has_car": True,
        "travel_style": payload.get("travel_style"),
        "group_type": (payload.get("group") or {}).get("type"),
    }
    try:
        win = getattr(plan, "daily_time_window", None)
        if win and getattr(win, "start", None):
            ctx["day_start"] = win.start
    except Exception:
        pass
    defects = [
        d for d in audit_plan(plan.days, context=ctx)
        if d.code in _ALL
    ]
    if defects:
        lines = "\n".join(
            f"  [{d.code}] D{d.day}: {d.message}" for d in defects
        )
        pytest.fail(
            f"Wrocław test-{num}.json still has {len(defects)} "
            f"client defects:\n{lines}"
        )
