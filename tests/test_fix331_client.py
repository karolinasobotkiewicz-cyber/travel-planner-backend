"""FIX #331 - the day starts with a place, comes home, and eats somewhere.

Client: "21 minut free time od razu po day_start jest troche sztuczne",
"D6 brak powrotu z Olawy do Wroclawia", "D7 lunch jest placeholderem",
"transit from=Katedra ale ostatni postoj to Muzeum Uniwersytetu".
"""
from __future__ import annotations

import os

os.environ.setdefault("ORS_ENABLED", "false")

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    DayEndItem,
    DayStartItem,
    DinnerBreakItem,
    FreeTimeItem,
    ItemType,
    LunchBreakItem,
    RestaurantSuggestion,
    TransitItem,
    TransitMode,
)
from app.domain.validators.client_invariants import audit_day
from app.infrastructure.repositories.poi_repository import POIRepository

WENA = (50.9329, 17.2924)
RYNEK = (51.1100, 17.0313)


def _svc():
    return PlanService(POIRepository("data/zakopane.xlsx"))


def _attr(name, start, end, pt, pid="poi-1"):
    return AttractionItem.model_construct(
        type=ItemType.ATTRACTION,
        poi_id=pid,
        name=name,
        description_short="",
        start_time=start,
        end_time=end,
        duration_min=None,
        lat=pt[0],
        lng=pt[1],
    )


def _hop(frm, to, start, end, km, mode=TransitMode.WALK):
    return TransitItem.model_construct(
        type=ItemType.TRANSIT,
        from_location=frm,
        to_location=to,
        start_time=start,
        end_time=end,
        duration_min=None,
        distance_km=km,
        mode=mode,
        routing_source="estimated_walk",
    )


def _ft(start, end, label="Poranna przerwa"):
    return FreeTimeItem.model_construct(
        type=ItemType.FREE_TIME,
        start_time=start,
        end_time=end,
        duration_min=None,
        label=label,
        suggestions=[],
    )


def _codes(items, **ctx):
    base = {"city": "Wroclaw", "requested_city": "Wroclaw"}
    base.update(ctx)
    return {d.code for d in audit_day(items, day=1, context=base)}


def test_idle_start_is_dropped_and_day_starts_later():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _ft("09:00", "09:26"),
        _hop("Wroclaw", "Hydropolis", "09:26", "09:36", 2.0, TransitMode.CAR),
        _attr("Hydropolis", "09:36", "11:06", (51.1035, 17.0572)),
        DayEndItem(time="11:06"),
    ]
    out = _svc()._drop_idle_morning_padding(items, {"day_start": "09:00"}, day_num=1)
    types = [getattr(x.type, "value", x.type) for x in out]
    assert "free_time" not in types
    start = next(x for x in out if getattr(x.type, "value", x.type) == "day_start")
    assert start.time == "09:26"
    assert "idle_start" not in _codes(out, day_start="09:26")


def test_hop_origin_is_rewritten_to_the_last_stop():
    items = [
        _attr("Hydropolis", "09:00", "10:30", (51.1035, 17.0572)),
        _hop("Dworzec Swiebodzki", "Rynek we Wroclawiu", "10:30", "10:45", 2.0),
        _attr("Rynek we Wroclawiu", "10:45", "11:30", RYNEK, pid="poi-2"),
    ]
    out = _svc()._rewrite_hop_origins(items, day_num=1)
    hop = next(x for x in out if getattr(x.type, "value", x.type) == "transit")
    assert hop.from_location == "Hydropolis"
    assert "from_mismatch" not in _codes(out)


def test_honest_hop_origin_is_left_alone():
    items = [
        _attr("Hydropolis", "09:00", "10:30", (51.1035, 17.0572)),
        _hop("Hydropolis", "Rynek we Wroclawiu", "10:30", "10:45", 2.0),
        _attr("Rynek we Wroclawiu", "10:45", "11:30", RYNEK, pid="poi-2"),
    ]
    hop = next(
        x for x in _svc()._rewrite_hop_origins(items, day_num=1)
        if getattr(x.type, "value", x.type) == "transit"
    )
    assert hop.from_location == "Hydropolis"


def test_tail_free_time_over_100_min_is_dropped():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Muzeum Motoryzacji Wena", "09:40", "13:32", WENA),
        _ft("13:32", "17:13", "Czas dla siebie"),
        DayEndItem(time="17:13"),
    ]
    out = _svc()._trim_tail_long_free_time(items, {}, day_num=6)
    assert not any(
        getattr(x.type, "value", x.type) == "free_time" for x in out
    )
    assert "long_free_time" not in _codes(out)


def test_placeholder_lunch_is_a_defect_until_named():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="12:00",
        end_time="12:45",
        duration_min=45,
        suggestions=[],
        label="Lunch / przerwa regeneracyjna",
        location_context="",
    )
    items = [
        _attr("Rynek w Niemczy", "09:30", "11:50", (50.7230, 16.8340)),
        lunch,
        DayEndItem(time="12:45"),
    ]
    assert "placeholder_meal" in _codes(items)
    named = lunch.model_copy(update={
        "suggestions": [
            RestaurantSuggestion.model_construct(
                id="r-1", name="Przystanek ze smakiem",
                lat=50.723, lng=16.834, city="Olawa", address="",
            ),
        ],
        "label": "Przystanek ze smakiem",
    })
    assert "placeholder_meal" not in _codes([
        items[0], named, items[2],
    ])
