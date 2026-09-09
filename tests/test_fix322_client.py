"""FIX #322 — one satellite region / trip, dinner ≥ 17:30, family lunch, holes.

Does not call generate_plan.
"""
from __future__ import annotations

from app.application.services.plan_service import PlanService, _fix_late_lunch
from app.domain.models.plan import (
    AttractionItem,
    DayEndItem,
    DayPlan,
    DayStartItem,
    DinnerBreakItem,
    FreeTimeItem,
    ItemType,
    LunchBreakItem,
    TransitItem,
    TransitMode,
)


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur=60, *, lat=50.946, lng=17.292):
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
        address="Oława",
        city="Oława",
        cost_estimate=0,
    )


def _tr(frm, to, start, end, *, km=40.0, dur=44,
        mode=TransitMode.CAR, src="estimated_road"):
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


def _lunch(start, end, dur=45):
    return LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time=start,
        end_time=end,
        duration_min=dur,
        suggestions=[],
        label="Lunch",
    )


def _dinner(start, end, dur=45):
    return DinnerBreakItem.model_construct(
        type=ItemType.DINNER_BREAK,
        start_time=start,
        end_time=end,
        duration_min=dur,
        suggestions=[],
        label="Kolacja",
    )


def _ctx(**extra):
    base = {
        "requested_city": "Wrocław",
        "has_car": True,
        "day_start": "09:00",
        "day_end": "20:00",
        "num_days": 7,
    }
    base.update(extra)
    return base


def _names(items):
    return [
        (getattr(it, "name", "") or "")
        for it in items
        if getattr(it, "type", None) == ItemType.ATTRACTION
    ]


def test_lonely_wena_40km_is_dropped():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Wena Park Wodny", "09:00", "09:44", km=40.0, dur=44),
        _attr("Wena Park Wodny", "09:44", "11:14", 90),
        _lunch("11:14", "12:00"),
        DayEndItem(time="13:28"),
    ]
    out = _svc()._complete_thin_daytrip(items, [], _ctx(), {}, day_num=5)
    blob = " ".join(_names(out)).lower()
    assert "wena" not in blob


def test_olawa_cluster_keeps_return_and_day_end_after_it():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Wena Park Wodny", "09:00", "09:44", km=40.0, dur=44),
        _attr("Wena Park Wodny", "09:44", "11:14", 90),
        _attr("Rynek w Oławie", "11:20", "12:10", 50, lat=50.945, lng=17.293),
        _lunch("12:10", "12:55"),
        DayEndItem(time="12:55"),
    ]
    svc = _svc()
    out = svc._complete_thin_daytrip(items, [], _ctx(), {}, day_num=5)
    out = svc._reconcile_day_end_marker(out, _ctx(), day_num=5)
    names = " ".join(_names(out)).lower()
    assert "wena" in names
    assert "oław" in names or "olaw" in names
    returns = [
        it for it in out
        if getattr(it, "type", None) == ItemType.TRANSIT
        and "wrocław" in (getattr(it, "to_location", "") or "").lower()
        and "oław" not in (getattr(it, "to_location", "") or "").lower()
    ]
    assert returns, "Oława cluster must drive back to Wrocław"
    ret_end = max(getattr(it, "end_time", "") or "" for it in returns)
    marker = next(
        it for it in out if getattr(it, "type", None) == ItemType.DAY_END
    )
    assert (marker.time or "") >= ret_end


def test_second_olawa_day_is_stripped_by_guardian():
    cluster = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Wena Park Wodny", "09:00", "09:44", km=40.0, dur=44),
        _attr("Wena Park Wodny", "09:44", "11:14", 90),
        _attr("Rynek w Oławie", "11:20", "12:10", 50, lat=50.945, lng=17.293),
        DayEndItem(time="13:28"),
    ]
    lonely = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Rynek w Oławie", "09:00", "09:42", km=38.0, dur=42),
        _attr("Rynek w Oławie", "09:42", "10:42", 60, lat=50.945, lng=17.293),
        DayEndItem(time="12:42"),
    ]
    days = [
        DayPlan(day=5, title="D5", items=cluster),
        DayPlan(day=6, title="D6", items=lonely),
    ]
    out = _svc()._guard_trip_invariants(days, _ctx(), coord_map={}, user={})
    d5 = next(d for d in out if int(d.day) == 5)
    d6 = next(d for d in out if int(d.day) == 6)
    n5 = " ".join(_names(d5.items or [])).lower()
    n6 = " ".join(_names(d6.items or [])).lower()
    assert "wena" in n5 or "oław" in n5 or "olaw" in n5
    assert "wena" not in n6
    assert "oław" not in n6 and "olaw" not in n6


def test_family_lunch_1446_moves_to_1330():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:30"),
        _attr(
            "Hydropolis", "10:00", "12:00", 120,
            lat=51.104, lng=17.056,
        ),
        _lunch("14:46", "15:26"),
        DayEndItem(time="16:00"),
    ]
    user = {"target_group": "family_kids", "children_age": 5}
    svc = _svc()
    out = svc._resit_late_lunch_after_morning_stop(items, user, day_num=2)
    out = _fix_late_lunch(out, latest_min=13 * 60 + 30)
    lunch = next(it for it in out if it.type == ItemType.LUNCH_BREAK)
    assert lunch.start_time <= "13:30"


def test_dinner_1630_is_pushed_to_1730():
    items = [
        _attr("Warzywniak", "15:10", "16:05", 55, lat=51.109, lng=17.032),
        _ft("16:05", "16:30", 25),
        _dinner("16:30", "17:15"),
        DayEndItem(time="19:00"),
    ]
    out = _svc()._enforce_dinner_not_before_1730(
        items, _ctx(day_end="20:00"), day_num=2,
    )
    dinner = next(it for it in out if it.type == ItemType.DINNER_BREAK)
    assert dinner.start_time >= "17:30"


def test_self_hop_dropped_regardless_of_km():
    items = [
        _attr("Warzywniak", "12:00", "13:00", 60, lat=51.109, lng=17.032),
        _tr("Warzywniak", "Warzywniak", "13:00", "13:20", km=3.2, dur=20),
        _attr("Rynek", "13:20", "14:20", 60, lat=51.110, lng=17.032),
    ]
    out = _svc()._drop_hops_not_to_next_stop(items, day_num=2)
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert not hops


def test_zajezdnia_stays_at_1000_after_morning_pull():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _ft("09:00", "10:00", 60, label="Spokojny poranek"),
        _attr(
            "Zajezdnia", "10:00", "11:30", 90,
            lat=51.094, lng=17.021,
        ),
        DayEndItem(time="16:00"),
    ]
    out = _svc()._pull_day_forward_to_start(
        items, _ctx(day_start="09:00", day_end="18:00"), day_num=3,
    )
    zaj = next(it for it in out if it.type == ItemType.ATTRACTION)
    assert zaj.start_time == "10:00"


def test_ft_overlapping_meal_hop_is_clipped():
    items = [
        _attr(
            "Muzeum Przyrodnicze we Wrocławiu", "10:00", "11:05", 65,
            lat=51.117, lng=17.046,
        ),
        _ft("11:05", "12:10", 65),
        _tr(
            "Muzeum Przyrodnicze we Wrocławiu",
            "Olio Pizza Napoletana",
            "12:03", "12:19", km=1.05, dur=16,
            mode=TransitMode.WALK, src="estimated_walk",
        ),
        _lunch("12:19", "13:19", 60),
    ]
    out = _svc()._clip_free_time_overlapping_hops(items)
    fts = [it for it in out if it.type == ItemType.FREE_TIME]
    assert fts
    assert fts[0].end_time <= "12:03"
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert hops


def test_post_dinner_ft_tail_is_dropped():
    items = [
        _attr("Hydropolis", "14:00", "15:30", 90, lat=51.104, lng=17.056),
        _dinner("17:30", "18:15"),
        _ft("18:15", "20:00", 105),
        DayEndItem(time="20:00"),
    ]
    out = _svc()._trim_idle_after_dinner(items, day_num=9)
    fts = [it for it in out if it.type == ItemType.FREE_TIME]
    assert not fts
