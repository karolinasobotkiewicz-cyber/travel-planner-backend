"""FIX #315 — first hop, trip-unique Pergola, idle before dinner.

Client Wrocław follow-up: D3/D5/D6 start the first attraction at day_start
with no city hop; Pergola repeats on D1/D3/D5/D6; 88 min named free_time
before dinner because 90 was the inject/eat floor.
"""
from __future__ import annotations

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    DayEndItem,
    DayPlan,
    DayStartItem,
    DinnerBreakItem,
    FreeTimeItem,
    ItemType,
)


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur=60, *, lat=51.1068, lng=17.0773):
    return AttractionItem.model_construct(
        type=ItemType.ATTRACTION,
        poi_id=f"id-{name}",
        name=name,
        description_short="",
        start_time=start,
        end_time=end,
        duration_min=dur,
        lat=lat,
        lng=lng,
        address="Wrocław",
        city="Wrocław",
        cost_estimate=0,
    )


def _ft(start, end, dur, label="Czas dla siebie"):
    return FreeTimeItem.model_construct(
        type=ItemType.FREE_TIME,
        start_time=start,
        end_time=end,
        duration_min=dur,
        label=label,
        suggestions=[],
    )


def _dinner(start, end, dur=45):
    return DinnerBreakItem.model_construct(
        type=ItemType.DINNER_BREAK,
        start_time=start,
        end_time=end,
        duration_min=dur,
        label="Kolacja",
        suggestions=[],
    )


def _ctx(**extra):
    base = {
        "requested_city": "Wrocław",
        "has_car": True,
        "day_start": "09:00",
        "day_end": "19:00",
        "start_date": "2026-02-20",
        "date": "2026-02-20",
    }
    base.update(extra)
    return base


def test_first_attraction_at_day_start_gets_city_hop():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Pergola", "09:00", "10:00", 60),
        DayEndItem(time="16:00"),
    ]
    out = _svc()._ensure_leading_transit(items, {}, _ctx(), day_num=3)
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert hops, "D3-style 09:00 Pergola must get Wrocław → Pergola"
    assert "wrocław" in (hops[0].from_location or "").lower()
    assert "pergola" in (hops[0].to_location or "").lower()
    attrs = [it for it in out if getattr(it, "type", None) == ItemType.ATTRACTION]
    assert attrs
    assert attrs[0].start_time > "09:00"


def test_same_courtyard_does_not_invent_a_hop():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Rynek we Wrocławiu", "09:00", "10:00", 60, lat=51.1079, lng=17.0385),
        DayEndItem(time="16:00"),
    ]
    out = _svc()._ensure_leading_transit(items, {}, _ctx(), day_num=1)
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert not hops


def test_pergola_stripped_on_later_days():
    days = [
        DayPlan(day=1, title="D1", items=[_attr("Pergola", "10:00", "11:00")]),
        DayPlan(day=3, title="D3", items=[
            _attr("Pergola", "09:00", "10:00"),
            _attr("Hydropolis", "11:00", "12:00", 60, lat=51.104, lng=17.056),
        ]),
        DayPlan(day=5, title="D5", items=[_attr("Pergola i Hala", "09:00", "10:00")]),
    ]
    out = _svc()._strip_cross_day_trip_repeats(days)
    later = []
    for day in out:
        if int(day.day) == 1:
            continue
        later.extend(
            (getattr(it, "name", "") or "").lower()
            for it in (day.items or [])
            if getattr(it, "type", None) == ItemType.ATTRACTION
        )
    assert not any("pergola" in n for n in later)


def test_inject_will_not_replant_pergola():
    items = [
        _attr("Hydropolis", "14:30", "16:02", 92, lat=51.104, lng=17.056),
        _ft("16:02", "17:30", 88),
        _dinner("17:30", "18:15"),
    ]
    pool = [{
        "id": "p1",
        "name": "Pergola",
        "lat": 51.1068,
        "lng": 17.0773,
        "city": "Wrocław",
        "tags": ["attraction"],
        "duration_min": 45,
    }]
    ctx = _ctx(
        trip_repeat_keys={"wro_pergola"},
        allow_pre_meal_inject=True,
        requested_city="Wrocław",
    )
    out = _svc()._inject_attraction_into_free_time(
        items, pool, ctx, {"preferences": []}, day_num=5,
    )
    names = [
        (getattr(it, "name", "") or "").lower()
        for it in out if getattr(it, "type", None) == ItemType.ATTRACTION
    ]
    assert not any("pergola" in n for n in names)


def test_88min_before_dinner_is_eaten():
    items = [
        _attr("Hydropolis", "14:30", "16:02", 92, lat=51.104, lng=17.056),
        _ft("16:02", "17:30", 88),
        _dinner("17:30", "18:15"),
    ]
    out = _svc()._eat_long_free_time_before_attraction(
        items, day_num=2, min_ft=45, keep=20,
    )
    dinners = [it for it in out if getattr(it, "type", None) == ItemType.DINNER_BREAK]
    assert dinners
    # FIX #322: 17:30 is the dinner floor — do not pull kolacja earlier.
    # The 88 min hole stays for inject / evening close, not a 16:xx dinner.
    assert dinners[0].start_time >= "17:30"


def test_guard_restores_leading_hop_and_strips_repeat_pergola():
    days = [
        DayPlan(
            day=1, title="D1",
            items=[
                DayStartItem(type=ItemType.DAY_START, time="09:00"),
                _attr("Pergola", "10:00", "11:00"),
                DayEndItem(time="16:00"),
            ],
        ),
        DayPlan(
            day=3, title="D3",
            items=[
                DayStartItem(type=ItemType.DAY_START, time="09:00"),
                _attr("Pergola", "09:00", "10:00"),
                _attr("Hydropolis", "11:00", "12:00", 60, lat=51.104, lng=17.056),
                DayEndItem(time="16:00"),
            ],
        ),
    ]
    out = _svc()._guard_trip_invariants(days, _ctx(), coord_map={}, user={})
    d3 = next(d for d in out if int(d.day) == 3)
    names = [
        (getattr(it, "name", "") or "").lower()
        for it in (d3.items or [])
        if getattr(it, "type", None) == ItemType.ATTRACTION
    ]
    assert not any("pergola" in n for n in names)
    hops = [
        it for it in (d3.items or [])
        if getattr(it, "type", None) == ItemType.TRANSIT
    ]
    assert hops, "after the Pergola strip, Hydropolis still needs a city hop"
    assert "hydropolis" in (hops[0].to_location or "").lower()
