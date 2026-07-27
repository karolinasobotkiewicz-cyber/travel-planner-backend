"""FIX #245 — Katowice client feedback round 2 (json 1–10)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.application.services.plan_client_audit import audit_day, audit_transit_routing
from app.application.services.plan_service import PlanService
from app.domain.models.plan import ItemType
from app.domain.models.trip_input import TripInput
from app.domain.scoring.family_fit import is_child_oriented_attraction
from app.domain.scoring.profile_poi_rules import poi_trip_repeat_key
from app.infrastructure.repositories import POIRepository
from tests.test_fix243_katowice_client import _audit_katowice

_JSON_ROOT = Path(__file__).resolve().parents[2] / "json_miasta" / "Katowice"


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


def _audit_katowice_245(plan, payload: dict, label: str) -> list[str]:
    issues = _audit_katowice(plan, payload, label)
    tg = payload.get("group", {}).get("type", "")
    prefs = set(payload.get("preferences") or [])
    style = payload.get("travel_style", "")
    adv = style == "adventure" or "adventure" in prefs
    num_days = payload.get("trip_length", {}).get("days", 1)

    repeat_counts: dict[str, int] = {}
    trip_has_water = False
    trip_kids_days: dict[int, bool] = {}
    guido_days: list[int] = []
    luiza_days: list[int] = []

    for day in plan.days:
        day_kids = False
        first_attr_min = None
        n_attr = 0
        day_names: list[str] = []

        for it in day.items or []:
            if _type_val(it) != ItemType.ATTRACTION.value:
                continue
            n_attr += 1
            name = (getattr(it, "name", "") or "").lower()
            day_names.append(name)
            st = getattr(it, "start_time", None)
            if st and first_attr_min is None:
                from app.domain.planner.time_utils import time_to_minutes
                first_attr_min = time_to_minutes(st)

            rk = poi_trip_repeat_key(getattr(it, "name", "") or "")
            if rk:
                repeat_counts[rk] = repeat_counts.get(rk, 0) + 1

            if is_child_oriented_attraction({"name": name, "tags": []}):
                day_kids = True

            if any(k in name for k in ("park wodny", "nemo", "wodny park", "tychy")):
                trip_has_water = True
            if "kopalnia guido" in name or name.strip() == "guido":
                guido_days.append(day.day)
            if "królowa luiza" in name or "krolowa luiza" in name:
                luiza_days.append(day.day)

        trip_kids_days[day.day] = day_kids

        min_needed = 3 if num_days >= 7 and day.day >= 7 else 2
        if n_attr < min_needed and day.day <= num_days:
            issues.append(f"{label} day{day.day}: sparse ({n_attr} attr, need {min_needed})")

        if tg == "friends" and adv and first_attr_min is not None and first_attr_min >= 12 * 60:
            issues.append(f"{label} day{day.day}: friends adventure starts after noon ({first_attr_min})")

        if len(day_names) != len(set(day_names)):
            issues.append(f"{label} day{day.day}: duplicate POI same day {day_names}")

    for rk, cnt in repeat_counts.items():
        if cnt > 1:
            issues.append(f"{label}: trip repeat {rk} x{cnt}")

    for g in guido_days:
        for l in luiza_days:
            if g == l:
                issues.append(f"{label}: Guido+Luiza same day {g}")
            elif abs(g - l) == 1:
                issues.append(f"{label}: Guido+Luiza consecutive days {g}/{l}")

    if tg == "family_kids" and "kids_attractions" in prefs:
        for d, has_k in trip_kids_days.items():
            if d >= 2 and not has_k:
                issues.append(f"{label} day{d}: no kids attraction")

    if tg == "couples" and "water_attractions" in prefs and not trip_has_water:
        issues.append(f"{label}: no water attraction in trip")

    if tg == "solo" and {"nature_landscape", "relaxation"} <= prefs:
        for day in plan.days:
            for it in day.items or []:
                if _type_val(it) != ItemType.ATTRACTION.value:
                    continue
                nm = (getattr(it, "name", "") or "").lower()
                if "muzeum" in nm or "planetarium" in nm:
                    issues.append(f"{label} day{day.day}: museum/planetarium in solo nature+relax {nm}")

    for day in plan.days:
        issues.extend(audit_transit_routing(day.items or []))

    return issues


@pytest.mark.slow
@pytest.mark.parametrize("json_path", _paths(), ids=lambda p: p.name)
def test_katowice_fix245_client_feedback(json_path, plan_service):
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    plan = plan_service.generate_plan(TripInput(**payload))
    issues = _audit_katowice_245(plan, payload, json_path.name)
    assert not issues, "; ".join(issues[:15])
