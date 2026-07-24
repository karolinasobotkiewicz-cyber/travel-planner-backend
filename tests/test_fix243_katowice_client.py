"""FIX #243 — Katowice client feedback regression (json 1–10)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.application.services.plan_client_audit import audit_day, audit_transit_routing
from app.application.services.plan_service import PlanService
from app.domain.models.plan import ItemType
from app.domain.models.trip_input import TripInput
from app.infrastructure.repositories import POIRepository

_JSON_ROOT = Path(__file__).resolve().parents[2] / "json_miasta" / "Katowice"

_KAT_CHURCH = (
    "św. anny", "sw. anny", "świętego michała", "swietego michala",
    "michała archanioła", "michala archanioła",
)
_KAT_MICRO = ("spodek", "rynek w katowicach", "rynek katowic")
_KAT_INDUSTRIAL = (
    "kopalnia guido", "guido", "królowa luiza", "krolowa luiza",
    "carboneum", "galeria szyb wilson", "szyb wilson",
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


def _audit_katowice(plan, payload: dict, label: str) -> list[str]:
    issues: list[str] = []
    tg = payload.get("group", {}).get("type", "")
    prefs = set(payload.get("preferences") or [])
    style = payload.get("travel_style", "")
    adv = style == "adventure" or "adventure" in prefs
    nat_relax = {"nature_landscape", "relaxation"} <= prefs
    num_days = payload.get("trip_length", {}).get("days", 1)
    trip_spodek = False
    industrial_hits = 0

    for day in plan.days:
        issues.extend(audit_day(day, day_label=f"{label} "))
        items = day.items or []
        n_attr = 0
        n_micro = 0
        free_min = 0
        day_industrial = False

        for it in items:
            t = _type_val(it)
            if t == ItemType.FREE_TIME.value:
                free_min += int(getattr(it, "duration_min", 0) or 0)
            if t != ItemType.ATTRACTION.value:
                continue
            n_attr += 1
            name = (getattr(it, "name", "") or "").lower()

            if "spodek" in name:
                trip_spodek = True
                if tg in ("family_kids", "couples") or (tg == "solo" and nat_relax) or (tg == "friends" and adv):
                    issues.append(f"{label} day{day.day}: spodek forbidden {name}")

            if tg == "family_kids":
                if day.day == 1 and any(k in name for k in ("rynek w katowicach", "rynek katowic")):
                    issues.append(f"{label} day{day.day}: rynek forbidden family day1 {name}")
                if any(k in name for k in _KAT_CHURCH):
                    issues.append(f"{label} day{day.day}: church forbidden family_kids {name}")

            if tg == "couples" and style == "cultural":
                if any(k in name for k in ("św. anny", "sw. anny")) and "parafia" in name:
                    issues.append(f"{label} day{day.day}: anny forbidden couples cultural {name}")

            if tg == "friends" and adv and "history_mystery" in prefs:
                if any(k in name for k in _KAT_INDUSTRIAL):
                    day_industrial = True
                    industrial_hits += 1
                if any(k in name for k in ("rynek w katowicach", "rynek katowic", "spodek")):
                    issues.append(f"{label} day{day.day}: micro filler friends adventure {name}")

            if tg == "solo" and nat_relax:
                for bad in ("spodek", "pijalnia czekolady", "muzeum historii katowic", "planetarium"):
                    if bad in name:
                        issues.append(f"{label} day{day.day}: solo relax forbidden {name}")

            if any(k in name for k in _KAT_MICRO[1:]):
                n_micro += 1

        if num_days >= 7 and day.day == 4 and tg == "couples":
            if n_attr < 3:
                issues.append(f"{label} day{day.day}: sparse day4 ({n_attr} attr, free={free_min}m)")
            if free_min > 90:
                issues.append(f"{label} day{day.day}: too much free time day4 ({free_min}m)")

        if num_days >= 5 and n_attr < 2 and day.day < num_days:
            issues.append(f"{label} day{day.day}: sparse day ({n_attr} attractions)")

        issues.extend(audit_transit_routing(items))

    if tg == "friends" and adv and "history_mystery" in prefs and industrial_hits == 0:
        issues.append(f"{label}: no industrial POI (Guido/Sztolnia/Wilson) in trip")

    if trip_spodek and tg == "solo" and nat_relax:
        issues.append(f"{label}: spodek in solo relax plan")

    return issues


@pytest.mark.slow
@pytest.mark.parametrize("json_path", _paths(), ids=lambda p: p.name)
def test_katowice_fix243_client_feedback(json_path, plan_service):
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    plan = plan_service.generate_plan(TripInput(**payload))
    issues = _audit_katowice(plan, payload, json_path.name)
    assert not issues, "; ".join(issues[:12])
