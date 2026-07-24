"""FIX #240 — Wrocław client feedback regression (json 1–10)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.application.services.plan_client_audit import audit_day, audit_transit_routing
from app.application.services.plan_service import PlanService
from app.domain.models.plan import ItemType
from app.domain.planner.engine import is_evening_only_poi
from app.domain.planner.time_utils import time_to_minutes
from app.domain.models.trip_input import TripInput
from app.infrastructure.repositories import POIRepository

_JSON_ROOT = Path(__file__).resolve().parents[2] / "json_miasta" / "Wrocław"


def _paths():
    if not _JSON_ROOT.is_dir():
        return []
    return sorted(_JSON_ROOT.glob("test-*.json"))


@pytest.fixture(scope="module")
def plan_service():
    excel = Path("data") / "multi_city_attractions.xlsx"
    return PlanService(POIRepository(str(excel)))


def _type_val(item) -> str:
    t = getattr(item, "type", None)
    return str(t.value if hasattr(t, "value") else t)


def _audit_wroclaw(plan, payload: dict, label: str) -> list[str]:
    issues: list[str] = []
    tg = payload.get("group", {}).get("type", "")
    prefs = set(payload.get("preferences") or [])
    winter = str(payload.get("trip_length", {}).get("start_date", "")).endswith("-02")

    for day in plan.days:
        issues.extend(audit_day(day, day_label=f"{label} "))
        items = day.items or []
        for it in items:
            if _type_val(it) != ItemType.ATTRACTION.value:
                continue
            name = (getattr(it, "name", "") or "").lower()
            st = getattr(it, "start_time", None)
            if tg == "family_kids":
                for bad in (
                    "dworzec świebodzki", "dworzec swiebodzki",
                    "muzeum uniwersytetu", "browar stu mostów", "browar stu mostow",
                ):
                    if bad in name:
                        issues.append(f"{label} day{day.day}: family_kids forbidden {name}")
            if winter and "fontanna multimedialna" in name:
                issues.append(f"{label} day{day.day}: fontanna in winter")
            if winter and "wojsławice" in name:
                issues.append(f"{label} day{day.day}: arboretum wojsławice in winter")
            if st and is_evening_only_poi({"name": name}) and time_to_minutes(st) < 17 * 60:
                issues.append(f"{label} day{day.day}: evening POI {name} at {st}")
            if {"active_sport", "history_mystery"} <= prefs and "hala targowa" in name:
                issues.append(f"{label} day{day.day}: hala targowa wrong prefs")
        for it in items:
            if _type_val(it) == ItemType.DINNER_BREAK.value:
                st = getattr(it, "start_time", None)
                de = payload.get("daily_time_window", {}).get("end", "19:00")
                if st and time_to_minutes(de) >= 19 * 60 and time_to_minutes(st) < 17 * 60 + 30:
                    issues.append(f"{label} day{day.day}: dinner too early {st}")
        issues.extend(audit_transit_routing(items))
    return issues


@pytest.mark.slow
@pytest.mark.parametrize("json_path", _paths(), ids=lambda p: p.name)
def test_wroclaw_fix240_client_feedback(json_path, plan_service):
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    plan = plan_service.generate_plan(TripInput(**payload))
    issues = _audit_wroclaw(plan, payload, json_path.name)
    assert not issues, "; ".join(issues[:10])
