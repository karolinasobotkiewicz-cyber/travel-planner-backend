"""FIX #327 — auditor learns the second client mail.

Repeats across days, opening hours, 15 min dinners, placeholder meals,
legs that contradict their own coordinates and a 115 min Rynek for a
family with an 8-year-old. No generate_plan here.
"""
from __future__ import annotations

from app.domain.models.plan import (
    AttractionItem,
    DayEndItem,
    DayPlan,
    DayStartItem,
    DinnerBreakItem,
    ItemType,
    LunchBreakItem,
    RestaurantSuggestion,
    TransitItem,
    TransitMode,
)
from app.domain.validators.client_invariants import audit_day, audit_plan


def _attr(name, start, end, dur=60, *, lat=51.11, lng=17.03):
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


def _tr(frm, to, start, end, *, km=1.0, dur=10,
        mode=TransitMode.WALK, src="estimated_walk"):
    return TransitItem.model_construct(
        type=ItemType.TRANSIT,
        from_location=frm,
        to_location=to,
        start_time=start,
        end_time=end,
        duration_min=dur,
        distance_km=km,
        mode=mode,
        routing_source=src,
    )


def _sug(name, *, lat=51.11, lng=17.03):
    return RestaurantSuggestion.model_construct(
        id=f"id-{name}", name=name, lat=lat, lng=lng,
        city="Wrocław", address="",
    )


def _lunch(start, end, dur, sugs=(), label="Lunch / przerwa regeneracyjna"):
    return LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time=start, end_time=end, duration_min=dur,
        suggestions=list(sugs), label=label, location_context="",
    )


def _dinner(start, end, dur, sugs=(), label="Kolacja"):
    return DinnerBreakItem.model_construct(
        type=ItemType.DINNER_BREAK,
        start_time=start, end_time=end, duration_min=dur,
        suggestions=list(sugs), label=label,
    )


def _codes(items, **kwargs):
    return {d.code for d in audit_day(items, **kwargs)}


def _ctx(**extra):
    base = {"day_start": "09:00", "requested_city": "Wrocław", "has_car": True}
    base.update(extra)
    return base


# --- J8: Muzeum Uniwersytetu three days in a row ---

def test_same_attraction_on_three_days_is_a_trip_repeat():
    def _day(n):
        return DayPlan(day=n, title=f"D{n}", items=[
            DayStartItem(type=ItemType.DAY_START, time="09:00"),
            _tr("Wrocław", "Muzeum Uniwersytetu Wrocławskiego",
                "09:00", "09:20", km=2.0, dur=20,
                mode=TransitMode.CAR, src="estimated_road"),
            _attr("Muzeum Uniwersytetu Wrocławskiego", "09:20", "11:00", 100),
            DayEndItem(time="11:00"),
        ])

    defects = [
        d for d in audit_plan([_day(2), _day(3), _day(4)], context=_ctx())
        if d.code == "trip_repeat"
    ]
    assert len(defects) == 2
    assert defects[0].meta["first_day"] == 2


def test_distinct_attractions_are_not_repeats():
    days = [
        DayPlan(day=1, title="D1", items=[
            DayStartItem(type=ItemType.DAY_START, time="09:00"),
            _tr("Wrocław", "Hydropolis", "09:00", "09:20", km=2.4, dur=20,
                mode=TransitMode.CAR, src="estimated_road"),
            _attr("Hydropolis", "09:20", "11:00", 100),
            DayEndItem(time="11:00"),
        ]),
        DayPlan(day=2, title="D2", items=[
            DayStartItem(type=ItemType.DAY_START, time="09:00"),
            _tr("Wrocław", "Most Tumski", "09:00", "09:20", km=2.0, dur=20,
                mode=TransitMode.CAR, src="estimated_road"),
            _attr("Most Tumski", "09:20", "09:50", 30),
            DayEndItem(time="09:50"),
        ]),
    ]
    assert not [d for d in audit_plan(days, context=_ctx()) if d.code == "trip_repeat"]


# --- J1 D1: Kolejkowo at 09:10, opens 10:00 ---

def test_visit_before_opening_is_a_closed_stop():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Kolejkowo Wrocław", "09:00", "09:10", km=1.5, dur=10),
        _attr("Kolejkowo Wrocław", "09:10", "10:40", 90),
        DayEndItem(time="10:40"),
    ]
    ctx = _ctx(
        date="2026-02-20",
        poi_meta={
            "kolejkowo wroclaw": {
                "opening_hours": {
                    "mon": "10:00-18:00", "tue": "10:00-18:00",
                    "wed": "10:00-18:00", "thu": "10:00-18:00",
                    "fri": "10:00-18:00", "sat": "10:00-18:00",
                    "sun": "10:00-18:00",
                },
                "opening_hours_seasonal": None,
            },
        },
    )
    assert "closed_stop" in _codes(items, day=1, context=ctx)


def test_visit_inside_opening_hours_is_clean():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Kolejkowo Wrocław", "09:50", "10:00", km=1.5, dur=10),
        _attr("Kolejkowo Wrocław", "10:00", "11:30", 90),
        DayEndItem(time="11:30"),
    ]
    ctx = _ctx(
        date="2026-02-20",
        poi_meta={
            "kolejkowo wroclaw": {
                "opening_hours": {
                    "mon": "10:00-18:00", "tue": "10:00-18:00",
                    "wed": "10:00-18:00", "thu": "10:00-18:00",
                    "fri": "10:00-18:00", "sat": "10:00-18:00",
                    "sun": "10:00-18:00",
                },
                "opening_hours_seasonal": None,
            },
        },
    )
    assert "closed_stop" not in _codes(items, day=1, context=ctx)


# --- J2 D3 / J7 D2: 15 and 21 minute dinners ---

def test_fifteen_minute_dinner_is_too_short():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Rynek we Wrocławiu", "09:00", "09:20", km=2.0, dur=20,
            mode=TransitMode.CAR, src="estimated_road"),
        _attr("Rynek we Wrocławiu", "09:20", "09:50", 30),
        _tr("Rynek we Wrocławiu", "The Cork", "17:30", "17:45", km=0.5, dur=15),
        _dinner("17:45", "18:00", 15, [_sug("The Cork")], label="The Cork"),
        DayEndItem(time="18:00"),
    ]
    codes = _codes(items, day=3, context=_ctx())
    assert "short_meal" in codes


def test_forty_five_minute_dinner_is_fine():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "The Cork", "17:15", "17:30", km=0.5, dur=15),
        _dinner("17:30", "18:15", 45, [_sug("The Cork")], label="The Cork"),
        DayEndItem(time="18:15"),
    ]
    assert "short_meal" not in _codes(items, day=3, context=_ctx())


# --- J8 D7: lunch is a placeholder, not a place ---

def test_lunch_without_a_restaurant_is_a_placeholder():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _lunch("12:00", "13:00", 60),
        DayEndItem(time="13:00"),
    ]
    codes = _codes(items, day=7, context=_ctx())
    assert "placeholder_meal" in codes
    assert "short_meal" not in codes


def test_named_lunch_is_not_a_placeholder():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _lunch("12:00", "12:45", 45, [_sug("Warzywniak")], label="Warzywniak"),
        DayEndItem(time="12:45"),
    ]
    assert "placeholder_meal" not in _codes(items, day=7, context=_ctx())


# --- J3 D1: 0.084 km between two stops that are kilometres apart ---

def test_leg_that_contradicts_its_own_coordinates():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "CityPaintball", "09:00", "09:25", km=8.0, dur=25,
            mode=TransitMode.CAR, src="estimated_road"),
        _attr("CityPaintball", "09:25", "11:00", 95, lat=51.085, lng=17.010),
        _tr("CityPaintball", "The Cork", "11:00", "11:02", km=0.084, dur=2),
        _dinner("17:30", "18:15", 45, [_sug("The Cork", lat=51.110, lng=17.032)],
                label="The Cork"),
        DayEndItem(time="18:15"),
    ]
    assert "hop_vs_coords" in _codes(items, day=1, context=_ctx())


def test_honest_leg_distance_is_accepted():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "CityPaintball", "09:00", "09:25", km=8.0, dur=25,
            mode=TransitMode.CAR, src="estimated_road"),
        _attr("CityPaintball", "09:25", "11:00", 95, lat=51.085, lng=17.010),
        _tr("CityPaintball", "The Cork", "11:00", "11:20", km=2.9, dur=20,
            mode=TransitMode.CAR, src="estimated_road"),
        _dinner("17:30", "18:15", 45, [_sug("The Cork", lat=51.110, lng=17.032)],
                label="The Cork"),
        DayEndItem(time="18:15"),
    ]
    assert "hop_vs_coords" not in _codes(items, day=1, context=_ctx())


# --- J1 D2: Rynek for 115 min with an 8-year-old ---

def test_rynek_for_115_minutes_with_a_child_is_overlong():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Rynek we Wrocławiu", "09:00", "09:20", km=2.0, dur=20,
            mode=TransitMode.CAR, src="estimated_road"),
        _attr("Rynek we Wrocławiu", "09:20", "11:15", 115),
        DayEndItem(time="11:15"),
    ]
    ctx = _ctx(group_type="family_kids", children_age=8)
    assert "overlong_stop" in _codes(items, day=2, context=ctx)


def test_bridge_for_62_minutes_is_overlong():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Most Grunwaldzki", "09:00", "09:20", km=2.0, dur=20,
            mode=TransitMode.CAR, src="estimated_road"),
        _attr("Most Grunwaldzki", "09:20", "10:22", 62),
        DayEndItem(time="10:22"),
    ]
    assert "overlong_stop" in _codes(items, day=4, context=_ctx(group_type="couples"))


def test_museum_for_two_hours_is_not_a_look_around():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Muzeum Narodowe we Wrocławiu", "09:00", "09:20",
            km=2.0, dur=20, mode=TransitMode.CAR, src="estimated_road"),
        _attr("Muzeum Narodowe we Wrocławiu", "09:20", "11:20", 120),
        DayEndItem(time="11:20"),
    ]
    assert "overlong_stop" not in _codes(items, day=2, context=_ctx())


def test_short_rynek_stroll_is_allowed():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Rynek we Wrocławiu", "09:00", "09:20", km=2.0, dur=20,
            mode=TransitMode.CAR, src="estimated_road"),
        _attr("Rynek we Wrocławiu", "09:20", "10:10", 50),
        DayEndItem(time="10:10"),
    ]
    assert "overlong_stop" not in _codes(items, day=2, context=_ctx(group_type="couples"))

