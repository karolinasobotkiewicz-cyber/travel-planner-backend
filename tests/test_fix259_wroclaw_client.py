"""FIX #259 — Wrocław retest: durations, hours, gaps, meals, daytrip warning."""
from __future__ import annotations

from app.domain.filters.seasonality import filter_by_season
from app.domain.planner.engine import is_open, visit_duration_hard_cap
from app.domain.planner.poi_copy import build_fallback_copy
from app.domain.scoring.profile_poi_rules import (
    poi_trip_repeat_key,
    profile_poi_score_delta,
)
from datetime import date


def test_fix259_panorama_duration_cap_40():
    assert visit_duration_hard_cap(
        {"name": "Panorama Racławicka"}, for_scheduling=True,
    ) == 40


def test_fix259_pitlane_duration_cap_90():
    assert visit_duration_hard_cap(
        {"name": "Pitlane Gokarty - Tor Kartingowy Wroclavia"},
        for_scheduling=True,
    ) == 90


def test_fix259_most_grunwaldzki_cap_25():
    # FIX #261: client — "Most Grunwaldzki 40 min jest za długo" → 25 min look-around.
    assert visit_duration_hard_cap(
        {"name": "Most Grunwaldzki"}, for_scheduling=True,
    ) == 25


def test_fix259_ostrow_cap_90():
    assert visit_duration_hard_cap(
        {"name": "Ostrów Tumski"}, for_scheduling=True,
    ) == 90


def test_fix259_partynice_winter_banned_season_filter():
    poi = {
        "name": "Park Linowy Partynice",
        "season_fit": {"winter": 1, "spring": 1, "summer": 1, "autumn": 1},
    }
    assert filter_by_season([poi], date(2026, 2, 10)) == []


def test_fix259_partynice_winter_banned_is_open():
    ctx = {"date": "2026-02-10", "year": 2026, "month": 2, "day": 10}
    assert is_open(
        {"name": "Park Linowy Partynice", "opening_hours": None},
        12 * 60, 60, "winter", ctx,
    ) is False


def test_fix259_panorama_winter_after_16_closed():
    ctx = {"date": "2026-02-10", "year": 2026, "month": 2, "day": 10}
    assert is_open(
        {"name": "Panorama Racławicka", "opening_hours": None},
        16 * 60, 40, "winter", ctx,
    ) is False


def test_fix259_narodowe_wro_friday_winter_closes_16():
    # Friday 2026-02-20
    ctx = {"date": "2026-02-20", "year": 2026, "month": 2, "day": 20}
    assert is_open(
        {"name": "Muzeum Narodowe we Wrocławiu", "opening_hours": None},
        15 * 60 + 6, 120, "winter", ctx,
    ) is False


def test_fix259_repeat_keys_for_wro_icons():
    assert poi_trip_repeat_key("Muzeum Narodowe we Wrocławiu") == "wro_muzeum_narodowe"
    assert poi_trip_repeat_key("Pergola") == "wro_pergola"
    assert poi_trip_repeat_key("Browar Stu Mostów") == "wro_browar_stu"
    assert poi_trip_repeat_key("Hydropolis") == "wro_hydropolis"


def test_fix259_mamuta_tip_not_ticket():
    desc, tip = build_fallback_copy(
        {
            "name": "Park Mamuta",
            "city": "Wrocław",
            "description_short": "Park z dinozaurami.",
            "pro_tip": "Kup bilet online przed wizytą.",
        }
    )
    assert tip and "darmow" in tip.lower()
    assert "kup bilet" not in tip.lower()


def test_fix259_hala_stulecia_demoted_for_water_food_relax():
    delta = profile_poi_score_delta(
        {"name": "Hala Stulecia"},
        {
            "target_group": "couples",
            "preferences": [
                "water_attractions", "local_food_experience", "relaxation",
            ],
            "travel_style": "relax",
        },
        context={},
    )
    assert delta <= -100


def test_fix259_strip_ghost_origin_not_kept_via_city_substring():
    """Katedra Wrocławska must not be kept just because the name contains Wrocław."""
    from types import SimpleNamespace

    from app.application.services.plan_service import PlanService
    from app.domain.models.plan import ItemType, TransitMode
    from app.infrastructure.repositories import POIRepository
    from pathlib import Path

    svc = PlanService(POIRepository(str(Path("data") / "multi_city_attractions.xlsx")))
    items = [
        SimpleNamespace(
            type=ItemType.TRANSIT,
            start_time="11:50",
            end_time="11:57",
            duration_min=7,
            mode=TransitMode.CAR,
            from_location="Katedra Wrocławska",
            to_location="Hala Targowa",
        ),
        SimpleNamespace(
            type=ItemType.ATTRACTION,
            name="Hala Targowa",
            start_time="11:57",
            end_time="12:51",
            duration_min=54,
        ),
    ]
    out = svc._strip_transits_to_unscheduled_destinations(items, day_num=2)
    assert all(getattr(it, "type", None) != ItemType.TRANSIT for it in out)


def test_fix259_leading_lunch_pulls_morning_attraction():
    from types import SimpleNamespace

    from app.application.services.plan_service import _reorder_leading_lunch
    from app.domain.models.plan import ItemType
    from app.domain.planner.time_utils import time_to_minutes

    class _Item(SimpleNamespace):
        def model_copy(self, update):
            data = dict(self.__dict__)
            data.update(update)
            return _Item(**data)

    items = [
        _Item(type=ItemType.DAY_START, time="09:00"),
        _Item(
            type=ItemType.LUNCH_BREAK,
            start_time="13:05",
            end_time="14:05",
            duration_min=60,
        ),
        _Item(
            type=ItemType.ATTRACTION,
            name="Hala Stulecia",
            start_time="14:44",
            end_time="16:14",
            duration_min=90,
        ),
    ]
    out = _reorder_leading_lunch(items)
    attrs = [it for it in out if getattr(it, "type", None) == ItemType.ATTRACTION]
    lunches = [it for it in out if getattr(it, "type", None) == ItemType.LUNCH_BREAK]
    assert attrs and lunches
    assert time_to_minutes(attrs[0].start_time) < time_to_minutes(lunches[0].start_time)
    assert time_to_minutes(attrs[0].start_time) < 11 * 60
