"""FIX #324 — auditor learns the defects the client still reported.

Every test below is one remark from her Wrocław mail. The auditor was
greener than her eye: buffers passed as hops, a car did 89 km/h, a day
could die at 12:20 and nothing complained. No generate_plan here.
"""
from __future__ import annotations

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


def _lunch(start, end, dur, sugs=(), label="Lunch / przerwa regeneracyjna"):
    return LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time=start, end_time=end, duration_min=dur,
        suggestions=list(sugs), label=label, location_context="",
    )


def _codes(items, **kwargs):
    return {d.code for d in audit_day(items, **kwargs)}


def _ctx(**extra):
    base = {"day_start": "09:00", "requested_city": "Wrocław", "has_car": True}
    base.update(extra)
    return base


# --- J8 D2, J10 D2, J4 D1/D4, J6 D2: buffer instead of a hop ---

def test_ten_minute_buffer_before_zoo_is_not_a_hop():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _ft("09:00", "09:10", 10, label="Krótka przerwa / bufor"),
        _attr("ZOO Wrocław", "09:10", "11:00", 110, lat=51.105, lng=17.075),
        DayEndItem(time="11:00"),
    ]
    assert "missing_hop" in _codes(items, day=2, context=_ctx())


def test_sixty_minutes_of_padding_before_muzeum_is_not_a_hop():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _ft("09:00", "09:30", 30, label="Krótka przerwa / bufor"),
        _ft("09:30", "10:00", 30, label="Spokojny poranek"),
        _attr("Muzeum Przyrodnicze we Wrocławiu", "10:00", "11:30", 90,
              lat=51.111, lng=17.047),
        DayEndItem(time="11:30"),
    ]
    assert "missing_hop" in _codes(items, day=5, context=_ctx())


def test_leading_hop_present_is_clean():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "ZOO Wrocław", "09:00", "09:15", km=4.0, dur=15,
            mode=TransitMode.CAR, src="estimated_road"),
        _attr("ZOO Wrocław", "09:15", "11:00", 105, lat=51.105, lng=17.075),
        DayEndItem(time="11:00"),
    ]
    assert "missing_hop" not in _codes(items, day=2, context=_ctx())


def test_glued_rynek_stays_the_only_courtyard_exception():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Rynek we Wrocławiu", "09:00", "10:00", 60,
              lat=51.1079, lng=17.0385),
        DayEndItem(time="10:00"),
    ]
    assert "missing_hop" not in _codes(items, day=1, context=_ctx())


def test_rynek_an_hour_after_start_still_needs_a_hop():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _ft("09:00", "10:00", 60, label="Spokojny poranek"),
        _attr("Rynek we Wrocławiu", "10:00", "11:00", 60,
              lat=51.1079, lng=17.0385),
        DayEndItem(time="11:00"),
    ]
    assert "missing_hop" in _codes(items, day=1, context=_ctx())


# --- J4 D3: lunch teleports to Żórawina ---

def test_lunch_without_coords_after_free_time_is_a_teleport():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Hala Targowa", "09:00", "09:20", km=2.0, dur=20,
            mode=TransitMode.CAR, src="estimated_road"),
        _attr("Hala Targowa", "09:20", "11:00", 100, lat=51.114, lng=17.041),
        _ft("11:00", "11:30", 30, label="Czas dla siebie"),
        _lunch("11:30", "12:15", 45, label="Renesans"),
        _tr("Renesans", "Muzeum Narodowe we Wrocławiu", "12:15", "12:40",
            km=18.0, dur=25, mode=TransitMode.CAR, src="estimated_road"),
        _attr("Muzeum Narodowe we Wrocławiu", "12:40", "14:00", 80,
              lat=51.110, lng=17.045),
        DayEndItem(time="14:00"),
    ]
    assert "missing_hop" in _codes(items, day=3, context=_ctx())


# --- J1 D2: hop to the restaurant, no kolacja ---

def test_day_ending_on_a_hop_to_a_restaurant_is_dangling():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Ogród Botaniczny", "09:00", "09:20", km=2.5, dur=20,
            mode=TransitMode.CAR, src="estimated_road"),
        _attr("Ogród Botaniczny", "09:20", "18:50", 570,
              lat=51.114, lng=17.048),
        _tr("Ogród Botaniczny", "Pierogarnia Ze Smakiem", "18:50", "19:00",
            km=1.2, dur=10),
        DayEndItem(time="19:00"),
    ]
    assert "dangling_hop" in _codes(items, day=2, context=_ctx())


def test_hop_followed_by_the_meal_is_not_dangling():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Ogród Botaniczny", "09:00", "09:20", km=2.5, dur=20,
            mode=TransitMode.CAR, src="estimated_road"),
        _attr("Ogród Botaniczny", "09:20", "18:50", 570,
              lat=51.114, lng=17.048),
        _tr("Ogród Botaniczny", "Pierogarnia Ze Smakiem", "18:50", "19:00",
            km=1.2, dur=10),
        DinnerBreakItem.model_construct(
            type=ItemType.DINNER_BREAK,
            start_time="19:00", end_time="19:45", duration_min=45,
            suggestions=[_sug("Pierogarnia Ze Smakiem")],
            label="Pierogarnia Ze Smakiem",
        ),
        DayEndItem(time="19:45"),
    ]
    assert "dangling_hop" not in _codes(items, day=2, context=_ctx())


# --- J1 D2: a wall of technical slivers ---

def test_three_slivers_in_a_row_are_fragmented():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Dom Krasnali", "09:00", "09:20", km=2.0, dur=20,
            mode=TransitMode.CAR, src="estimated_road"),
        _attr("Dom Krasnali", "09:20", "11:00", 100, lat=51.110, lng=17.031),
        _tr("Dom Krasnali", "Kurna Chata", "11:00", "11:02", km=0.15, dur=2),
        _ft("11:02", "11:12", 10, label="Krótka przerwa / bufor"),
        _lunch("11:16", "12:00", 44, [_sug("Kurna Chata")], label="Kurna Chata"),
        DayEndItem(time="12:00"),
    ]
    assert "fragmented" in _codes(items, day=2, context=_ctx())


def test_normal_blocks_are_not_fragmented():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Hydropolis", "09:00", "09:20", km=2.4, dur=20,
            mode=TransitMode.CAR, src="estimated_road"),
        _attr("Hydropolis", "09:20", "11:00", 100, lat=51.104, lng=17.056),
        _tr("Hydropolis", "Most Tumski", "11:00", "11:20", km=1.6, dur=20),
        _attr("Most Tumski", "11:20", "12:00", 40, lat=51.114, lng=17.047),
        DayEndItem(time="12:00"),
    ]
    assert "fragmented" not in _codes(items, day=2, context=_ctx())


# --- J8 D6: 155 min of "Popołudniowa przerwa" ---

def test_free_time_of_155_minutes_is_a_hole():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Rynek w Oławie", "09:00", "09:40", km=28.0, dur=40,
            mode=TransitMode.CAR, src="estimated_road"),
        _attr("Rynek w Oławie", "09:40", "13:00", 200, lat=50.94, lng=17.29),
        _lunch("13:00", "13:47", 47, [_sug("Bistro")], label="Bistro"),
        _ft("13:47", "16:22", 155, label="Popołudniowa przerwa"),
        DayEndItem(time="16:22"),
    ]
    assert "long_free_time" in _codes(items, day=6, context=_ctx())


# --- J8 D4/D7, J6 D3: the day dies before lunch is digested ---

def test_day_closing_at_1220_on_a_2000_window_is_short():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Hydropolis", "09:00", "09:20", km=2.4, dur=20,
            mode=TransitMode.CAR, src="estimated_road"),
        _attr("Hydropolis", "09:20", "11:30", 130, lat=51.104, lng=17.056),
        _tr("Hydropolis", "Bernard", "11:30", "11:40", km=1.0, dur=10),
        _lunch("11:40", "12:20", 40, [_sug("Bernard")], label="Bernard"),
        DayEndItem(time="12:20"),
    ]
    codes = _codes(items, day=7, context=_ctx(day_end="20:00"))
    assert "short_day" in codes


def test_day_closing_at_1730_is_not_short():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Hydropolis", "09:00", "09:20", km=2.4, dur=20,
            mode=TransitMode.CAR, src="estimated_road"),
        _attr("Hydropolis", "09:20", "17:30", 490, lat=51.104, lng=17.056),
        DayEndItem(time="17:30"),
    ]
    assert "short_day" not in _codes(items, day=4, context=_ctx(day_end="20:00"))


# --- J4 D5, J8 D6: satellite without a way home ---

def test_satellite_day_without_return_is_flagged():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Rynek w Oławie", "09:00", "09:40", km=28.0, dur=40,
            mode=TransitMode.CAR, src="estimated_road"),
        _attr("Rynek w Oławie", "09:40", "13:00", 200, lat=50.94, lng=17.29),
        DayEndItem(time="13:00"),
    ]
    codes = _codes(items, day=6, context=_ctx(day_end="20:00"))
    assert "no_return" in codes


def test_satellite_day_with_return_hop_is_clean_of_no_return():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Rynek w Oławie", "09:00", "09:40", km=28.0, dur=40,
            mode=TransitMode.CAR, src="estimated_road"),
        _attr("Rynek w Oławie", "09:40", "15:00", 320, lat=50.94, lng=17.29),
        _tr("Rynek w Oławie", "Wrocław centrum", "15:00", "15:40", km=28.0,
            dur=40, mode=TransitMode.CAR, src="estimated_road"),
        DayEndItem(time="15:40"),
    ]
    assert "no_return" not in _codes(items, day=6, context=_ctx(day_end="20:00"))


# --- J9 D2: 5.95 km by car in 4 minutes ---

def test_car_doing_89_kmh_through_the_city_is_dishonest():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Centrum Historii Zajezdnia", "09:00", "09:20",
            km=3.0, dur=20, mode=TransitMode.CAR, src="estimated_road"),
        _attr("Centrum Historii Zajezdnia", "09:20", "18:56", 576,
              lat=51.094, lng=17.021),
        _tr("Centrum Historii Zajezdnia", "Most Tumski", "18:56", "19:00",
            km=5.95, dur=4, mode=TransitMode.CAR, src="estimated_road"),
        _attr("Most Tumski", "19:00", "19:20", 20, lat=51.114, lng=17.047),
        DayEndItem(time="19:20"),
    ]
    assert "dishonest_leg" in _codes(items, day=2, context=_ctx())


def test_intercity_run_at_65_kmh_is_honest():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Baszta Miejska w Niemczy", "09:00", "10:00",
            km=64.58, dur=60, mode=TransitMode.CAR, src="estimated_road"),
        _attr("Baszta Miejska w Niemczy", "10:00", "11:00", 60,
              lat=50.72, lng=16.84),
        DayEndItem(time="11:00"),
    ]
    assert "dishonest_leg" not in _codes(items, day=7, context=_ctx())


def test_car_at_city_pace_is_honest():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Centrum Historii Zajezdnia", "09:00", "09:20",
            km=3.0, dur=20, mode=TransitMode.CAR, src="estimated_road"),
        _attr("Centrum Historii Zajezdnia", "09:20", "11:00", 100,
              lat=51.094, lng=17.021),
        _tr("Centrum Historii Zajezdnia", "Most Tumski", "11:00", "11:15",
            km=5.95, dur=15, mode=TransitMode.CAR, src="estimated_road"),
        _attr("Most Tumski", "11:15", "11:45", 30, lat=51.114, lng=17.047),
        DayEndItem(time="11:45"),
    ]
    assert "dishonest_leg" not in _codes(items, day=2, context=_ctx())


# --- J9 D3: Bungee for a solo relax / nature quiz ---

def test_bungee_on_a_relax_profile_is_a_conflict():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Bungee Wrocław", "09:00", "09:20", km=3.0, dur=20,
            mode=TransitMode.CAR, src="estimated_road"),
        _attr("Bungee Wrocław", "09:20", "10:20", 60, lat=51.10, lng=17.05),
        DayEndItem(time="10:20"),
    ]
    ctx = _ctx(travel_style="relax", group_type="solo")
    assert "profile_conflict" in _codes(items, day=3, context=ctx)


def test_bungee_on_an_active_profile_is_allowed():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Bungee Wrocław", "09:00", "09:20", km=3.0, dur=20,
            mode=TransitMode.CAR, src="estimated_road"),
        _attr("Bungee Wrocław", "09:20", "10:20", 60, lat=51.10, lng=17.05),
        DayEndItem(time="10:20"),
    ]
    ctx = _ctx(travel_style="active", group_type="friends")
    assert "profile_conflict" not in _codes(items, day=3, context=ctx)
