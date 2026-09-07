"""FIX #314 — clocks, empty dinner, waiting, hours, short Dworzec.

Client Wrocław follow-up: 50 min empty morning, dinner with no restaurant,
68 min buffer after a 2 min hop, Neon Side 18:00–18:01 vs duration 45,
overlap Wyspa/transit, Przyrodnicze before opening, stacked waits,
Dworzec Świebodzki as a 60 min visit.
"""
from __future__ import annotations

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


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur=60, *, lat=51.0774, lng=17.0188):
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


def _dinner(start, end, dur, sugs, label="Kolacja"):
    return DinnerBreakItem.model_construct(
        type=ItemType.DINNER_BREAK,
        start_time=start, end_time=end, duration_min=dur,
        label=label, suggestions=sugs,
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


def test_clocks_win_over_stale_duration():
    items = [_attr("Galeria Neon Side", "18:00", "18:01", 45)]
    out = _svc()._sync_timeline_clocks(items)
    assert out[0].duration_min == 1


def test_crushed_neon_grows_into_following_free_time():
    items = [
        _attr("Galeria Neon Side", "18:00", "18:01", 45, lat=51.11, lng=17.03),
        _ft("18:06", "18:30", 24),
        _tr("Galeria Neon Side", "The Cork", "18:30", "18:40", km=0.4, dur=10),
    ]
    out = _svc()._extend_crushed_attraction_into_gap(
        items, _ctx(day_end="20:00"), day_num=2,
    )
    neon = [it for it in out if getattr(it, "type", None) == ItemType.ATTRACTION][0]
    assert neon.end_time >= "18:20"


def test_54min_buffer_before_attraction_is_eaten():
    items = [
        _attr("Panorama Racławicka", "09:30", "10:50", 80),
        _ft("10:50", "11:44", 54, label="Krótka przerwa / bufor"),
        _attr("Sky Tower", "11:44", "12:30", 46, lat=51.094, lng=17.02),
    ]
    out = _svc()._eat_long_free_time_before_attraction(items, day_num=1)
    fts = [it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME]
    assert fts
    assert int(fts[0].duration_min) <= 25


def test_stacked_waits_before_olawa_square_are_eaten():
    items = [
        _tr("Wrocław", "Rynek w Oławie", "12:40", "13:23", km=28, dur=43),
        _ft("13:23", "14:48", 85),
        _ft("14:48", "15:13", 25),
        _attr("Rynek w Oławie", "15:13", "16:00", 47, lat=50.94, lng=17.29),
    ]
    out = _svc()._eat_long_free_time_before_attraction(items, day_num=7)
    rynek = [it for it in out if getattr(it, "type", None) == ItemType.ATTRACTION][0]
    assert rynek.start_time < "15:13"


def test_wyspa_transit_overlap_is_shifted():
    items = [
        _attr("Wyspa Słodowa", "13:00", "13:54", 54, lat=51.116, lng=17.038),
        _tr("Wyspa Słodowa", "Warzywniak", "13:46", "13:55", km=0.6, dur=9),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="13:55", end_time="14:40", duration_min=45,
            suggestions=[], location_context="centrum",
        ),
    ]
    out = _svc()._remove_timeline_overlaps(items, 2)
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert hops
    assert hops[0].start_time >= "13:54"


def test_przyrodnicze_before_opening_is_shifted():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Muzeum Przyrodnicze we Wrocławiu", "09:20", "10:20", 60),
        DayEndItem(time="16:00"),
    ]
    out = _svc()._strip_after_hours_museums(items, day_num=5, trip_date="2026-02-24")
    attrs = [it for it in out if getattr(it, "type", None) == ItemType.ATTRACTION]
    assert attrs
    assert attrs[0].start_time >= "10:00"


def test_dworzec_swiebodzki_is_a_short_stop():
    items = [_attr("Dworzec Świebodzki", "10:00", "11:00", 60)]
    out = _svc()._cap_stretched_attraction_durations(items, day_num=4)
    assert int(out[0].duration_min) <= 30


def test_morning_50min_hole_is_pulled_for_rynek():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _ft("09:00", "09:50", 50, label="Spokojny poranek"),
        _attr("Rynek we Wrocławiu", "09:50", "10:50", 60, lat=51.110, lng=17.032),
        DayEndItem(time="16:00"),
    ]
    out = _svc()._pull_day_forward_to_start(items, _ctx(), day_num=1)
    attrs = [it for it in out if getattr(it, "type", None) == ItemType.ATTRACTION]
    assert attrs
    assert attrs[0].start_time <= "09:20"


def test_empty_dinner_snaps_to_nearby_restaurant():
    items = [
        _attr("Park Mamuta", "16:45", "17:30", 45, lat=51.09, lng=17.01),
        _dinner("17:30", "18:15", 45, []),
    ]
    ctx = _ctx(restaurants_available=[{
        "id": "r1", "name": "Konspira", "lat": 51.091, "lng": 17.012,
        "city": "Wrocław", "address": "Wrocław",
    }])
    out = _svc()._snap_meals_to_nearby_restaurants(
        items, ctx, {"preferences": []}, day_num=1,
    )
    dinners = [it for it in out if getattr(it, "type", None) == ItemType.DINNER_BREAK]
    assert dinners
    assert dinners[0].suggestions


def test_68min_buffer_after_two_minute_hop_is_eaten():
    items = [
        _attr("Sky Tower", "12:30", "13:34", 64, lat=51.094, lng=17.02),
        _tr("Sky Tower", "Wystawa Pająków", "13:34", "13:36", km=0.063, dur=2),
        _ft("13:36", "14:44", 68, label="Krótka przerwa / bufor"),
        _attr("Wystawa Pająków", "14:44", "15:30", 46, lat=51.094, lng=17.021),
    ]
    out = _svc()._eat_long_free_time_before_attraction(items, day_num=3)
    fts = [it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME]
    assert fts
    assert int(fts[0].duration_min) <= 25
