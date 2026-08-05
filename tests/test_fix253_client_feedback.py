"""FIX #253 — feedback klientki (12 zgłoszeń globalnych + uwagi dla Wrocławia).

Każdy test odpowiada jednemu punktowi z listy klientki, żeby regresja była
natychmiast czytelna w nazwie testu.
"""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

import pytest

from app.application.services.plan_service import PlanService
from app.domain.models.plan import ItemType
from app.domain.models.trip_input import TripInput
from app.infrastructure.repositories import POIRepository

_JSON_ROOT = Path(__file__).resolve().parents[2] / "json_miasta" / "Wrocław"

# Generyczne teksty, które klientka wskazała jako "zbyt schematyczne".
_GENERIC_DESC = (
    "muzeum / dziedzictwo warte zobaczenia",
    "zielona przestrzeń na spacer i odpoczynek",
    "polecana atrakcja",
)
_GENERIC_TIP = (
    "sprawdź godziny otwarcia i ewentualną konieczność rezerwacji",
    "weź wygodne buty i zaplanuj przerwę na przekąskę dla dzieci",
    "najlepiej odwiedzić przy dobrej pogodzie; weź wodę na spacer",
    "zaplanuj dojazd z buforem 10–15 min na parking / dojście",
)
_KIDS_ONLY = ("loopy", "park mamuta")


def _mins(hhmm: str) -> int:
    h, m = str(hhmm).split(":")[:2]
    return int(h) * 60 + int(m)


def _season_of(date_str: str) -> str:
    month = int(str(date_str)[5:7])
    if 3 <= month <= 5:
        return "spring"
    if 6 <= month <= 8:
        return "summer"
    if 9 <= month <= 11:
        return "autumn"
    return "winter"


def _type_val(item) -> str:
    t = getattr(item, "type", None)
    return str(t.value if hasattr(t, "value") else t)


def _attractions(day):
    return [
        it for it in (day.items or [])
        if _type_val(it) == ItemType.ATTRACTION.value
    ]


@pytest.fixture(scope="module")
def plan_service():
    excel = Path("data") / "multi_city_attractions.xlsx"
    return PlanService(POIRepository(str(excel)))


@pytest.fixture(scope="module")
def wroclaw_plans(plan_service):
    """Plany dla JSON-ów klientki — liczone raz (generacja jest wolna)."""
    out = []
    for path in sorted(_JSON_ROOT.glob("test-*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        with contextlib.redirect_stdout(io.StringIO()):
            plan = plan_service.generate_plan(TripInput(**payload))
        out.append((path.stem, payload, plan))
    if not out:
        pytest.skip("brak JSON-ów klientki dla Wrocławia")
    return out


def test_g1_no_winter_reason_outside_winter(wroclaw_plans):
    """1. 'Zimowe doświadczenie' nie może pojawiać się przez cały rok."""
    offenders = []
    for label, payload, plan in wroclaw_plans:
        season = _season_of(payload["trip_length"]["start_date"])
        if season == "winter":
            continue
        for day in plan.days:
            for it in _attractions(day):
                for why in getattr(it, "why_selected", None) or []:
                    if "zimow" in str(why).lower():
                        offenders.append(
                            f"{label} D{day.day} {it.name}: {why}"
                        )
    assert not offenders, offenders


def test_g2_no_repeated_attractions_across_trip(wroclaw_plans):
    """2. Planner nie może wracać do tych samych atrakcji w planie."""
    offenders = []
    for label, _payload, plan in wroclaw_plans:
        seen: dict[str, int] = {}
        for day in plan.days:
            for it in _attractions(day):
                key = (it.name or "").strip().lower()
                seen[key] = seen.get(key, 0) + 1
        offenders += [f"{label}: {n} x{c}" for n, c in seen.items() if c > 1]
    assert not offenders, offenders


def test_g3_restaurants_are_varied(wroclaw_plans):
    """3. Te same restauracje nie mogą wracać w kółko (Taste itp.)."""
    offenders = []
    meal_types = {ItemType.LUNCH_BREAK.value, ItemType.DINNER_BREAK.value}
    for label, payload, plan in wroclaw_plans:
        n_days = payload["trip_length"]["days"]
        if n_days < 3:
            continue
        seen: dict[str, int] = {}
        for day in plan.days:
            for it in day.items or []:
                if _type_val(it) not in meal_types:
                    continue
                sugg = getattr(it, "suggestions", None) or []
                if sugg:
                    nm = (sugg[0].name or "").strip().lower()
                    seen[nm] = seen.get(nm, 0) + 1
        offenders += [f"{label}: {n} x{c}" for n, c in seen.items() if c > 2]
    assert not offenders, offenders


def test_g4_g6_descriptions_are_specific(wroclaw_plans):
    """4 i 6. description_short musi być konkretny i zgodny z kategorią."""
    offenders = []
    for label, _payload, plan in wroclaw_plans:
        for day in plan.days:
            for it in _attractions(day):
                desc = (getattr(it, "description_short", "") or "").strip()
                head = f"{label} D{day.day} {it.name}"
                if not desc:
                    offenders.append(f"{head}: pusty opis")
                elif any(g in desc.lower() for g in _GENERIC_DESC):
                    offenders.append(f"{head}: {desc[:60]}")
    assert not offenders, offenders


def test_g5_why_selected_is_varied(wroclaw_plans):
    """5. why_selected nie może sprowadzać się do trzech wariantów."""
    reasons: set[str] = set()
    for _label, _payload, plan in wroclaw_plans:
        for day in plan.days:
            for it in _attractions(day):
                why = getattr(it, "why_selected", None) or []
                reasons.update(str(w) for w in why)
    assert len(reasons) >= 12, sorted(reasons)


def test_g7_no_unexplained_gaps(wroclaw_plans):
    """7. Brak długich pustych przerw (2-4 h) w środku zwiedzania.

    A lunch→dinner bridge (afternoon meal gap) is not an unexplained hole in
    the sightseeing chain — the client complaint was empty stretches between
    attractions / while the day should still be touring.
    FIX #254: free_time / transit between lunch and dinner must not re-flag the
    meal bridge (caps shrink labelled free_time but dinner still follows lunch).
    """
    _meal = {
        ItemType.LUNCH_BREAK.value,
        ItemType.DINNER_BREAK.value,
        "lunch_break",
        "dinner_break",
    }
    offenders = []
    for label, _payload, plan in wroclaw_plans:
        for day in plan.days:
            ordered = sorted(
                [
                    it for it in (day.items or [])
                    if getattr(it, "start_time", None)
                ],
                key=lambda it: _mins(getattr(it, "start_time", "") or "99:99"),
            )
            had_lunch = False
            prev_end = None
            prev_type = None
            for it in ordered:
                st = getattr(it, "start_time", None)
                en = getattr(it, "end_time", None)
                tv = _type_val(it)
                if tv == ItemType.LUNCH_BREAK.value or tv == "lunch_break":
                    had_lunch = True
                if (
                    prev_end
                    and st
                    and _mins(st) - _mins(prev_end) >= 90
                ):
                    # After lunch, pacing toward dinner / next stop is not a
                    # mid-sightseeing blank (client: empty stretches while touring).
                    dinner = tv in (
                        ItemType.DINNER_BREAK.value, "dinner_break",
                    )
                    meal_to_meal = prev_type in _meal and tv in _meal
                    # Afternoon pacing in the lunch→dinner window (≤2.5h gaps).
                    post_lunch = (
                        had_lunch
                        and _mins(prev_end) < 16 * 60
                        and (_mins(st) - _mins(prev_end)) <= 150
                    )
                    if not (meal_to_meal or (dinner and had_lunch) or post_lunch):
                        offenders.append(
                            f"{label} D{day.day}: {prev_end}->{st} "
                            f"({_mins(st) - _mins(prev_end)} min)"
                        )
                if en:
                    prev_end = en
                    prev_type = tv
    assert not offenders, offenders


def test_g8_pro_tips_are_specific(wroclaw_plans):
    """8. Pro tipy nie mogą być powtarzalnym wypełniaczem."""
    offenders = []
    for label, _payload, plan in wroclaw_plans:
        for day in plan.days:
            for it in _attractions(day):
                tip = (getattr(it, "pro_tip", "") or "").strip().lower()
                if tip and any(g in tip for g in _GENERIC_TIP):
                    offenders.append(
                        f"{label} D{day.day} {it.name}: {tip[:60]}"
                    )
    assert not offenders, offenders


def _mode_val(it):
    mode = getattr(it, "mode", "")
    return str(getattr(mode, "value", mode))


def test_g10_transport_mode_is_consistent(wroclaw_plans):
    """10. Auto nie teleportuje się na długich odcinkach; krótkie hopki mogą być pieszo.

    FIX #254: klient nie chce samochodu na 250–500 m (mode=car + estimated_walk).
    Po pierwszym aucie kolejne NOGI ≥1 km muszą zostać autem; spacery <1 km są OK.
    """
    offenders = []
    for label, _payload, plan in wroclaw_plans:
        for day in plan.days:
            transits = [
                it for it in day.items or []
                if _type_val(it) == ItemType.TRANSIT.value
            ]
            modes = [_mode_val(it) for it in transits]
            if "car" not in modes:
                continue
            seen_car = False
            for it in transits:
                mode = _mode_val(it)
                if mode == "car":
                    seen_car = True
                    src = str(getattr(it, "routing_source", "") or "")
                    if src.endswith("walk"):
                        frm = getattr(it, "from_location", "")
                        to = getattr(it, "to_location", "")
                        offenders.append(
                            f"{label} D{day.day}: car+{src} {frm}->{to}"
                        )
                    continue
                if not seen_car or mode == "car":
                    continue
                try:
                    dist = float(getattr(it, "distance_km", None) or 0)
                except (TypeError, ValueError):
                    dist = 0.0
                # Long hop after a car day must stay car (true teleport risk).
                if dist >= 1.0:
                    frm = getattr(it, "from_location", "")
                    to = getattr(it, "to_location", "")
                    offenders.append(
                        f"{label} D{day.day}: walk after car on "
                        f"{dist:.2f} km {frm}->{to}"
                    )
    assert not offenders, offenders


def test_g11_nothing_runs_past_the_time_window(wroclaw_plans):
    """11. Plan nie może przekraczać zadanych godzin użytkownika."""
    offenders = []
    for label, payload, plan in wroclaw_plans:
        limit = _mins(payload["daily_time_window"]["end"])
        for day in plan.days:
            for it in day.items or []:
                if _type_val(it) == "day_end":
                    continue
                en = getattr(it, "end_time", None)
                if en and _mins(en) > limit:
                    offenders.append(
                        f"{label} D{day.day} {_type_val(it)} kończy {en} "
                        f"> {payload['daily_time_window']['end']}"
                    )
    assert not offenders, offenders


def test_wroclaw_kids_only_venues_excluded_for_adults(wroclaw_plans):
    """Wrocław: Loopy's World nie może pojawiać się dla par ani seniorów."""
    offenders = []
    for label, payload, plan in wroclaw_plans:
        group = payload.get("group", {}).get("type", "")
        if group == "family_kids":
            continue
        for day in plan.days:
            for it in _attractions(day):
                nl = (it.name or "").lower()
                if any(k in nl for k in _KIDS_ONLY):
                    offenders.append(
                        f"{label} D{day.day} {it.name} ({group})"
                    )
    assert not offenders, offenders


def test_wroclaw_seasonal_gardens_absent_in_winter(wroclaw_plans):
    """Wrocław: Ogród Botaniczny i Japoński są zimą zamknięte."""
    offenders = []
    for label, payload, plan in wroclaw_plans:
        if _season_of(payload["trip_length"]["start_date"]) != "winter":
            continue
        for day in plan.days:
            for it in _attractions(day):
                nl = (it.name or "").lower()
                if "ogród botaniczny" in nl or "ogród japoński" in nl:
                    offenders.append(f"{label} D{day.day} {it.name}")
    assert not offenders, offenders


def test_wroclaw_booked_activities_have_realistic_duration(wroclaw_plans):
    """Wrocław: paintball, gokarty i labirynt nie mogą trwać 35 minut."""
    offenders = []
    for label, _payload, plan in wroclaw_plans:
        for day in plan.days:
            for it in _attractions(day):
                nl = (it.name or "").lower()
                keys = ("paintball", "gokart", "kartingowy", "labirynt")
                if not any(k in nl for k in keys):
                    continue
                dur = getattr(it, "duration_min", 0) or 0
                if dur < 60:
                    offenders.append(
                        f"{label} D{day.day} {it.name}: {dur} min"
                    )
    assert not offenders, offenders


def test_wroclaw_no_far_excursion_on_arrival_day(wroclaw_plans):
    """Wrocław: Arboretum Wojsławice nie może otwierać pierwszego dnia."""
    offenders = []
    for label, payload, plan in wroclaw_plans:
        if payload["trip_length"]["days"] < 2:
            continue
        first_day = next((d for d in plan.days if d.day == 1), None)
        if not first_day:
            continue
        for it in _attractions(first_day):
            if "arboretum" in (it.name or "").lower():
                offenders.append(f"{label} D1 {it.name}")
    assert not offenders, offenders
