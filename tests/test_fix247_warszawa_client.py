"""FIX #247 — Warszawa client feedback round 2 (json 1–10)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.application.services.plan_service import PlanService
from app.domain.models.plan import ItemType
from app.domain.models.trip_input import TripInput
from app.domain.scoring.preference_coverage import poi_covers_preference_report
from app.domain.scoring.profile_poi_rules import is_active_city_poi, poi_trip_repeat_key
from app.infrastructure.repositories import POIRepository

_JSON_ROOT = Path(__file__).resolve().parents[2] / "json_miasta" / "Warszawa"

_WAW_FILLER = (
    "most świętokrzyski", "most swietokrzyski", "pałac prezydencki", "palac prezydencki",
    "plac europejski", "centrum pieniądza", "centrum pieniadza", "ogrody zamku", "ogrod zamku",
)

_ADV_MARKERS = (
    "podziemia", "schron", "krypta", "bunkier", "fort ", "kopalnia", "escape",
    "paintball", "park linowy", "tepfactor", "kajak", "muzeum powstania",
    "kopiec powstania", "gazowni", "grawitacja", "norblin",
)

_WATER_MARKERS = (
    "park wodny", "warszawianka", "bulwary wiślane", "bulwary wislane", "kajak",
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


def _is_filler(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in _WAW_FILLER)


def _poi_dict(name: str) -> dict:
    return {"name": name, "tags": []}


def _audit_warszawa_247(plan, payload: dict, label: str) -> list[str]:
    issues: list[str] = []
    tg = payload.get("group", {}).get("type", "")
    prefs = set(payload.get("preferences") or [])
    style = payload.get("travel_style", "")
    num_days = payload.get("trip_length", {}).get("days", 1)

    trip_active = trip_water = trip_adv = 0
    repeat_keys: dict[str, list[int]] = {}

    for day in plan.days:
        items = day.items or []
        day_active = day_water = day_adv = 0
        ft_total = 0
        n_attr = 0

        for it in items:
            tv = _type_val(it)
            if tv == ItemType.FREE_TIME.value:
                ft_total += int(getattr(it, "duration_min", 0) or 0)
            if tv != ItemType.ATTRACTION.value:
                continue
            n_attr += 1
            name = getattr(it, "name", "") or ""
            nl = name.lower()
            poi = _poi_dict(name)

            if poi_covers_preference_report(poi, "active_sport") or is_active_city_poi(poi):
                day_active += 1
                trip_active += 1
            if poi_covers_preference_report(poi, "water_attractions") or any(
                k in nl for k in _WATER_MARKERS
            ):
                day_water += 1
                trip_water += 1
            if any(m in nl for m in _ADV_MARKERS):
                day_adv += 1
                trip_adv += 1

            rk = poi_trip_repeat_key(name)
            if rk:
                repeat_keys.setdefault(rk, []).append(day.day)

            if _is_filler(nl):
                if label == "test-02.json" and "most świętokrz" in nl and day.day == 3:
                    issues.append(f"{label} day{day.day}: most swietokrzyski couples D3")
                if label == "test-04.json" and "prezyden" in nl and day.day == 1:
                    issues.append(f"{label} day{day.day}: palac prezydencki solo D1")
                if label == "test-04.json" and "most świętokrz" in nl and day.day == 4:
                    issues.append(f"{label} day{day.day}: most swietokrzyski solo D4")
                if label == "test-09.json" and "centrum pieni" in nl:
                    issues.append(f"{label} day{day.day}: centrum pieniadza solo relax")
                if label == "test-10.json" and tg == "couples" and "water" in prefs:
                    if "prezyden" in nl or "grób" in nl or "grob" in nl:
                        issues.append(f"{label} day{day.day}: heritage filler couples water")

        if label == "test-08.json" and day.day in (6, 7):
            if ft_total >= 45:
                issues.append(f"{label} day{day.day}: long free_time {ft_total}m")
            if n_attr < 3:
                issues.append(f"{label} day{day.day}: sparse day ({n_attr} attr)")

        if label == "test-10.json" and "water_attractions" in prefs and day_water == 0:
            if n_attr >= 2:
                issues.append(f"{label} day{day.day}: no water POI")

    for rk, days in repeat_keys.items():
        if len(days) >= 2 and rk in (
            "waw_ogrody_zamku", "waw_plac_europejski", "waw_most_swietokrzyski",
            "waw_palac_prezydencki", "waw_centrum_pieniadza",
        ):
            issues.append(f"{label}: repeat {rk} days {days}")

    if label == "test-03.json" and "active_sport" in prefs and trip_active < 1:
        issues.append(f"{label}: active_sport not covered")

    if label == "test-07.json" and style == "adventure" and tg == "friends":
        if trip_adv < 2 and "underground" in prefs:
            issues.append(f"{label}: adventure profile weak ({trip_adv} adv POI)")

    if label == "test-10.json" and "water_attractions" in prefs and trip_water < 1:
        issues.append(f"{label}: water_attractions not covered")

    return issues


@pytest.mark.slow
@pytest.mark.parametrize("json_path", _paths(), ids=lambda p: p.name)
def test_warszawa_fix247_client_feedback(json_path, plan_service):
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    plan = plan_service.generate_plan(TripInput(**payload))
    issues = _audit_warszawa_247(plan, payload, json_path.name)
    assert not issues, "; ".join(issues[:15])
