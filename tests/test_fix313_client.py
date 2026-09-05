"""FIX #313 — attractions must survive finalisation, no teleports, no lost half-days.

Client report: "generator wybiera atrakcje, ale później gubi je w finalnym
planie", "teleporty typu przejazd z Aquaparku", "bloki free_time po 1-3,5
godziny", "warnings dalej zwraca pustą tablicę".
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


def _sug(name):
    return RestaurantSuggestion.model_construct(
        id=f"id-{name}", name=name, lat=51.11, lng=17.03,
        city="Wrocław", address="",
    )


def _lunch(start, end, dur, sugs, label="Lunch / przerwa regeneracyjna"):
    return LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time=start, end_time=end, duration_min=dur,
        label=label, suggestions=sugs, location_context="centrum",
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


def _names(items):
    return [
        it.name for it in items
        if getattr(it, "type", None) == ItemType.ATTRACTION
    ]


def test_winter_strip_without_pool_keeps_open_attractions():
    items = [
        _attr("Aquapark Wrocław", "09:10", "11:10", 120),
        _attr("Hydropolis", "11:30", "13:00", 90),
        _attr("Arboretum Wojsławice", "14:00", "15:30", 90),
    ]
    out = _svc()._strip_winter_closed_attractions(
        items, "2026-02-20", day_num=1,
    )
    assert "Aquapark Wrocław" in _names(out)
    assert "Hydropolis" in _names(out)
    assert "Arboretum Wojsławice" not in _names(out)


def test_winter_strip_is_a_noop_outside_winter():
    items = [_attr("Arboretum Wojsławice", "14:00", "15:30", 90)]
    out = _svc()._strip_winter_closed_attractions(
        items, "2026-07-20", day_num=1,
    )
    assert _names(out) == ["Arboretum Wojsławice"]


def test_empty_poi_pool_must_not_delete_the_day():
    items = [
        _attr("Rynek we Wrocławiu", "09:10", "10:10", 60),
        _attr("Hydropolis", "10:25", "11:55", 90),
    ]
    # The FIX #312 regression: empty pool => allowed_ids empty => wipe.
    out = _svc()._strip_winter_closed_attractions(
        items, "2026-02-20", day_num=1,
    )
    assert len(_names(out)) == 2


def test_seal_keeps_every_attraction_of_a_normal_day():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Rynek we Wrocławiu", "09:00", "09:10"),
        _attr("Rynek we Wrocławiu", "09:10", "10:10", 60),
        _tr("Rynek we Wrocławiu", "Hydropolis", "10:10", "10:25", km=2.4, dur=15),
        _attr("Hydropolis", "10:25", "11:55", 90, lat=51.104, lng=17.09),
        _tr("Hydropolis", "IDA", "11:55", "12:05", km=1.2, dur=10),
        _lunch("12:05", "12:45", 40, [_sug("IDA kuchnia i wino")]),
        _tr("IDA", "Aquapark Wrocław", "12:45", "13:00", km=3.0, dur=15),
        _attr("Aquapark Wrocław", "13:00", "15:00", 120, lat=51.09, lng=17.01),
        DayEndItem(time="15:00"),
    ]
    out = _svc()._seal_client_day_window(
        items, _ctx(day_end="16:00"), {"preferences": []}, {}, day_num=1,
    )
    kept = _names(out)
    for name in ("Rynek we Wrocławiu", "Hydropolis", "Aquapark Wrocław"):
        assert name in kept, f"{name} disappeared from the sealed timeline"


def test_pre_start_attraction_is_shifted_not_deleted():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="10:00"),
        _attr("Ogród Botaniczny", "09:47", "10:47", 60),
        DayEndItem(time="16:00"),
    ]
    out = _svc()._clip_timeline_to_declared_window(
        items, _ctx(day_start="10:00", day_end="16:00"), day_num=1,
    )
    attrs = [it for it in out if getattr(it, "type", None) == ItemType.ATTRACTION]
    assert len(attrs) == 1
    assert attrs[0].start_time >= "10:00"


def test_opening_hop_from_a_stripped_stop_falls_back_to_the_city():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Arboretum Wojsławice", "Dolina Tatarska", "10:45", "10:56"),
        _attr("Dolina Tatarska", "11:40", "13:00", 80),
        DayEndItem(time="13:40"),
    ]
    out = _svc()._retarget_all_legs_to_prev_stop(
        items, day_num=6, context=_ctx(),
    )
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert hops
    assert "arboretum" not in hops[0].from_location.lower()


def test_meal_without_suggestions_is_de_identified():
    items = [
        _attr("Muzeum Motoryzacji Wena", "09:44", "11:14", 90),
        _lunch("13:29", "14:14", 45, [], label="Chinkalnia Wrocław Sukiennice"),
        _dinner("18:00", "18:45", 45, [], label="The Cork"),
    ]
    out = _svc()._scrub_phantom_meal_stops(items, day_num=5)
    lunch = [it for it in out if getattr(it, "type", None) == ItemType.LUNCH_BREAK][0]
    dinner = [it for it in out if getattr(it, "type", None) == ItemType.DINNER_BREAK][0]
    assert "chinkalnia" not in lunch.label.lower()
    assert "cork" not in dinner.label.lower()


def test_named_meal_with_suggestions_is_left_alone():
    items = [_lunch("12:00", "12:40", 40, [_sug("IDA")], label="IDA")]
    out = _svc()._scrub_phantom_meal_stops(items, day_num=1)
    assert out[0].label == "IDA"


def test_approach_hop_is_delayed_instead_of_waiting_at_the_door():
    items = [
        _attr("Panorama Racławicka", "09:45", "10:15", 30),
        _tr("Panorama Racławicka", "Restauracja Česká", "10:15", "10:29",
            km=0.9, dur=14),
        _lunch("12:00", "12:40", 40, [_sug("Restauracja Česká")],
               label="Restauracja Česká"),
    ]
    out = _svc()._delay_meal_approach_hop(items, day_num=3)
    hop = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT][0]
    assert hop.end_time == "12:00"
    assert hop.start_time == "11:46"


def test_approach_hop_is_not_pulled_before_the_previous_stop_ends():
    items = [
        _attr("Panorama Racławicka", "09:45", "11:55", 130),
        _tr("Panorama Racławicka", "Česká", "11:55", "12:05", km=0.6, dur=10),
        _lunch("12:10", "12:50", 40, [_sug("Česká")], label="Česká"),
    ]
    out = _svc()._delay_meal_approach_hop(items, day_num=3)
    hop = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT][0]
    assert hop.start_time >= "11:55"


def test_long_interior_gap_is_fully_labelled():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Panorama Racławicka", "09:30", "15:13", 343),
        _attr("Most Tumski", "17:53", "18:40", 47),
        DayEndItem(time="18:40"),
    ]
    out = _svc()._name_remaining_holes(
        items, _ctx(day_end="19:00"), day_num=3,
    )
    covered = sum(
        it.duration_min for it in out
        if getattr(it, "type", None) == ItemType.FREE_TIME
    )
    assert covered >= 155, f"only {covered} of the 160 min gap got a label"


def test_labelled_blocks_stay_under_an_hour_each():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Panorama Racławicka", "09:30", "15:13", 343),
        _attr("Most Tumski", "17:53", "18:40", 47),
        DayEndItem(time="18:40"),
    ]
    out = _svc()._name_remaining_holes(
        items, _ctx(day_end="19:00"), day_num=3,
    )
    for it in out:
        if getattr(it, "type", None) == ItemType.FREE_TIME:
            assert it.duration_min <= 60


def test_collapse_does_not_build_a_three_hour_block():
    items = [
        _ft("09:00", "09:45", 45),
        _ft("09:45", "10:30", 45),
        _ft("10:30", "11:15", 45),
        _ft("11:15", "12:00", 45),
    ]
    out = _svc()._collapse_adjacent_free_time(items, day_num=6)
    for it in out:
        assert it.duration_min <= 90


def test_hard_merge_does_not_build_a_three_hour_block():
    items = [
        _ft("09:00", "09:45", 45),
        _ft("09:45", "10:30", 45),
        _ft("10:30", "11:15", 45),
        _ft("11:15", "12:00", 45),
    ]
    out = _svc()._merge_abutting_free_time_hard(items, day_num=6)
    for it in out:
        assert it.duration_min <= 90


def test_day_without_attractions_is_reported():
    day = DayPlan(
        day=2,
        title="Dzień 2",
        items=[
            DayStartItem(type=ItemType.DAY_START, time="09:00"),
            _ft("09:00", "12:00", 180),
            _lunch("12:00", "12:58", 58, [_sug("IDA")]),
            DayEndItem(time="12:58"),
        ],
        quality_badges=[],
    )
    out = _svc()._day_density_warnings([day], "09:00", "18:00")
    types = {w["type"] for w in out}
    assert "day_without_attractions" in types
    flagged = [w for w in out if w["type"] == "day_without_attractions"][0]
    assert flagged["day"] == 2
    assert flagged["severity"] == "warning"


def test_full_day_raises_no_density_warning():
    day = DayPlan(
        day=1,
        title="Rynek we Wrocławiu i Hydropolis",
        items=[
            DayStartItem(type=ItemType.DAY_START, time="09:00"),
            _attr("Rynek we Wrocławiu", "09:00", "12:00", 180),
            _attr("Hydropolis", "12:30", "17:00", 270),
            DayEndItem(time="17:00"),
        ],
        quality_badges=[],
    )
    assert _svc()._day_density_warnings([day], "09:00", "18:00") == []
