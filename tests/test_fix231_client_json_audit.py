"""
FIX #231 — audit plans generated from client JSON fixtures (json_miasta/).

Runs test-01..test-10 for Wrocław, Warszawa, Kraków, Katowice, Poznań.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

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


def _time_min(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _audit_day(day) -> list[str]:
    issues = []
    items = day.items or []
    attrs = [it for it in items if getattr(it, "type", None) and str(it.type) == "attraction"]
    ft_total = sum(
        int(getattr(it, "duration_min", 0) or 0)
        for it in items
        if getattr(it, "type", None) and str(it.type) == "free_time"
    )
    if len(attrs) < 2 and ft_total > 30:
        issues.append(f"day{day.day}: sparse ({len(attrs)} attr, {ft_total}min free_time)")
    if ft_total > 60:
        issues.append(f"day{day.day}: excessive free_time ({ft_total}min)")
    for it in items:
        if getattr(it, "type", None) and str(it.type) == "lunch_break":
            st = getattr(it, "start_time", None)
            if st and _time_min(st) > 840:
                issues.append(f"day{day.day}: late lunch {st}")
    return issues


@pytest.fixture(scope="module")
def plan_service():
    excel = Path("data") / "multi_city_attractions.xlsx"
    if not excel.is_file():
        excel = Path("data") / "zakopane.xlsx"
    return PlanService(POIRepository(str(excel)))


_FIXTURES = _fixture_paths()
_IDS = [f"{c}-{p.name}" for c, p in _FIXTURES]


@pytest.mark.parametrize("city,json_path", _FIXTURES, ids=_IDS)
def test_client_json_plan_quality(city, json_path, plan_service):
    if not json_path.is_file():
        pytest.skip(f"missing {json_path}")
    with open(json_path, encoding="utf-8") as f:
        payload = json.load(f)
    trip = TripInput(**payload)
    plan = plan_service.generate_plan(trip)
    all_issues = []
    for day in plan.days:
        all_issues.extend(_audit_day(day))
    assert not all_issues, f"{city}/{json_path.name}: " + "; ".join(all_issues)
