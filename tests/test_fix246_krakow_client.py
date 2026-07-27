"""FIX #246 — Kraków client feedback round 2 (json 1–10)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.application.services.plan_client_audit import audit_day, audit_transit_routing
from app.application.services.plan_service import PlanService
from app.domain.models.plan import ItemType
from app.domain.models.trip_input import TripInput
from app.domain.scoring.family_fit import is_child_oriented_attraction
from app.domain.scoring.preference_coverage import poi_covers_preference_report
from app.infrastructure.repositories import POIRepository
from tests.test_fix241_krakow_client import _audit_krakow

_JSON_ROOT = Path(__file__).resolve().parents[2] / "json_miasta" / "Kraków"

_KIDS_MARKERS = (
    "papugarnia", "kolejkowo", "pixel", "guliwer", "w budowie", "lego",
    "smoczy", "iluzj", "motyl", "fabryka cukier", "park wodny", "trampolin",
    "gojump", "smart kids", "miniciti", "zoo",
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


def _is_kids_name(name: str) -> bool:
    n = name.lower()
    return is_child_oriented_attraction({"name": n, "tags": []}) or any(
        k in n for k in _KIDS_MARKERS
    )


def _is_relax_or_water_name(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in (
        "park wodny", "bulwary", "błonia", "blonia", "planty", "spa", "term",
        "ogród botaniczny", "ogrod botaniczny", "kopiec krakusa", "rezerwat",
    ))


def _audit_krakow_246(plan, payload: dict, label: str) -> list[str]:
    issues = _audit_krakow(plan, payload, label)
    tg = payload.get("group", {}).get("type", "")
    prefs = set(payload.get("preferences") or [])
    num_days = payload.get("trip_length", {}).get("days", 1)
    trip_kids = 0
    trip_relax = 0

    for day in plan.days:
        items = day.items or []
        day_kids = 0
        day_relax = 0
        has_dinner_sugs = True

        for it in items:
            t = _type_val(it)
            if t == ItemType.ATTRACTION.value:
                name = getattr(it, "name", "") or ""
                nl = name.lower()
                if _is_kids_name(nl):
                    day_kids += 1
                    trip_kids += 1
                poi = {"name": name, "tags": []}
                if (
                    poi_covers_preference_report(poi, "relaxation")
                    or poi_covers_preference_report(poi, "water_attractions")
                    or _is_relax_or_water_name(name)
                ):
                    day_relax += 1
                    trip_relax += 1
                if "lustrzany labirynt" in nl:
                    if tg == "couples" and day.day == 2 and label == "test-08.json":
                        issues.append(f"{label} day{day.day}: lustrzany on couples nature D2")
                    if tg == "couples" and "kids_attractions" not in prefs and "nature_landscape" in prefs:
                        issues.append(f"{label} day{day.day}: lustrzany wrong couples profile")
                if "alvernia planet" in nl and tg == "solo" and "nature_landscape" in prefs:
                    issues.append(f"{label} day{day.day}: alvernia planet wrong solo nature")
            elif t == ItemType.TRANSIT.value:
                dur = int(getattr(it, "duration_min", 0) or 0)
                if dur > 35:
                    issues.append(
                        f"{label} day{day.day}: long transit {dur}m "
                        f"{getattr(it, 'from_location', '')}->{getattr(it, 'to_location', '')}"
                    )
            elif t == ItemType.DINNER_BREAK.value:
                sugs = getattr(it, "suggestions", None) or []
                if not sugs:
                    has_dinner_sugs = False

        if "local_food_experience" in prefs and day.day == num_days and not has_dinner_sugs:
            n_attr = sum(1 for it in items if _type_val(it) == ItemType.ATTRACTION.value)
            if n_attr >= 1:
                issues.append(f"{label} day{day.day}: dinner without suggestions")

        if tg == "couples" and {"water_attractions", "relaxation"} <= prefs and day_relax == 0:
            n_attr = sum(1 for it in items if _type_val(it) == ItemType.ATTRACTION.value)
            if n_attr >= 2:
                issues.append(f"{label} day{day.day}: no relaxation/water POI")

        issues.extend(audit_transit_routing(items))

    if tg == "family_kids" and "kids_attractions" in prefs and trip_kids < 2:
        issues.append(f"{label}: too few kids POI in trip ({trip_kids})")

    if tg == "couples" and {"water_attractions", "relaxation", "local_food_experience"} <= prefs:
        if trip_relax < 2:
            issues.append(f"{label}: relaxation/water under-covered ({trip_relax})")

    return issues


@pytest.mark.slow
@pytest.mark.parametrize("json_path", _paths(), ids=lambda p: p.name)
def test_krakow_fix246_client_feedback(json_path, plan_service):
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    plan = plan_service.generate_plan(TripInput(**payload))
    issues = _audit_krakow_246(plan, payload, json_path.name)
    assert not issues, "; ".join(issues[:15])
