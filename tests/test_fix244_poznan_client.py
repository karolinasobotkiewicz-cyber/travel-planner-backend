"""FIX #244 — Poznań client feedback regression (json 1–10)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.application.services.plan_client_audit import audit_day, audit_transit_routing
from app.application.services.plan_service import PlanService
from app.domain.models.plan import ItemType
from app.domain.models.trip_input import TripInput
from app.infrastructure.repositories import POIRepository

_JSON_ROOT = Path(__file__).resolve().parents[2] / "json_miasta" / "Poznań"

_POZ_MICRO = ("okrąglak", "okraglak", "domy kupieckie", "ratusz w poznaniu")
_NON_LOCAL_MEAL = (
    "forno", "pizza", "włosk", "wlosk", "italian", "gruzi", "georgian", "khinkali",
)


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


def _is_zoo_name(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in ("nowe zoo", "stare zoo")) or (
        "zoo" in n and "mini" not in n
    )


def _is_museum_name(name: str) -> bool:
    n = name.lower()
    return "muzeum" in n or "museum" in n


def _audit_poznan(plan, payload: dict, label: str) -> list[str]:
    issues: list[str] = []
    tg = payload.get("group", {}).get("type", "")
    prefs = set(payload.get("preferences") or [])
    style = payload.get("travel_style", "")
    adv = style == "adventure" or "adventure" in prefs
    nat_relax = {"nature_landscape", "relaxation"} <= prefs
    want_local = "local_food_experience" in prefs
    num_days = payload.get("trip_length", {}).get("days", 1)

    for day in plan.days:
        issues.extend(audit_day(day, day_label=f"{label} "))
        items = day.items or []
        n_attr = 0
        n_mus = 0
        zoo_names: list[str] = []
        free_min = 0

        for it in items:
            t = _type_val(it)
            if t == ItemType.FREE_TIME.value:
                free_min += int(getattr(it, "duration_min", 0) or 0)
            if t == ItemType.DINNER_BREAK.value and want_local:
                sugs = getattr(it, "suggestions", []) or []
                if sugs:
                    first = sugs[0]
                    name = (getattr(first, "name", "") or "").lower()
                    cuisine = (getattr(first, "cuisine_type", "") or "").lower()
                    if any(k in name for k in _NON_LOCAL_MEAL) or any(
                        k in cuisine for k in ("italian", "georgian", "gruzi")
                    ):
                        issues.append(f"{label} day{day.day}: non-regional dinner {name}")
            if t != ItemType.ATTRACTION.value:
                continue
            n_attr += 1
            name = getattr(it, "name", "") or ""
            nl = name.lower()
            dur = int(getattr(it, "duration_min", 0) or 0)

            if _is_zoo_name(nl):
                zoo_names.append(nl)
            if _is_museum_name(nl):
                n_mus += 1

            if tg == "friends" and adv:
                if any(k in nl for k in _POZ_MICRO):
                    issues.append(f"{label} day{day.day}: micro forbidden friends adv {name}")
                if "pixel xl" in nl or "pixel" in nl:
                    if {"underground", "history_mystery", "museum_heritage"} <= prefs:
                        issues.append(f"{label} day{day.day}: pixel wrong profile {name}")

            if tg == "family_kids" and ("pixel xl" in nl or "pixel" in nl):
                if dur > 0 and dur < 45:
                    issues.append(f"{label} day{day.day}: pixel too short ({dur}m)")

            if tg == "solo" and nat_relax:
                if any(k in nl for k in ("pijalnia czekolady", "spodek")):
                    issues.append(f"{label} day{day.day}: solo relax forbidden {name}")

        if len(zoo_names) >= 2:
            issues.append(f"{label} day{day.day}: double zoo {zoo_names}")

        max_mus = 1 if (tg == "couples" and style == "cultural" and "relaxation" in prefs) else 2
        if n_mus > max_mus:
            issues.append(f"{label} day{day.day}: museum stack ({n_mus}>{max_mus})")

        if num_days >= 5 and n_attr < 1 and day.day < num_days:
            issues.append(f"{label} day{day.day}: empty day")
        if num_days >= 7 and day.day == 7 and n_attr < 2:
            issues.append(f"{label} day{day.day}: sparse last day ({n_attr} attr)")
        if num_days >= 5 and day.day >= 4 and free_min > 120 and n_attr < 3:
            issues.append(f"{label} day{day.day}: idle afternoon (free={free_min}m)")

        issues.extend(audit_transit_routing(items))
    return issues


@pytest.mark.slow
@pytest.mark.parametrize("json_path", _paths(), ids=lambda p: p.name)
def test_poznan_fix244_client_feedback(json_path, plan_service):
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if payload.get("location", {}).get("city", "").lower() not in ("poznań", "poznan"):
        pytest.skip("fixture not Poznań")
    plan = plan_service.generate_plan(TripInput(**payload))
    issues = _audit_poznan(plan, payload, json_path.name)
    assert not issues, "; ".join(issues[:12])
