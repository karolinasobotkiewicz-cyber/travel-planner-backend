"""FIX #328 — one place, one day.

Client J8: "Muzeum Uniwersytetu Wrocławskiego pojawia się aż 3 razy, dzień
po dniu." The trip-level set of used names is diacritic-folded, the POI name
is not, so every Polish name slipped past the uniqueness check.
"""
from __future__ import annotations

import os

os.environ.setdefault("ORS_ENABLED", "false")

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    DayEndItem,
    DayStartItem,
    FreeTimeItem,
    ItemType,
)
from app.infrastructure.repositories.poi_repository import POIRepository

_NAME = "Muzeum Uniwesytetu Wrocławskiego"
_FOLDED = "muzeum uniwesytetu wroclawskiego"


def _svc():
    return PlanService(POIRepository("data/zakopane.xlsx"))


def _poi(name):
    return {
        "id": "poi-uni",
        "type": "poi",
        "name": name,
        "Name": name,
        "city": "Wrocław",
        "lat": 51.1140,
        "lng": 17.0330,
        "Lat": 51.1140,
        "Lng": 17.0330,
        "Address": "pl. Uniwersytecki 1",
        "Description_short": "Zabytkowe wnętrza uniwersytetu.",
        "time_min": 45,
        "time_max": 90,
        "opening_hours": None,
        "opening_hours_seasonal": [{
            "date_from": "01-01", "date_to": "12-31",
            "mon": "09:00-18:00", "tue": "09:00-18:00", "wed": "09:00-18:00",
            "thu": "09:00-18:00", "fri": "09:00-18:00", "sat": "09:00-18:00",
            "sun": "09:00-18:00",
        }],
        "tags": ["culture", "history"],
        "space": "indoor",
        "intensity": "low",
        "popularity_score": 70,
        "ticket_normal": 20,
    }


def _items():
    return [
        DayStartItem(type=ItemType.DAY_START, time="10:00"),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME,
            start_time="10:00",
            end_time="13:00",
            duration_min=180,
            label="Czas wolny w centrum",
        ),
        DayEndItem(time="13:00"),
    ]


def _ctx(prior_names):
    return {
        "requested_city": "Wrocław",
        "date": "2026-06-12",
        "trip_date": "2026-06-12",
        "day_start": "10:00",
        "day_end": "18:00",
        "season": "summer",
        "allow_soft_profile": True,
        "allow_pre_meal_inject": True,
        "city_holes_only": True,
        "trip_repeat_keys": set(),
        "trip_attraction_names": set(prior_names),
    }


_USER = {
    "group_type": "couples",
    "travel_style": "cultural",
    "interests": ["culture", "history"],
    "budget": "medium",
    "has_car": True,
}


def _injected_names(items):
    return [
        (getattr(it, "name", "") or "")
        for it in items
        if getattr(getattr(it, "type", None), "value", None) == "attraction"
    ]


def test_poi_is_injected_when_the_trip_has_not_used_it():
    svc = _svc()
    out = svc._inject_attraction_into_free_time(
        _items(), [_poi(_NAME)], _ctx(set()), _USER, day_num=3,
    )
    assert _NAME in _injected_names(out), (
        "control case: an unused POI must be plantable, otherwise the "
        "uniqueness assertion below proves nothing"
    )


def test_folded_prior_name_blocks_the_same_poi_on_another_day():
    svc = _svc()
    out = svc._inject_attraction_into_free_time(
        _items(), [_poi(_NAME)], _ctx({_FOLDED}), _USER, day_num=3,
    )
    assert _NAME not in _injected_names(out)


def test_raw_prior_name_still_blocks_the_same_poi():
    svc = _svc()
    out = svc._inject_attraction_into_free_time(
        _items(), [_poi(_NAME)], _ctx({_NAME.lower()}), _USER, day_num=3,
    )
    assert _NAME not in _injected_names(out)
