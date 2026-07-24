"""FIX #242 — Warszawa client feedback regression (json 1–10)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.application.services.plan_client_audit import audit_day, audit_transit_routing
from app.application.services.plan_service import PlanService
from app.domain.models.plan import ItemType
from app.domain.models.trip_input import TripInput
from app.domain.planner.engine import is_evening_only_poi
from app.domain.planner.time_utils import time_to_minutes
from app.infrastructure.repositories import POIRepository

_JSON_ROOT = Path(__file__).resolve().parents[2] / "json_miasta" / "Warszawa"

_WAW_MICRO = (
    "pomnik syrenki", "pomnik syreny", "syrenki warszawskiej", "syreny warszawskiej",
    "pałac prezydencki", "palac prezydencki", "most świętokrzyski", "most swietokrzyski",
    "grób nieznanego", "grob nieznanego", "taras widokowy na dzwonnicy",
)
_NON_LOCAL_MEAL = ("forno", "pizza", "włosk", "wlosk", "italian")


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


def _audit_warszawa(plan, payload: dict, label: str) -> list[str]:
    issues: list[str] = []
    tg = payload.get("group", {}).get("type", "")
    prefs = set(payload.get("preferences") or [])
    style = payload.get("travel_style", "")
    adv = style == "adventure" or "adventure" in prefs
    nat_relax = {"nature_landscape", "relaxation"} <= prefs
    hist_prefs = {"history_mystery", "museum_heritage", "underground"} & prefs
    want_local = "local_food_experience" in prefs

    for day in plan.days:
        issues.extend(audit_day(day, day_label=f"{label} "))
        items = day.items or []
        day_has_history = False
        n_attr = 0
        n_micro = 0

        for it in items:
            t = _type_val(it)
            if t == ItemType.DINNER_BREAK.value and want_local:
                sugs = getattr(it, "suggestions", []) or []
                if sugs:
                    first = sugs[0]
                    name = (getattr(first, "name", "") or "").lower()
                    cuisine = (getattr(first, "cuisine_type", "") or "").lower()
                    if any(k in name for k in _NON_LOCAL_MEAL) or "italian" in cuisine:
                        issues.append(f"{label} day{day.day}: non-regional dinner first {name}")
            if t != ItemType.ATTRACTION.value:
                continue
            n_attr += 1
            name = (getattr(it, "name", "") or "").lower()
            st = getattr(it, "start_time", None)

            if any(k in name for k in _WAW_MICRO[:4]):
                issues.append(f"{label} day{day.day}: syreny forbidden {name}")
            if st and is_evening_only_poi({"name": name}) and time_to_minutes(st) < 17 * 60:
                issues.append(f"{label} day{day.day}: evening POI {name} at {st}")

            if tg == "family_kids" and any(k in name for k in _WAW_MICRO[:4]):
                issues.append(f"{label} day{day.day}: syreny bad for kids {name}")

            if tg == "friends" and adv and "active_sport" in prefs and "museum_heritage" not in prefs:
                for bad in (
                    "pałac kultury", "palac kultury", "pkin", "bulwary wiślane", "bulwary wislane",
                    "ogrody zamku", "ogrod zamku", "norblin", "centrum pieniądza", "centrum pieniadza",
                    "muzeum sztuki nowoczesnej",
                ):
                    if bad in name:
                        issues.append(f"{label} day{day.day}: adventure sport forbidden {name}")

            if tg == "friends" and adv and {"underground", "history_mystery"} <= prefs:
                if any(k in name for k in (
                    "most świętokrzyski", "most swietokrzyski", "grób nieznanego", "grob nieznanego",
                    "taras widokowy", "pałac prezydencki", "palac prezydencki",
                )):
                    issues.append(f"{label} day{day.day}: history adventure filler {name}")

            if tg == "solo" and nat_relax:
                for bad in ("browary warszawskie", "pałac prezydencki", "palac prezydencki",
                            "most świętokrzyski", "most swietokrzyski"):
                    if bad in name:
                        issues.append(f"{label} day{day.day}: nature relax forbidden {name}")

            if any(k in name for k in _WAW_MICRO[4:]):
                n_micro += 1
            if any(k in name for k in ("powstania", "polin", "podziemia", "schron", "muzeum")):
                day_has_history = True

            if tg == "friends" and adv and {"underground", "history_mystery", "museum_heritage"} <= prefs:
                if day_has_history and any(k in name for k in (
                    "most ", "grób", "grob", "taras widokowy", "plac europejski",
                )):
                    issues.append(f"{label} day{day.day}: generic after history {name}")

        num_days = payload.get("trip_length", {}).get("days", 1)
        if num_days >= 5 and n_attr < 2 and day.day < num_days:
            issues.append(f"{label} day{day.day}: sparse day ({n_attr} attractions)")
        if num_days >= 5 and day.day >= 4 and n_attr >= 2 and n_micro >= 2:
            issues.append(f"{label} day{day.day}: weak micro-heavy day ({n_micro} fillers)")

        issues.extend(audit_transit_routing(items))
    return issues


@pytest.mark.slow
@pytest.mark.parametrize("json_path", _paths(), ids=lambda p: p.name)
def test_warszawa_fix242_client_feedback(json_path, plan_service):
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    plan = plan_service.generate_plan(TripInput(**payload))
    issues = _audit_warszawa(plan, payload, json_path.name)
    assert not issues, "; ".join(issues[:12])
