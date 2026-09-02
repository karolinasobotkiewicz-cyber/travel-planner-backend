"""FIX #305 — Wrocław leftover: large FT, ghost hops, Topacz, IDA, Tadeusz."""
from __future__ import annotations

from types import SimpleNamespace

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
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


def _tr(frm, to, start, end, *, km, dur, mode=TransitMode.WALK, src="estimated_road"):
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
    return FreeTimeItem(
        type=ItemType.FREE_TIME,
        start_time=start,
        end_time=end,
        duration_min=dur,
        label=label,
        suggestions=[],
    )


def test_72min_ft_before_attraction_is_eaten():
    items = [
        _attr("Hydropolis", "16:00", "17:34", 94),
        _ft("17:34", "18:46", 72),
        _attr("Most Tumski", "18:46", "19:20", 34, lat=51.114, lng=17.047),
    ]
    out = _svc()._eat_long_free_time_before_attraction(items, day_num=3)
    fts = [it for it in out if it.type == ItemType.FREE_TIME]
    assert fts
    assert int(fts[0].duration_min) <= 25


def test_151min_ft_before_dinner_is_eaten():
    dinner = DinnerBreakItem.model_construct(
        type=ItemType.DINNER_BREAK,
        start_time="20:09",
        end_time="21:00",
        duration_min=51,
        suggestions=[],
    )
    items = [
        _attr("Hydropolis", "16:00", "17:38", 98),
        _ft("17:38", "20:09", 151),
        dinner,
    ]
    out = _svc()._eat_long_free_time_before_attraction(items, day_num=2)
    fts = [it for it in out if it.type == ItemType.FREE_TIME]
    assert fts
    assert int(fts[0].duration_min) <= 25


def test_182min_morning_ft_is_pulled():
    items = [
        _ft("09:00", "12:02", 182, label="Spokojny poranek"),
        _attr("Hala Stulecia", "12:02", "13:00", 58, lat=51.107, lng=17.077),
    ]
    out = _svc()._pull_next_stop_over_large_gaps(
        items, {"day_start": "09:00"}, day_num=5,
    )
    fts = [it for it in out if it.type == ItemType.FREE_TIME]
    assert not fts or int(fts[0].duration_min) <= 25
    first = next(it for it in out if it.type == ItemType.ATTRACTION)
    # FIX #311: sights stay at opening-hour floor 10:00 (not 09:30).
    assert first.start_time == "10:00"


def test_name_holes_does_not_invent_72min_block():
    items = [
        _attr("Hydropolis", "16:00", "17:34", 94),
        _attr("Most Tumski", "18:46", "19:20", 34, lat=51.114, lng=17.047),
    ]
    out = _svc()._name_remaining_holes(
        items, {"day_start": "09:00", "day_end": "20:00"}, day_num=3,
    )
    fts = [it for it in out if it.type == ItemType.FREE_TIME]
    assert all(int(it.duration_min) <= 45 for it in fts)


def test_warzywniak_rynek_retargets_to_kwatera():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="13:00",
        end_time="14:00",
        duration_min=60,
        suggestions=[
            RestaurantSuggestion.model_construct(
                id="w", name="Warzywniak", lat=51.11, lng=17.03, city="Wrocław",
            )
        ],
    )
    items = [
        lunch,
        _tr("Warzywniak", "Rynek", "14:00", "14:10", km=0.6, dur=10),
        _attr("Kwatera Główna", "14:15", "15:15", 60),
    ]
    out = _svc()._retarget_all_legs_to_next_stop(items, day_num=1)
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert hops
    assert "kwatera" in (hops[0].to_location or "").lower()


def test_bastion_forum_retargets_to_zajezdnia():
    items = [
        _attr("Bastion Sakwowy", "14:00", "15:00", 60),
        _tr("Bastion Sakwowy", "Restauracja Forum Kulinarne", "15:00", "15:20", km=3.0, dur=20),
        _attr("Centrum Historii Zajezdnia", "15:25", "16:25", 60, lat=51.09, lng=17.0),
    ]
    out = _svc()._retarget_all_legs_to_next_stop(items, day_num=3)
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert hops
    assert "zajezdnia" in (hops[0].to_location or "").lower()


def test_1833km_walk_6min_becomes_honest_walk():
    items = [
        _tr(
            "Wyspa Słodowa", "VaffaNapoli",
            "13:00", "13:06", km=1.833, dur=6,
            mode=TransitMode.WALK, src="estimated_road",
        ),
    ]
    out = _svc()._honest_transit_physics(items, day_num=4, context={"has_car": True})
    mode = str(getattr(out[0].mode, "value", out[0].mode) or "").lower()
    assert "walk" in mode
    assert int(out[0].duration_min) >= 18
    assert "walk" in str(out[0].routing_source or "").lower()


def test_zajezdnia_hop_does_not_start_during_visit():
    items = [
        _attr("Centrum Historii Zajezdnia", "11:44", "12:44", 60),
        _tr(
            "Zajezdnia", "VaffaNapoli",
            "12:34", "12:44", km=2.0, dur=10,
            mode=TransitMode.CAR, src="estimated_road",
        ),
    ]
    out = _svc()._snap_transits_to_previous_stop_end(items, day_num=2)
    hop = next(it for it in out if it.type == ItemType.TRANSIT)
    assert hop.start_time >= "12:44"


def test_empty_lunch_then_topacz_gets_a_drive():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="12:12",
        end_time="13:12",
        duration_min=60,
        suggestions=[],
    )
    items = [
        lunch,
        _attr(
            "Muzeum Motoryzacji Zamek Topacz",
            "13:12", "14:12", 60,
            lat=51.05, lng=16.86,
        ),
    ]
    out = _svc()._ensure_city_to_far_after_meal(
        items, {}, {"requested_city": "Wrocław", "has_car": True}, day_num=5,
    )
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert hops
    assert "topacz" in (hops[0].to_location or "").lower()


def test_ida_to_muzeum_narodowe_gets_a_hop():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="12:41",
        end_time="13:41",
        duration_min=60,
        suggestions=[
            RestaurantSuggestion.model_construct(
                id="ida", name="IDA", lat=51.109, lng=17.032, city="Wrocław",
            )
        ],
    )
    items = [
        lunch,
        _attr("Muzeum Narodowe", "13:51", "14:51", 60, lat=51.110, lng=17.048),
    ]
    out = _svc()._ensure_stop_to_stop_legs(
        items, {}, {"has_car": True, "requested_city": "Wrocław"}, day_num=3,
    )
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert hops
    assert "narodowe" in (hops[0].to_location or "").lower()


def test_pana_tadeusza_not_twice_on_trip():
    days = [
        SimpleNamespace(day=1, items=[
            _attr("Muzeum Pana Tadeusza", "10:00", "11:00"),
        ]),
        SimpleNamespace(day=4, items=[
            _attr("Muzeum Pana Tadeusza", "15:00", "16:00"),
        ]),
    ]
    out = _svc()._strip_cross_day_trip_repeats(days)
    names = [
        getattr(it, "name", "")
        for d in out for it in (d.items or [])
        if it.type == ItemType.ATTRACTION
    ]
    assert sum("tadeusz" in n.lower() for n in names) == 1


def test_pergola_still_unique_across_days():
    days = [
        SimpleNamespace(day=1, items=[
            _attr("Pergola przy Hali Stulecia", "10:00", "11:00"),
        ]),
        SimpleNamespace(day=3, items=[
            _attr("Pergola przy Hali Stulecia", "14:00", "15:00"),
        ]),
    ]
    out = _svc()._strip_cross_day_trip_repeats(days)
    names = [
        getattr(it, "name", "")
        for d in out for it in (d.items or [])
        if it.type == ItemType.ATTRACTION
    ]
    assert sum("pergola" in n.lower() for n in names) == 1
