"""FIX #312 — declared window, FT/transit overlap, first hops, winter Arboretum."""
from __future__ import annotations

from app.application.services.plan_service import (
    PlanService,
    _wroclaw_seed_coords,
)
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


def _tr(frm, to, start, end, *, km, dur, mode=TransitMode.CAR, src="estimated_road"):
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


def _sug(name):
    return RestaurantSuggestion.model_construct(
        id=f"id-{name}", name=name, lat=51.11, lng=17.03, city="Wrocław", address="",
    )


def _lunch(start, end, dur, sugs):
    return LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time=start, end_time=end, duration_min=dur,
        suggestions=sugs, location_context="centrum",
    )


def _dinner(start, end, dur, sugs):
    return DinnerBreakItem.model_construct(
        type=ItemType.DINNER_BREAK,
        start_time=start, end_time=end, duration_min=dur,
        suggestions=sugs, location_context="centrum",
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


def test_wroclaw_aquapark_seed_is_not_rynek():
    latlng = _wroclaw_seed_coords("Aquapark Wrocław")
    assert latlng
    assert abs(latlng[1] - 17.0385) > 0.01


def test_pre_window_free_time_is_clipped():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="10:00"),
        _ft("09:00", "10:10", 70),
        _attr("Aquapark Wrocław", "10:10", "12:10", 120),
        DayEndItem(time="16:00"),
    ]
    out = _svc()._clip_timeline_to_declared_window(
        items, _ctx(day_start="10:00", day_end="16:00"), day_num=1,
    )
    fts = [it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME]
    for it in fts:
        assert it.start_time >= "10:00"
    starts = [getattr(it, "time", None) or getattr(it, "start_time", None) for it in out]
    assert all(s is None or s >= "10:00" or getattr(it, "type", None) == ItemType.DAY_START
               for it, s in zip(out, starts))


def test_ft_overlapping_transit_is_split():
    items = [
        _attr("Park Mamuta", "15:00", "16:01", 61, lat=51.09, lng=17.01),
        _ft("16:01", "16:27", 26),
        _tr("Park Mamuta", "Hydropolis", "16:01", "16:20", km=3.2, dur=19),
        _attr("Hydropolis", "16:20", "17:50", 90, lat=51.104, lng=17.09),
    ]
    out = _svc()._remove_timeline_overlaps(items, 2)
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    fts = [it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME]
    assert hops
    for ft in fts:
        for hop in hops:
            ft_s, ft_e = ft.start_time, ft.end_time
            assert ft_e <= hop.start_time or ft_s >= hop.end_time


def test_lunch_is_pushed_after_arrival_hop():
    items = [
        _attr("Muzeum Świat Iluzji", "10:00", "11:58"),
        _tr("Muzeum Świat Iluzji", "Česká", "11:58", "12:15", km=0.8, dur=17,
            mode=TransitMode.WALK, src="estimated_walk"),
        _lunch("12:12", "13:00", 48, [_sug("Restauracja Česká")]),
    ]
    out = _svc()._snap_meals_after_approach_hop(items, day_num=1)
    meals = [it for it in out if getattr(it, "type", None) == ItemType.LUNCH_BREAK]
    assert meals
    assert meals[0].start_time >= "12:15"


def test_day_end_matches_last_named_item():
    items = [
        _attr("Pergola", "14:00", "14:40", 40),
        _ft("14:40", "16:00", 80),
        DayEndItem(time="14:40"),
    ]
    out = _svc()._reconcile_day_end_marker(
        items, _ctx(day_end="16:00"), day_num=1, include_named_tail=True,
    )
    ends = [it for it in out if getattr(it, "type", None) == ItemType.DAY_END]
    assert ends
    assert ends[0].time >= "16:00" or ends[0].time == "16:00"


def test_orphan_trailing_hop_is_dropped():
    items = [
        _attr("Hydropolis", "14:00", "15:30", 90),
        _tr("Hydropolis", "Muzeum Pana Tadeusza", "15:30", "15:45", km=3.0, dur=15),
        DayEndItem(time="16:00"),
    ]
    out = _svc()._drop_trailing_orphan_transits(items, day_num=2)
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert not hops


def test_narodowe_before_open_is_shifted():
    items = [_attr("Muzeum Narodowe we Wrocławiu", "09:05", "10:35", 90,
                   lat=51.110, lng=17.047)]
    out = _svc()._strip_after_hours_museums(
        items, day_num=3, trip_date="2026-02-20",
    )
    assert out
    assert out[0].start_time >= "10:00"


def test_winter_arboretum_is_stripped():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Arboretum Wojsławice", "10:00", "11:30", 90, lat=50.725, lng=16.852),
        DayEndItem(time="20:00"),
    ]
    out = _svc()._strip_out_of_season_attractions(items, "2026-02-20", {})
    names = [getattr(it, "name", "") for it in out if getattr(it, "type", None) == ItemType.ATTRACTION]
    assert not any("arboretum" in n.lower() for n in names)


def test_55km_car_50min_is_shortened():
    items = [
        _tr("Most Tumski", "Galeria Neon Side", "17:00", "17:50", km=5.5, dur=50),
    ]
    out = _svc()._honest_transit_physics(items, day_num=3, context=_ctx())
    assert int(out[0].duration_min) <= 25


def test_stacked_waits_collapse():
    items = [
        _attr("Bernard", "12:00", "13:27"),
        _ft("13:27", "14:12", 45),
        _ft("14:12", "14:27", 15),
        _ft("14:27", "14:47", 20),
        _attr("Muzeum Narodowe we Wrocławiu", "14:47", "16:17", 90),
    ]
    out = _svc()._collapse_adjacent_free_time(items, day_num=4)
    fts = [it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME]
    assert len(fts) == 1
    assert int(fts[0].duration_min) >= 70


def test_aquapark_gets_leading_hop():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _ft("09:00", "09:10", 10),
        _attr("Aquapark Wrocław", "09:10", "11:10", 120, lat=51.0774, lng=17.0188),
    ]
    out = _svc()._ensure_leading_transit(items, {}, _ctx(), day_num=2)
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert hops
    assert "aquapark" in (hops[0].to_location or "").lower()


def test_past_window_tail_is_clipped():
    items = [
        _dinner("18:15", "19:00", 45, [_sug("The Cork")]),
        _ft("19:00", "19:45", 45),
        _ft("19:45", "20:00", 15, "bufor"),
        DayEndItem(time="18:15"),
    ]
    out = _svc()._clip_timeline_to_declared_window(
        items, _ctx(day_start="09:00", day_end="19:00"), day_num=1,
    )
    for it in out:
        en = getattr(it, "end_time", None)
        if en:
            assert en <= "19:40"
        if getattr(it, "start_time", None):
            assert it.start_time < "19:01" or it.start_time == "19:00"
