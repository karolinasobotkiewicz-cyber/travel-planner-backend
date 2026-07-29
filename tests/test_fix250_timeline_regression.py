"""FIX #250 — timeline quality regression (day_start, overlaps, transits, budget)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.application.services.plan_client_audit import audit_day
from app.application.services.plan_service import PlanService
from app.domain.models.trip_input import TripInput
from app.infrastructure.repositories import POIRepository

_JSON = Path(__file__).resolve().parents[2] / "json_miasta"
_SAMPLES = [
    ("Poznań", "test-05.json"),
    ("Wrocław", "test-01.json"),
    ("Warszawa", "test-04.json"),
    ("Kraków", "test-02.json"),
    ("Katowice", "test-01.json"),
]


@pytest.fixture(scope="module")
def plan_service():
    excel = Path("data") / "multi_city_attractions.xlsx"
    return PlanService(POIRepository(str(excel)))


@pytest.mark.slow
@pytest.mark.parametrize("city,filename", _SAMPLES, ids=[f"{c}-{f}" for c, f in _SAMPLES])
def test_fix250_timeline_quality(city, filename, plan_service):
    path = _JSON / city / filename
    if not path.is_file():
        pytest.skip(str(path))
    payload = json.loads(path.read_text(encoding="utf-8"))
    plan = plan_service.generate_plan(TripInput(**payload))
    day_start = payload.get("daily_time_window", {}).get("start", "09:00")
    daily_limit = payload.get("budget", {}).get("daily_limit")
    issues = []
    for day in plan.days:
        issues.extend(
            audit_day(
                day,
                day_label=f"{city}/{filename} ",
                day_start=day_start,
                daily_limit=daily_limit,
            )
        )
    assert not issues, "; ".join(issues[:10])
