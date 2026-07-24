"""FIX #241 — Kraków client feedback regression (json 1–10)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.application.services.plan_client_audit import audit_day, audit_transit_routing
from app.application.services.plan_service import PlanService
from app.domain.models.plan import ItemType
from app.domain.models.trip_input import TripInput
from app.domain.planner.engine import is_afternoon_only_poi, poi_geo_region_key
from app.domain.planner.time_utils import time_to_minutes
from app.infrastructure.repositories import POIRepository

_JSON_ROOT = Path(__file__).resolve().parents[2] / "json_miasta" / "Kraków"


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


def _audit_krakow(plan, payload: dict, label: str) -> list[str]:
    issues: list[str] = []
    tg = payload.get("group", {}).get("type", "")
    prefs = set(payload.get("preferences") or [])
    style = payload.get("travel_style", "")
    adv = style == "adventure" or "adventure" in prefs
    nat_relax = {"nature_landscape", "relaxation"} <= prefs
    no_history = not ({"history_mystery", "museum_heritage", "underground"} & prefs)
    child_age = payload.get("group", {}).get("children_age")
    trip_old_town = False

    for day in plan.days:
        issues.extend(audit_day(day, day_label=f"{label} "))
        items = day.items or []
        day_has_opn = False
        day_has_city = False
        for it in items:
            if _type_val(it) != ItemType.ATTRACTION.value:
                continue
            name = (getattr(it, "name", "") or "").lower()
            st = getattr(it, "start_time", None)
            if any(k in name for k in ("rynek główny", "rynek glowny", "stare miasto", "sukiennice")):
                if trip_old_town and day.day >= 2:
                    issues.append(f"{label} day{day.day}: repeat old town {name}")
                trip_old_town = True
            if any(k in name for k in ("kładka bernatka", "kladka bernatka", "ojca bernatka")):
                if tg == "family_kids":
                    issues.append(f"{label} day{day.day}: bernatka forbidden family_kids")
                if tg == "friends" and adv:
                    issues.append(f"{label} day{day.day}: bernatka forbidden friends adventure")
            if st and is_afternoon_only_poi({"name": name}) and time_to_minutes(st) < 14 * 60:
                issues.append(f"{label} day{day.day}: afternoon POI {name} at {st}")
            if adv and any(k in name for k in ("kino 7d", "kino 7 d", "& vr")):
                issues.append(f"{label} day{day.day}: kino 7d wrong for adventure")
            if "lustrzany labirynt" in name:
                if style == "cultural" or (tg == "couples" and ("water_attractions" in prefs or "relaxation" in prefs)):
                    issues.append(f"{label} day{day.day}: lustrzany wrong profile")
            if tg == "solo" and nat_relax and no_history:
                if any(k in name for k in ("podziemia rynku", "fabryka schindlera", "wieliczka", "kopalnia soli")):
                    issues.append(f"{label} day{day.day}: history icon without history pref {name}")
            if tg == "couples" and {"water_attractions", "relaxation", "local_food_experience"} <= prefs:
                for bad in (
                    "kościół św. wojciecha", "sw. wojciecha", "nowa huta",
                    "bazylika mariacka", "lustrzany labirynt",
                ):
                    if bad in name:
                        issues.append(f"{label} day{day.day}: couples water/relax forbidden {name}")
                if name.strip() == "zoo" or (name.endswith(" zoo") and "mini" not in name):
                    issues.append(f"{label} day{day.day}: couples water/relax forbidden {name}")
            if tg == "friends" and adv and {"underground", "history_mystery", "museum_heritage"} <= prefs:
                if any(k in name for k in ("park decjusza", "kopiec wandy", "kładka bernatka", "kladka bernatka")):
                    issues.append(f"{label} day{day.day}: weak POI for history friends {name}")
            reg = poi_geo_region_key({"name": name, "city": "Kraków"})
            if reg == "region_ojcow" or any(k in name for k in ("ojców", "ojcow", "maczuga", "pieskowa")):
                day_has_opn = True
            elif not any(k in name for k in ("wieliczka", "kopalnia soli")):
                day_has_city = True
        if day_has_opn and day_has_city:
            issues.append(f"{label} day{day.day}: mixed OPN and Kraków center")
        n_attr = sum(1 for it in items if _type_val(it) == ItemType.ATTRACTION.value)
        num_days = payload.get("trip_length", {}).get("days", 1)
        if num_days >= 5 and n_attr < 2 and day.day < num_days:
            issues.append(f"{label} day{day.day}: sparse day ({n_attr} attractions)")
        if tg == "family_kids" and child_age is not None and int(child_age) <= 5:
            kids_like = sum(
                1 for it in items
                if _type_val(it) == ItemType.ATTRACTION.value
                and any(k in (getattr(it, "name", "") or "").lower() for k in (
                    "papugarnia", "kolejkowo", "pixel", "smoczy", "mini zoo", "fabryka cukier",
                    "park wodny", "iluzj", "motyl", "lego", "zoo",
                ))
            )
            if kids_like == 0 and n_attr >= 2:
                issues.append(f"{label} day{day.day}: no age-5 kids POI")
        issues.extend(audit_transit_routing(items))
    return issues


@pytest.mark.slow
@pytest.mark.parametrize("json_path", _paths(), ids=lambda p: p.name)
def test_krakow_fix241_client_feedback(json_path, plan_service):
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    plan = plan_service.generate_plan(TripInput(**payload))
    issues = _audit_krakow(plan, payload, json_path.name)
    assert not issues, "; ".join(issues[:12])
