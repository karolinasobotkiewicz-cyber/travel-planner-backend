"""Regression gate over the ten Wrocław JSONs the client reviews.

The auditor in `client_invariants` already knows every defect class she has
reported. This test runs it over all ten plans and compares the result with
`KNOWN_OPEN` below — the defects we have accepted for now, each with the reason
it is still open. A new defect fails the build; a fixed one has to be deleted
from the baseline, so the list can only shrink.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

import pytest

from app.application.services.plan_service import PlanService
from app.domain.models.trip_input import TripInput
from app.domain.planner.city_copy import hub_poi_load_cities
from app.domain.validators.client_invariants import _fold, audit_plan
from app.infrastructure.repositories.load_multi_city import load_multi_city_poi
from app.infrastructure.repositories.poi_repository import POIRepository

_HERE = Path(__file__).resolve().parent
_JSON_DIR = _HERE.parents[1] / "json_miasta" / "Wrocław"
_EXCEL = _HERE.parents[0] / "data" / "zakopane.xlsx"
_MULTI = _HERE.parents[0] / "data" / "multi_city_attractions.xlsx"

# (json number, defect code) -> why it is still open.
KNOWN_OPEN: dict[tuple[int, str], str] = {
    (3, "missing_hop"): "first stop of the day has no lead ride from day_start",
    (3, "meal_identity"): "meal caption not synced with the booked venue",
    (3, "long_free_time"): "city pool exhausted for friends/adventure",
    (8, "fragmented"): "three technical mini-breaks in a row",
    (8, "long_free_time"): "satellite day, morning hole before the drive out",
    (9, "long_free_time"): "solo nature/relax pool exhausted (two days)",
    (9, "hop_vs_coords"): "distance_km not refreshed when geometry is restamped",
}


@pytest.fixture(scope="module")
def poi_meta() -> dict:
    if not _MULTI.exists():
        return {}
    cities = hub_poi_load_cities("Wrocław") or ["Wrocław"]
    out: dict = {}
    for p in load_multi_city_poi(str(_MULTI), cities):
        nm = p.get("name") or p.get("Name") or ""
        if nm:
            out.setdefault(_fold(nm), {
                "opening_hours": p.get("opening_hours"),
                "opening_hours_seasonal": p.get("opening_hours_seasonal"),
                "time_max": p.get("time_max"),
                "time_min": p.get("time_min"),
                "kids_only": p.get("kids_only"),
                "target_groups": p.get("target_groups"),
                "type_of_attraction": p.get("type_of_attraction"),
            })
    return out


@pytest.mark.slow
def test_wroclaw_defects_do_not_grow(poi_meta):
    if not _JSON_DIR.exists() or not _EXCEL.exists():
        pytest.skip("Wrocław fixtures are not present in this checkout")
    os.environ.setdefault("ORS_ENABLED", "false")
    svc = PlanService(POIRepository(str(_EXCEL)))

    found: Counter = Counter()
    detail: list[str] = []
    for num in range(1, 11):
        path = _JSON_DIR / f"test-{num:02d}.json"
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        plan = svc.generate_plan(TripInput(**payload))
        window = payload.get("daily_time_window") or {}
        ctx = {
            "day_start": window.get("start") or "09:00",
            "day_end": window.get("end"),
            "requested_city": "Wrocław",
            "has_car": True,
            "travel_style": payload.get("travel_style"),
            "group_type": (payload.get("group") or {}).get("type"),
            "children_age": (payload.get("group") or {}).get("children_age"),
            "preferences": payload.get("preferences") or [],
            "poi_meta": poi_meta,
        }
        for d in audit_plan(plan.days, context=ctx):
            found[(num, d.code)] += 1
            detail.append(f"J{num} [{d.code}] {d.message}")

    new = sorted(k for k in found if k not in KNOWN_OPEN)
    fixed = sorted(k for k in KNOWN_OPEN if k not in found)
    report = "\n".join(detail)
    assert not new, (
        "Nowe defekty (dopisz naprawę, nie baseline):\n"
        + "\n".join(f"  J{n} {code}" for n, code in new)
        + f"\n\nPełny audyt:\n{report}"
    )
    assert not fixed, (
        "Te defekty są już naprawione — usuń je z KNOWN_OPEN:\n"
        + "\n".join(f"  J{n} {code}" for n, code in fixed)
    )
