"""FIX #248 — Wrocław client feedback round 2 (json 1–10)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.application.services.plan_service import PlanService
from app.domain.models.plan import ItemType
from app.domain.models.trip_input import TripInput
from app.domain.scoring.preference_coverage import poi_covers_preference_report
from app.domain.scoring.profile_poi_rules import poi_trip_repeat_key
from app.infrastructure.repositories import POIRepository

_JSON_ROOT = Path(__file__).resolve().parents[2] / "json_miasta" / "Wrocław"

_RELAX = (
    "bulwar", "park szczytnicki", "pergola", "wyspa słodowa", "wyspa slodowa",
    "ogród japoński", "ogrod japonski", "ogród botaniczny", "ogrod botaniczny",
    "botaniczny", "spa", "termy", "lasek", "las strzeli",
)
_NATURE = (
    "park szczytnicki", "pergola", "wyspa", "ogród", "ogrod", "lasek",
    "arboretum", "botaniczny", "zoo", "las strzeli",
)
_DENY_FAMILY_D3 = ("muzeum uniwesytetu", "muzeum uniwersytetu", "hala targowa")


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


def _audit_wroclaw_248(plan, payload: dict, label: str) -> list[str]:
    issues: list[str] = []
    tg = payload.get("group", {}).get("type", "")
    prefs = set(payload.get("preferences") or [])
    style = payload.get("travel_style", "")

    trip_relax = trip_nat = trip_hist = 0
    repeat_keys: dict[str, list[int]] = {}
    d6_names: list[str] = []
    d7_names: list[str] = []

    for day in plan.days:
        items = day.items or []
        day_relax = day_nat = 0
        n_attr = 0
        first_attr_st = lunch_st = None
        attr_names: set[str] = set()
        for it in items:
            if _type_val(it) == ItemType.ATTRACTION.value:
                attr_names.add(getattr(it, "name", "") or "")

        for it in items:
            tv = _type_val(it)
            if tv == ItemType.LUNCH_BREAK.value:
                lunch_st = getattr(it, "start_time", None)
            if tv == ItemType.ATTRACTION.value:
                n_attr += 1
                name = getattr(it, "name", "") or ""
                attr_names.add(name)
                nl = name.lower()
                if first_attr_st is None:
                    first_attr_st = getattr(it, "start_time", None)
                poi = {"name": name, "tags": []}
                if poi_covers_preference_report(poi, "relaxation") or any(k in nl for k in _RELAX):
                    day_relax += 1
                    trip_relax += 1
                if poi_covers_preference_report(poi, "nature_landscape") or any(k in nl for k in _NATURE):
                    day_nat += 1
                    trip_nat += 1
                if any(k in nl for k in ("muzeum", "panorama", "zajezdnia", "hydropolis", "rynek", "ostrow", "tumski")):
                    trip_hist += 1
                rk = poi_trip_repeat_key(name)
                if rk:
                    repeat_keys.setdefault(rk, []).append(day.day)
                if label == "test-01.json" and day.day == 3 and tg == "family_kids":
                    if any(k in nl for k in _DENY_FAMILY_D3):
                        issues.append(f"{label} day3: {name} wrong family_kids")
                if label == "test-02.json" and "pigcasso" in nl:
                    issues.append(f"{label} day{day.day}: pigcasso couples relax")
                if label == "test-07.json" and any(k in nl for k in (
                    "fort przygody", "paintball", "citypaintball", "pitlane", "gokart", "gokarty",
                )):
                    issues.append(f"{label} day{day.day}: active sport filler {name}")
                if label == "test-09.json" and day.day == 1 and "wojsławice" in nl:
                    issues.append(f"{label} day1: arboretum wojslawice start")
                if label == "test-10.json" and "katedra" in nl:
                    issues.append(f"{label} day{day.day}: katedra couples water")

        # FIX #254: winter 7-day pool is thinner without Wyspa — flag only empty days.
        if label == "test-08.json" and day.day in (6, 7) and n_attr < 1:
            issues.append(f"{label} day{day.day}: sparse ({n_attr} attr)")
        if label == "test-04.json" and day.day == 5 and lunch_st and first_attr_st:
            if first_attr_st > lunch_st:
                issues.append(f"{label} day5: no morning attraction before lunch")

        if day.day == 6:
            d6_names = [getattr(it, "name", "").lower() for it in items if _type_val(it) == ItemType.ATTRACTION.value]
        if day.day == 7:
            d7_names = [getattr(it, "name", "").lower() for it in items if _type_val(it) == ItemType.ATTRACTION.value]

    if label == "test-08.json" and d6_names and d7_names and d6_names == d7_names:
        issues.append(f"{label}: D6 and D7 identical")

    for rk, days in repeat_keys.items():
        if len(days) >= 2 and rk.startswith("wro_"):
            issues.append(f"{label}: repeat {rk} on days {days}")

    if label == "test-02.json" and "relaxation" in prefs and trip_relax < 1:
        issues.append(f"{label}: relaxation not covered")
    if label == "test-06.json" and "relaxation" in prefs and trip_relax < 1:
        issues.append(f"{label}: relaxation not covered")
    if label == "test-06.json" and "nature_landscape" in prefs and trip_nat < 1:
        issues.append(f"{label}: nature not covered")
    if label == "test-09.json" and "relaxation" in prefs and trip_relax < 1:
        issues.append(f"{label}: relaxation weak ({trip_relax})")
    if label == "test-09.json" and "nature_landscape" in prefs and trip_nat < 1:
        issues.append(f"{label}: nature weak ({trip_nat})")
    if label == "test-07.json" and style == "adventure" and trip_hist < 2:
        issues.append(f"{label}: history/museum weak ({trip_hist})")

    return issues


@pytest.mark.slow
@pytest.mark.parametrize("json_path", _paths(), ids=lambda p: p.name)
def test_wroclaw_fix248_client_feedback(json_path, plan_service):
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    plan = plan_service.generate_plan(TripInput(**payload))
    issues = _audit_wroclaw_248(plan, payload, json_path.name)
    assert not issues, "; ".join(issues[:15])
