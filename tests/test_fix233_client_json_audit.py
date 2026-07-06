"""
FIX #233 — audit plans from client JSON fixtures (json_miasta/).

Runs test-01..test-10 for Wrocław, Warszawa, Kraków, Katowice, Poznań.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.application.services.plan_service import PlanService
from app.domain.models.plan import ItemType
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
    attrs = [it for it in items if getattr(it, "type", None) == ItemType.ATTRACTION]
    ft_total = sum(
        int(getattr(it, "duration_min", 0) or 0)
        for it in items
        if getattr(it, "type", None) == ItemType.FREE_TIME
    )
    if len(attrs) < 2 and ft_total > 25:
        issues.append(f"day{day.day}: sparse ({len(attrs)} attr, {ft_total}min free_time)")
    if ft_total > 60:
        issues.append(f"day{day.day}: excessive free_time ({ft_total}min)")
    for it in items:
        if getattr(it, "type", None) == ItemType.LUNCH_BREAK:
            st = getattr(it, "start_time", None)
            if st and _time_min(st) > 840:
                issues.append(f"day{day.day}: late lunch {st}")
    # generic restaurant labels (FIX #233)
    for it in items:
        if getattr(it, "type", None) in (ItemType.LUNCH_BREAK, ItemType.DINNER_BREAK):
            for sug in getattr(it, "suggestions", []) or []:
                name = getattr(sug, "name", None) or (sug.get("name") if isinstance(sug, dict) else "")
                if name and "restauracja w centrum" in str(name).lower():
                    issues.append(f"day{day.day}: generic restaurant '{name}'")
    # parking all free
    free_park = paid_park = 0
    for it in attrs:
        park = getattr(it, "parking", None)
        if not park:
            continue
        pt = getattr(park, "parking_type", None)
        val = pt.value if hasattr(pt, "value") else str(pt)
        if val == "free":
            free_park += 1
        elif val == "paid":
            paid_park += 1
    if free_park >= 5 and paid_park == 0:
        issues.append(f"day{day.day}: all parking marked free ({free_park} attrs)")
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
