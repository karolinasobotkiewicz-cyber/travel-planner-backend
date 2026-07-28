"""FIX #249 — Poznań client feedback round 2 (json 3–9)."""
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

_JSON_ROOT = Path(__file__).resolve().parents[2] / "json_miasta" / "Poznań"

_RELAX = (
    "bulwar", "jezioro malta", "termy malta", "wartostrada", "park sołacki",
    "park solacki", "dolina trzech", "spa", "termy", "maltańskie", "maltanskie",
)
_NATURE = (
    "jezioro", "park ", "dolina", "rezerwat", "lasek", "botaniczny", "cytadela",
    "wartostrada", "fort ",
)
_CENTER = (
    "stary rynek w poznaniu", "zamek królewski", "zamek krolewski",
    "ratusz w poznaniu", "domy kupieckie", "okrąglak", "okraglak",
)
_SIGHTSEE = (
    "stary rynek", "ostrów tumski", "ostrow tumski", "bazylika",
    "plac wolności", "plac wolnosci", "trakt królewsko", "ratusz w poznaniu",
)
_ACTIVE = (
    "flypark", "jump arena", "park linowy", "trampolin", "paintball",
    "escape", "gokart", "wartostrada", "fort va", "fort bonin",
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


def _last_timed_end(items) -> int | None:
    from app.application.services.plan_service import time_to_minutes

    last = None
    for it in items:
        if _type_val(it) in ("day_end",):
            continue
        et = getattr(it, "end_time", None)
        if et:
            last = max(last or 0, time_to_minutes(et))
    return last


def _audit_poznan_249(plan, payload: dict, label: str) -> list[str]:
    issues: list[str] = []
    tg = payload.get("group", {}).get("type", "")
    prefs = set(payload.get("preferences") or [])
    style = payload.get("travel_style", "")
    child_age = payload.get("group", {}).get("children_age")
    num_days = payload.get("trip_length", {}).get("days", 1)
    day_end_str = payload.get("daily_time_window", {}).get("end", "19:00")

    from app.application.services.plan_service import time_to_minutes

    day_end_min = time_to_minutes(day_end_str)
    center_days: list[int] = []
    mick_days: list[int] = []
    trip_active = trip_relax = 0
    trip_sightsee_d2plus = 0

    for day in plan.days:
        items = day.items or []
        day_active = day_relax = day_sightsee = 0
        last_end = _last_timed_end(items)

        for it in items:
            if _type_val(it) != ItemType.ATTRACTION.value:
                continue
            name = getattr(it, "name", "") or ""
            nl = name.lower()
            poi = {"name": name, "tags": []}

            if any(k in nl for k in _CENTER):
                center_days.append(day.day)
            if "park adama mickiewicza" in nl:
                mick_days.append(day.day)

            if any(k in nl for k in _ACTIVE) or poi_covers_preference_report(poi, "active_sport"):
                day_active += 1
                trip_active += 1
            if poi_covers_preference_report(poi, "relaxation") or any(k in nl for k in _RELAX):
                day_relax += 1
                trip_relax += 1
            if any(k in nl for k in _SIGHTSEE):
                day_sightsee += 1
                if day.day >= 2:
                    trip_sightsee_d2plus += 1

            if label == "test-05.json":
                if day.day == 1 and "pixel xl" in nl:
                    issues.append(f"{label} day1: pixel xl for age {child_age}")
                if day.day == 2 and "pomnik ofiar czerwca" in nl:
                    issues.append(f"{label} day2: pomnik ofiar czerwca for kids")
                if "palmiarnia" in nl and not any(
                    k in nl for k in ("zoo", "malta", "termy", "jezioro")
                ):
                    pass  # palmiarnia alone ok as visit, not as relax proof

            if label == "test-07.json" and any(k in nl for k in ("muzeum bambrów", "muzeum bambrow")):
                issues.append(f"{label} day{day.day}: muzeum bambrów off-profile")

        if label == "test-08.json" and day.day == 7 and last_end is not None:
            if last_end < day_end_min - 90:
                issues.append(
                    f"{label} day7: ends too early ({last_end // 60}:{last_end % 60:02d} vs {day_end_str})"
                )

        if label == "test-03.json" and day_active < 1 and day.day == 1:
            issues.append(f"{label} day{day.day}: no active_sport POI")

        if label == "test-03.json":
            if "makieta dawnego poznania" in " ".join(
                getattr(it, "name", "").lower()
                for it in items
                if _type_val(it) == ItemType.ATTRACTION.value
            ):
                issues.append(f"{label}: makieta dawnego poznania present")

    if label == "test-05.json" and "relaxation" in prefs:
        relax_only_palm = True
        for day in plan.days:
            for it in day.items or []:
                if _type_val(it) != ItemType.ATTRACTION.value:
                    continue
                nl = (getattr(it, "name", "") or "").lower()
                if any(k in nl for k in _RELAX) and "palmiarnia" not in nl:
                    relax_only_palm = False
                if any(k in nl for k in ("zoo", "termy malta", "jezioro malta")):
                    relax_only_palm = False
        if relax_only_palm and trip_relax < 1:
            issues.append(f"{label}: relaxation only via palmiarnia")

    if label == "test-08.json" and num_days >= 7:
        if len(set(center_days)) >= 4:
            issues.append(f"{label}: center repeat on days {sorted(set(center_days))}")

    if label == "test-04.json" and len(mick_days) >= 2:
        issues.append(f"{label}: park mickiewicza repeat days {mick_days}")

    for rk, days in _repeat_keys(plan).items():
        if rk.startswith("poz_") and len(days) >= 2:
            issues.append(f"{label}: repeat {rk} on days {days}")

    if label == "test-07.json":
        church_count = sum(
            1
            for day in plan.days
            for it in (day.items or [])
            if _type_val(it) == ItemType.ATTRACTION.value
            and any(k in (getattr(it, "name", "") or "").lower() for k in (
                "bazylika", "kościół", "kosciol", "katedra", "parafia",
            ))
        )
        if church_count >= 3:
            issues.append(f"{label}: too many churches ({church_count})")

    if label == "test-09.json" and trip_sightsee_d2plus >= 5 and trip_relax < 2:
        issues.append(f"{label}: D2-3 too much classic sightseeing")

    if label == "test-03.json" and "active_sport" in prefs and trip_active < 2:
        issues.append(f"{label}: active_sport weak ({trip_active})")

    return issues


def _repeat_keys(plan) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for day in plan.days:
        for it in day.items or []:
            if _type_val(it) != ItemType.ATTRACTION.value:
                continue
            rk = poi_trip_repeat_key(getattr(it, "name", "") or "")
            if rk:
                out.setdefault(rk, []).append(day.day)
    return out


@pytest.mark.slow
@pytest.mark.parametrize("json_path", _paths(), ids=lambda p: p.name)
def test_poznan_fix249_client_feedback(json_path, plan_service):
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    plan = plan_service.generate_plan(TripInput(**payload))
    issues = _audit_poznan_249(plan, payload, json_path.name)
    assert not issues, "; ".join(issues[:15])
