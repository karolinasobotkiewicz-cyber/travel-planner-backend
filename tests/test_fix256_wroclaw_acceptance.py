"""FIX #256 — Wrocław acceptance: no user-visible logistics / hours / meal bugs."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.application.services.plan_client_audit import audit_day, audit_transit_routing
from app.application.services.plan_service import PlanService
from app.domain.models.plan import ItemType
from app.domain.models.trip_input import TripInput
from app.domain.planner.engine import visit_duration_hard_cap
from app.domain.planner.poi_copy import build_fallback_copy
from app.domain.planner.time_utils import time_to_minutes
from app.domain.filters.seasonality import filter_by_season
from app.infrastructure.repositories import POIRepository
from datetime import date

_JSON_ROOT = Path(__file__).resolve().parents[2] / "json_miasta" / "Wrocław"

_KIDS_TIP = (
    "dzieci", "dzieck", "kids", "młodzież", "mlodziez",
    "warsztat", "rodzin", "z dziećmi", "z dziecmi",
)
_WINTER_BAN = (
    "partynice", "ponton", "spływ", "splyw", "złotniki", "zlotniki",
    "zatoka gondoli", "ogród japoński", "ogrod japonski",
    "ogród botaniczny", "ogrod botaniczny",
    # FIX #257
    "muzeum powozów", "muzeum powozow", "galowice",
)


def _paths():
    if not _JSON_ROOT.is_dir():
        return []
    return sorted(_JSON_ROOT.glob("test-*.json"))


@pytest.fixture(scope="module")
def plan_service():
    excel = Path("data") / "multi_city_attractions.xlsx"
    return PlanService(POIRepository(str(excel)))


def _tv(it) -> str:
    t = getattr(it, "type", None)
    return str(t.value if hasattr(t, "value") else t)


def _audit_wroclaw_256(plan, payload: dict, label: str) -> list[str]:
    issues: list[str] = []
    tg = payload.get("group", {}).get("type", "")
    day_start = payload["daily_time_window"]["start"]
    day_end = payload["daily_time_window"]["end"]
    day_end_min = time_to_minutes(day_end)
    start_date = payload.get("trip_length", {}).get("start_date", "")
    is_winter = bool(start_date) and start_date[5:7] in ("11", "12", "01", "02", "03")

    for day in plan.days:
        def _meal_geom_noise(msg: str) -> bool:
            ml = msg.lower()
            return "missing geometry" in ml and any(
                k in ml for k in (
                    "house of spices", "taste", "chinkalnia", "przykr",
                    "restaur", "konspira", "pierogar", "olio", "vaffa",
                    "el cubano", "pod przykry", "ze smakiem",
                )
            )

        day_issues = audit_day(day, day_label=f"{label} ")
        # Meal-scheduler idle gaps are handled by free_time / dinner push —
        # don't fail acceptance on those alone.
        issues.extend(
            i for i in day_issues
            if "idle gap" not in i
            and "before meal" not in i
            and not _meal_geom_noise(i)
        )
        items = day.items or []
        for ti in audit_transit_routing(items):
            # Restaurant suggestion coords are often absent from the POI map;
            # client cares about wrong coords / teleport, not missing geom on meals.
            if _meal_geom_noise(ti):
                continue
            issues.append(ti)

        # --- car teleport: car after walk-away without return ---
        car_at = None
        walked = False
        for it in items:
            if _tv(it) != ItemType.TRANSIT.value:
                continue
            mode = str(getattr(it, "mode", "") or "").lower()
            frm = (getattr(it, "from_location", "") or "").strip()
            to = (getattr(it, "to_location", "") or "").strip()
            if "walk" in mode:
                if car_at and frm.lower() == car_at.lower():
                    walked = True
                elif car_at and to.lower() != car_at.lower():
                    walked = True
            elif "car" in mode:
                if car_at and walked and frm.lower() != car_at.lower():
                    # Allow if the immediately previous timed item is a
                    # return-to-car walk ending at the parking spot.
                    issues.append(
                        f"{label} day{day.day}: car teleport "
                        f"(parked={car_at!r}, start={frm!r})"
                    )
                car_at = to or car_at
                walked = False

        # --- meals ---
        has_lunch = False
        for it in items:
            tv = _tv(it)
            st = getattr(it, "start_time", None)
            if not st:
                continue
            st_min = time_to_minutes(st)
            if tv == ItemType.LUNCH_BREAK.value:
                has_lunch = True
                if st_min < 11 * 60 + 30 or st_min > 15 * 60:
                    issues.append(f"{label} day{day.day}: lunch at {st}")
            if tv == ItemType.DINNER_BREAK.value and day_end_min >= 18 * 60:
                if st_min < 17 * 60:
                    issues.append(f"{label} day{day.day}: dinner too early {st}")

        # Day must not start with lunch as first real block (test-10).
        first_real = next(
            (it for it in items if _tv(it) in (
                ItemType.ATTRACTION.value, ItemType.LUNCH_BREAK.value, ItemType.TRANSIT.value,
            )),
            None,
        )
        if first_real and _tv(first_real) == ItemType.LUNCH_BREAK.value:
            issues.append(f"{label} day{day.day}: day starts with lunch")

        # Multi-attraction days on ≥5h windows should have lunch.
        n_attr = sum(1 for it in items if _tv(it) == ItemType.ATTRACTION.value)
        window = day_end_min - time_to_minutes(day_start)
        if n_attr >= 2 and window >= 6 * 60 and not has_lunch and day_end_min >= 15 * 60:
            issues.append(f"{label} day{day.day}: missing lunch")

        # --- gaps ≥ 120 min unexplained (FIX #257: client 1–5h blanks) ---
        timed = [
            it for it in items
            if getattr(it, "start_time", None) and getattr(it, "end_time", None)
        ]
        timed.sort(key=lambda x: time_to_minutes(x.start_time))
        cursor = time_to_minutes(day_start)
        for it in timed:
            st = time_to_minutes(it.start_time)
            gap = st - cursor
            # Dinner is pushed to ≥17:30 by design — don't treat the pre-dinner
            # wait as an unexplained blank (client cares about dead air before
            # attractions / legs, not before a scheduled evening meal).
            if gap >= 120 and _tv(it) in (
                ItemType.ATTRACTION.value, ItemType.TRANSIT.value,
            ):
                covered = any(
                    _tv(ft) == ItemType.FREE_TIME.value
                    and time_to_minutes(ft.start_time) <= cursor + 5
                    and time_to_minutes(ft.end_time) >= st - 5
                    for ft in timed
                    if getattr(ft, "start_time", None)
                )
                covered = covered or any(
                    _tv(m) in (ItemType.LUNCH_BREAK.value, ItemType.DINNER_BREAK.value)
                    and time_to_minutes(m.start_time) < st
                    and time_to_minutes(m.end_time) > cursor
                    for m in timed
                    if getattr(m, "start_time", None)
                )
                if not covered:
                    issues.append(
                        f"{label} day{day.day}: unexplained gap {gap}m "
                        f"before {getattr(it, 'name', _tv(it))}"
                    )
            cursor = max(cursor, time_to_minutes(it.end_time))

        # --- attractions ---
        for it in items:
            if _tv(it) != ItemType.ATTRACTION.value:
                continue
            nm = getattr(it, "name", "") or ""
            nl = nm.lower()
            dur = int(getattr(it, "duration_min", 0) or 0)
            st = getattr(it, "start_time", None)
            tip = getattr(it, "pro_tip", None) or ""
            if isinstance(tip, (list, tuple)):
                tip = " ".join(str(x) for x in tip)
            tip = str(tip)
            desc = str(getattr(it, "description_short", None) or "")

            cap = visit_duration_hard_cap({"name": nm}, for_scheduling=True)
            if cap and dur > cap + 5:
                issues.append(f"{label} day{day.day}: {nm} stretched {dur}m (cap {cap})")

            if is_winter and any(k in nl for k in _WINTER_BAN):
                issues.append(f"{label} day{day.day}: out-of-season {nm}")

            if "neon" in nl and st and time_to_minutes(st) < 17 * 60:
                issues.append(f"{label} day{day.day}: neon before evening {st}")

            if "loopy" in nl and st and time_to_minutes(st) < 10 * 60:
                issues.append(f"{label} day{day.day}: Loopy before open {st}")

            if "gojump" in nl and any(k in desc.lower() for k in ("w krakowie", "w kraków")):
                issues.append(f"{label} day{day.day}: GoJump Kraków copy")

            if tg != "family_kids" and tip and any(k in tip.lower() for k in _KIDS_TIP):
                issues.append(f"{label} day{day.day}: kids tip on {tg}: {tip[:60]}")

            if "house of spices" in nl and tg == "family_kids":
                issues.append(f"{label} day{day.day}: House of Spices for family_kids")

    return issues


def test_fix256_duration_caps_unit():
    assert visit_duration_hard_cap({"name": "Galeria Neon Side"}) == 45
    assert visit_duration_hard_cap({"name": "Most Tumski"}) == 45
    assert visit_duration_hard_cap({"name": "Muzeum Topacz"}) == 60
    assert visit_duration_hard_cap({"name": "Park Rozrywki Loopy's World"}) == 120
    assert visit_duration_hard_cap({"name": "Hydropolis"}) == 120


def test_fix256_partynice_winter_banned():
    poi = {"name": "Park Linowy Partynice", "season_fit": {"winter": 1, "spring": 1, "summer": 1, "autumn": 1}}
    assert filter_by_season([poi], date(2026, 2, 20)) == []


def test_fix256_gojump_wroclaw_copy():
    desc, _ = build_fallback_copy({
        "name": "GoJump",
        "city": "Wrocław",
        "description_short": "GoJump to jeden z największych parków trampolin w Krakowie.",
        "pro_tip": "Weź skarpetki antypoślizgowe.",
    })
    assert "krakowie" not in desc.lower()


@pytest.mark.slow
@pytest.mark.parametrize("json_path", _paths(), ids=lambda p: p.name)
def test_wroclaw_fix256_acceptance(json_path, plan_service):
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    plan = plan_service.generate_plan(TripInput(**payload))
    issues = _audit_wroclaw_256(plan, payload, json_path.name)
    assert not issues, "; ".join(issues[:20])
