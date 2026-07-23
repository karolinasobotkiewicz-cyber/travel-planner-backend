"""FIX #239 — client JSON audit (routing, transits, free_time, idle gaps)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.application.services.plan_client_audit import audit_day
from app.application.services.plan_service import PlanService
from app.domain.models.trip_input import TripInput
from app.infrastructure.repositories import POIRepository

_JSON_ROOT = Path(__file__).resolve().parents[2] / "json_miasta"
_CITIES = ("Wrocław", "Warszawa", "Kraków", "Katowice", "Poznań")


def _fixture_paths():
    out = []
    for city in _CITIES:
        folder = _JSON_ROOT / city
        if not folder.is_dir():
            continue
        for p in sorted(folder.glob("test-*.json")):
            out.append((city, p))
    return out


@pytest.fixture(scope="module")
def plan_service():
    excel = Path("data") / "multi_city_attractions.xlsx"
    if not excel.is_file():
        excel = Path("data") / "zakopane.xlsx"
    return PlanService(POIRepository(str(excel)))


_FIXTURES = _fixture_paths()
_IDS = [f"{c}-{p.name}" for c, p in _FIXTURES]


@pytest.mark.slow
@pytest.mark.parametrize("city,json_path", _FIXTURES, ids=_IDS)
def test_client_json_fix239_quality(city, json_path, plan_service):
    if not json_path.is_file():
        pytest.skip(f"missing {json_path}")
    with open(json_path, encoding="utf-8") as f:
        payload = json.load(f)
    trip = TripInput(**payload)
    plan = plan_service.generate_plan(trip)
    all_issues = []
    for day in plan.days:
        all_issues.extend(audit_day(day, day_label=f"{city}/{json_path.name} "))
    assert not all_issues, "; ".join(all_issues[:12]) + (
        f" (+{len(all_issues) - 12} more)" if len(all_issues) > 12 else ""
    )
