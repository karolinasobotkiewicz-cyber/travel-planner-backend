"""FIX #317 — auditor: the six defect classes from the Wrocław JSON reports.

These tests prove the auditor sees the client's defects. They do not call
generate_plan. JSON 1–10 live plans live in test_fix317_wroclaw_json.py.
"""
from __future__ import annotations

from app.domain.models.plan import (
    AttractionItem,
    DayEndItem,
    DayPlan,
    DayStartItem,
    FreeTimeItem,
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


def _ft(start, end, dur, label="Czas dla siebie"):
    return FreeTimeItem.model_construct(
        type=ItemType.FREE_TIME,
        start_time=start,
        end_time=end,
        duration_min=dur,
        label=label,
        suggestions=[],
    )


def _sug(name, *, lat=51.11, lng=17.03):
    return RestaurantSuggestion.model_construct(
        id=f"id-{name}", name=name, lat=lat, lng=lng,
        city="Wrocław", address="",
    )


def _lunch(start, end, dur, sugs, label="Lunch / przerwa regeneracyjna", loc=""):
    return LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time=start, end_time=end, duration_min=dur,
        suggestions=sugs, label=label, location_context=loc,
    )


def _codes(items, **kwargs):
    return {d.code for d in audit_day(items, **kwargs)}


def test_auditor_accepts_a_coherent_city_day():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Hydropolis", "09:00", "09:15", km=2.4, dur=15,
            mode=TransitMode.CAR, src="estimated_road"),
        _attr("Hydropolis", "09:15", "10:45", 90, lat=51.104, lng=17.056),
        _tr("Hydropolis", "Most Tumski", "10:45", "11:00", km=1.8, dur=15),
        _attr("Most Tumski", "11:00", "12:00", 60, lat=51.114, lng=17.047),
        _tr("Most Tumski", "Bernard", "12:00", "12:10", km=0.6, dur=10),
        _lunch("12:10", "12:55", 45, [_sug("Bernard")], label="Bernard"),
        DayEndItem(time="12:55"),
    ]
    assert audit_day(items, day=1) == []


def test_anonymous_gap_134min_after_restaurant():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Pixel XL", "13:00", "14:30", 90, lat=51.09, lng=17.02),
        _tr("Pixel XL", "Restauracja Česká", "14:30", "14:59", km=2.0, dur=29),
        _lunch("14:59", "14:59", 0, [_sug("Restauracja Česká")], label="Česká"),
        _attr("Aquapark Wrocław", "17:13", "18:30", 77, lat=51.09, lng=17.01),
        DayEndItem(time="19:00"),
    ]
    assert "anonymous_gap" in _codes(items, day=3)


def test_morning_free_time_is_not_an_anonymous_gap():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _ft("09:00", "09:47", 47, label="Spokojny poranek"),
        _tr("Wrocław", "Hydropolis", "09:47", "10:00", km=2.0, dur=13,
            mode=TransitMode.CAR, src="estimated_road"),
        _attr("Hydropolis", "10:00", "11:00", 60, lat=51.104, lng=17.056),
        DayEndItem(time="11:00"),
    ]
    assert "anonymous_gap" not in _codes(items, day=2)


def test_teleport_same_minute_without_hop():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Muzeum Przyrodnicze", "09:00", "09:20", km=1.5, dur=20),
        _attr("Muzeum Przyrodnicze we Wrocławiu", "09:20", "10:40", 80,
              lat=51.111, lng=17.047),
        _attr("GoJump", "10:40", "12:00", 80, lat=51.10, lng=17.08),
        DayEndItem(time="12:00"),
    ]
    assert "missing_hop" in _codes(items, day=1)


def test_one_minute_walk_of_two_km_is_dishonest():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Panorama Racławicka", "11:00", "12:00", 60, lat=51.110, lng=17.044),
        _tr("Panorama Racławicka", "Warzywniak", "11:59", "12:00",
            km=2.127, dur=1),
        _lunch("12:00", "12:45", 45, [_sug("Warzywniak")], label="Warzywniak"),
        DayEndItem(time="12:45"),
    ]
    codes = _codes(items, day=1)
    assert "dishonest_leg" in codes
    assert "overlap" in codes


def test_car_on_150m_is_urban_car():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Muzeum Pana Tadeusza", "10:00", "11:00", 60, lat=51.110, lng=17.032),
        _tr("Muzeum Pana Tadeusza", "Rynek we Wrocławiu", "11:00", "11:16",
            km=0.15, dur=16, mode=TransitMode.CAR, src="estimated_road"),
        _attr("Rynek we Wrocławiu", "11:16", "12:00", 44, lat=51.110, lng=17.031),
        DayEndItem(time="12:00"),
    ]
    assert "urban_car" in _codes(items, day=2)


def test_citypaintball_at_day_start_needs_leading_hop():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("CityPaintball", "09:00", "10:30", 90, lat=51.085, lng=17.010),
        DayEndItem(time="10:30"),
    ]
    assert "missing_hop" in _codes(items, day=1)


def test_50min_unnamed_morning_is_anonymous_gap():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Hydropolis", "09:50", "10:05", km=2.0, dur=15,
            mode=TransitMode.CAR, src="estimated_road"),
        _attr("Hydropolis", "10:05", "11:00", 55, lat=51.104, lng=17.056),
        DayEndItem(time="11:00"),
    ]
    assert "anonymous_gap" in _codes(items, day=2)


def test_free_time_after_day_end_is_flagged():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Hydropolis", "10:00", "14:30", 270, lat=51.104, lng=17.056),
        DayEndItem(time="14:43"),
        _ft("14:55", "15:14", 19),
    ]
    assert "after_day_end" in _codes(items, day=7)


def test_meal_label_and_generic_from_mismatch():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Loopy's World", "10:00", "12:00", 120, lat=51.08, lng=17.05),
        _tr("Loopy's World", "Bernard", "12:00", "12:10", km=0.4, dur=10),
        _lunch(
            "12:10", "12:55", 45, [_sug("Bernard")],
            label="Bernard", loc="Park Rozrywki Loopy's World",
        ),
        _tr("Restauracja (obiad)", "Hydropolis", "12:55", "13:10",
            km=3.0, dur=15, mode=TransitMode.CAR, src="estimated_road"),
        _attr("Hydropolis", "13:10", "14:00", 50, lat=51.104, lng=17.056),
        DayEndItem(time="14:00"),
    ]
    codes = _codes(items, day=2)
    assert "meal_identity" in codes


def test_phantom_from_zabkowice_after_brzeg():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Zamek Piastów Śląskich w Brzegu", "11:00", "12:30", 90,
              lat=50.861, lng=17.467),
        _lunch("12:30", "13:15", 45, [_sug("Karczma")], label="Karczma"),
        _tr("Zamek w Ząbkowicach Śląskich", "Zamek Topacz", "13:15", "14:00",
            km=40.0, dur=45, mode=TransitMode.CAR, src="estimated_road"),
        _attr("Muzeum Motoryzacji i Techniki Zamek Topacz", "14:00", "14:11", 11,
              lat=51.02, lng=16.95),
        DayEndItem(time="14:11"),
    ]
    codes = _codes(items, day=3)
    assert "from_mismatch" in codes
    assert "mixed_regions" in codes


def test_empty_day_with_only_free_time():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _ft("09:00", "12:00", 180),
        _lunch("12:00", "12:45", 45, [_sug("IDA")], label="IDA"),
        _ft("12:45", "14:59", 134),
        DayEndItem(time="14:59"),
    ]
    assert "empty_day" in _codes(items, day=7, trip_days=7)


def test_audit_plan_walks_all_days():
    days = [
        DayPlan(day=1, title="D1", items=[
            DayStartItem(type=ItemType.DAY_START, time="09:00"),
            _attr("Hydropolis", "09:20", "10:20", 60, lat=51.104, lng=17.056),
            DayEndItem(time="10:20"),
        ]),
        DayPlan(day=2, title="D2", items=[
            DayStartItem(type=ItemType.DAY_START, time="09:00"),
            _ft("09:00", "13:47", 287),
            DayEndItem(time="13:47"),
        ]),
    ]
    codes = {d.code for d in audit_plan(days)}
    assert "empty_day" in codes
    assert "anonymous_gap" in codes
