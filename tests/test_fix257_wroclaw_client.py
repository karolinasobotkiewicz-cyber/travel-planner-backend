"""FIX #257 — Wrocław client retest: closed POIs, car, gaps, meals, day-trips."""
from __future__ import annotations

from datetime import date

from app.application.services.plan_service import (
    PlanService,
    _filter_meal_suggestions,
    _restaurant_dict_to_suggestion,
)
from app.domain.filters.seasonality import filter_by_season
from app.domain.models.plan import ItemType, RestaurantSuggestion, TransitItem, TransitMode
from app.domain.planner.engine import is_open
from app.domain.planner.time_utils import minutes_to_time
from app.domain.scoring.family_fit import (
    restaurant_hard_denied_for_group,
    restaurant_matches_target_group,
)


def test_fix257_galowice_winter_banned_season_filter():
    poi = {
        "name": "Muzeum Powozów Galowice",
        "season_fit": {"winter": 1, "spring": 1, "summer": 1, "autumn": 1},
    }
    assert filter_by_season([poi], date(2026, 2, 10)) == []


def test_fix257_pontoon_winter_banned_is_open():
    ctx = {"date": "2026-02-10", "year": 2026, "month": 2, "day": 10}
    assert is_open(
        {"name": "Spływy pontonowe Złotniki", "opening_hours": None},
        12 * 60, 60, "winter", ctx,
    ) is False


def test_fix257_monday_museums_closed_without_hours():
    # Monday 2026-02-09
    ctx = {"date": "2026-02-09", "year": 2026, "month": 2, "day": 9}
    for name in (
        "Muzeum Narodowe we Wrocławiu",
        "Muzeum Przyrodnicze",
        "Muzeum Pana Tadeusza",
    ):
        assert is_open(
            {"name": name, "opening_hours": None},
            12 * 60, 60, "winter", ctx,
        ) is False


def test_fix257_tuesday_muzeum_narodowe_allowed_without_hours():
    ctx = {"date": "2026-02-10", "year": 2026, "month": 2, "day": 10}
    assert is_open(
        {"name": "Muzeum Narodowe we Wrocławiu", "opening_hours": None},
        12 * 60, 60, "winter", ctx,
    ) is True


def test_fix257_house_of_spices_denied_family():
    r = {"name": "House of Spices", "target_groups": ["couples", "friends"]}
    assert restaurant_hard_denied_for_group(r, {"target_group": "family_kids"})
    assert not restaurant_matches_target_group(r, {"target_group": "family_kids"})
    assert restaurant_matches_target_group(r, {"target_group": "couples"})


def test_fix257_recommended_for_prefers_family_match():
    family = RestaurantSuggestion(
        id="1", name="Pierogarnia Ze Smakiem", lat=51.1, lng=17.0,
        target_groups=["family_kids", "friends"],
    )
    spices = RestaurantSuggestion(
        id="2", name="House of Spices", lat=51.1, lng=17.0,
        target_groups=["couples", "friends"],
    )
    out = _filter_meal_suggestions(
        [spices, family], target_group="family_kids",
    )
    assert [s.name for s in out] == ["Pierogarnia Ze Smakiem"]


def test_fix257_seniors_fallback_when_no_recommended_for_match():
    spices = RestaurantSuggestion(
        id="2", name="House of Spices", lat=51.1, lng=17.0,
        target_groups=["couples", "friends"],
    )
    out = _filter_meal_suggestions([spices], target_group="seniors")
    # No senior tag in city data → keep pool (not empty meals).
    assert len(out) == 1


def test_fix257_daytrip_keep_galowice_long_transit():
    from types import SimpleNamespace

    svc = PlanService.__new__(PlanService)
    items = [
        TransitItem(
            start_time="10:00",
            end_time="10:50",
            duration_min=50,
            mode=TransitMode.CAR,
            from_location="Wrocław centrum",
            to_location="Muzeum Powozów Galowice",
            distance_km=25.0,
        ),
        SimpleNamespace(
            type=ItemType.ATTRACTION,
            start_time="11:00",
            end_time="12:00",
            duration_min=60,
            name="Muzeum Powozów Galowice",
            poi_id="g1",
        ),
    ]
    out = svc._strip_long_transit_destinations(items, max_min=35, day_num=1)
    names = [
        getattr(it, "name", None) or getattr(it, "to_location", None) for it in out
    ]
    assert any("Galowice" in (n or "") for n in names)


def test_fix257_restaurant_dict_keeps_target_groups():
    sug = _restaurant_dict_to_suggestion(
        {
            "id": "x",
            "name": "House of Spices",
            "lat": 51.1,
            "lng": 17.0,
            "target_groups": ["couples", "friends"],
        },
        "lunch",
    )
    assert sug.target_groups == ["couples", "friends"]
