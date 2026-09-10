"""FIX #326 — one break and one ride between two stops, never a sliver wall.

Client J1 D2: "dojście 2 min, potem 10 min free time, potem jeszcze 4 min
niewyjaśnionej różnicy przed lunchem. Później znowu 10 min po lunchu."
No generate_plan here.
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
    TransitItem,
    TransitMode,
)
from app.domain.planner.time_utils import time_to_minutes


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur=60, *, lat=51.116, lng=17.048):
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


def _ft(start, end, dur, label="Krótka przerwa / bufor"):
    return FreeTimeItem.model_construct(
        type=ItemType.FREE_TIME,
        start_time=start,
        end_time=end,
        duration_min=dur,
        label=label,
        suggestions=[],
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


def _ctx(**extra):
    base = {
        "requested_city": "Wrocław",
        "has_car": True,
        "day_start": "09:00",
        "day_end": "20:00",
    }
    base.update(extra)
    return base


def _spans(out):
    """Every timed block as (type, start, end), day markers excluded."""
    res = []
    for it in out:
        tv = it.type.value if hasattr(it.type, "value") else str(it.type)
        if tv in ("day_start", "day_end"):
            continue
        res.append((tv, it.start_time, it.end_time))
    return res


def test_buffer_hop_gap_before_lunch_becomes_break_plus_hop():
    """J1 D2: Park Mamuta 12:25, buffer, hop, 5 min of nothing, lunch 12:51."""
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Park Mamuta", "11:10", "12:25", 75, lat=51.10, lng=17.05),
        _ft("12:25", "12:35", 10),
        _tr("Park Mamuta", "VaffaNapoli", "12:35", "12:46", km=1.0, dur=11),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="12:51", end_time="13:36", duration_min=45,
            suggestions=[], label="VaffaNapoli",
        ),
        DayEndItem(time="13:36"),
    ]
    out = _svc()._defragment_micro_blocks(items, _ctx(), day_num=2)
    between = [
        s for s in _spans(out)
        if "12:25" <= s[1] < "12:51"
    ]
    assert len(between) == 2, between
    assert between[0][0] == "free_time"
    assert between[1][0] == "transit"
    # nothing floats: break starts on the visit, hop lands on lunch
    assert between[0][1] == "12:25"
    assert between[0][2] == between[1][1]
    assert between[1][2] == "12:51"


def test_two_buffers_around_a_hop_collapse_to_one_break():
    """J9 D1: buffer, hop, buffer, then Hydropolis."""
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Pergola przy Hali Stulecia", "14:00", "14:54", 54,
              lat=51.107, lng=17.077),
        _ft("14:54", "15:04", 10),
        _tr("Pergola przy Hali Stulecia", "Hydropolis", "15:04", "15:14",
            km=1.4, dur=10),
        _ft("15:14", "15:24", 10, label="Popołudniowa przerwa"),
        _attr("Hydropolis", "15:24", "16:54", 90, lat=51.104, lng=17.056),
        DayEndItem(time="18:00"),
    ]
    out = _svc()._defragment_micro_blocks(items, _ctx(), day_num=1)
    fts = [it for it in out if it.type == ItemType.FREE_TIME]
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert len(fts) == 1
    assert len(hops) == 1
    assert fts[0].start_time == "14:54"
    assert fts[0].end_time == hops[0].start_time
    assert hops[0].end_time == "15:24"


def test_short_leftover_is_absorbed_by_the_hop():
    """J8 D1: 2 min walk then a 12 min buffer is just a 14 min approach."""
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Muzeum Świat Iluzji we Wrocławiu", "11:00", "12:02", 62,
              lat=51.110, lng=17.033),
        _tr("Muzeum Świat Iluzji we Wrocławiu", "Restauracja Česká",
            "12:02", "12:04", km=0.2, dur=2),
        _ft("12:04", "12:16", 12),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="12:16", end_time="12:56", duration_min=40,
            suggestions=[], label="Restauracja Česká",
        ),
        DayEndItem(time="12:56"),
    ]
    out = _svc()._defragment_micro_blocks(items, _ctx(), day_num=1)
    assert not [it for it in out if it.type == ItemType.FREE_TIME]
    hop = next(it for it in out if it.type == ItemType.TRANSIT)
    assert hop.start_time == "12:02"
    assert hop.end_time == "12:16"


def test_dinner_floor_keeps_its_slot_and_the_break_absorbs_the_wait():
    """J9 D1: dinner may not move to 17:15, so one break covers the wait."""
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Hydropolis", "15:24", "16:54", 90, lat=51.104, lng=17.056),
        _ft("16:54", "17:04", 10),
        _tr("Hydropolis", "The Cork", "17:04", "17:15", km=1.2, dur=11),
        _ft("17:15", "17:25", 10),
        DinnerBreakItem.model_construct(
            type=ItemType.DINNER_BREAK,
            start_time="17:30", end_time="18:30", duration_min=60,
            suggestions=[], label="The Cork",
        ),
        DayEndItem(time="18:30"),
    ]
    out = _svc()._defragment_micro_blocks(items, _ctx(), day_num=1)
    dinner = next(it for it in out if it.type == ItemType.DINNER_BREAK)
    assert dinner.start_time == "17:30"
    hop = next(it for it in out if it.type == ItemType.TRANSIT)
    assert hop.end_time == "17:30"
    fts = [it for it in out if it.type == ItemType.FREE_TIME]
    assert len(fts) == 1
    assert fts[0].start_time == "16:54"
    assert fts[0].end_time == hop.start_time


def test_clean_day_is_left_untouched():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Hydropolis", "09:00", "09:20", km=2.4, dur=20,
            mode=TransitMode.CAR, src="estimated_road"),
        _attr("Hydropolis", "09:20", "11:00", 100, lat=51.104, lng=17.056),
        _tr("Hydropolis", "Most Tumski", "11:00", "11:20", km=1.6, dur=20),
        _attr("Most Tumski", "11:20", "12:00", 40, lat=51.114, lng=17.047),
        DayEndItem(time="12:00"),
    ]
    out = _svc()._defragment_micro_blocks(items, _ctx(), day_num=2)
    assert _spans(out) == _spans(items)


def test_long_afternoon_break_is_not_eaten_by_the_hop():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Rynek we Wrocławiu", "13:00", "15:18", 138,
              lat=51.110, lng=17.031),
        _ft("15:18", "15:28", 10),
        _tr("Rynek we Wrocławiu", "The Cork", "15:31", "15:33", km=0.2, dur=2),
        _ft("15:33", "15:48", 15),
        DinnerBreakItem.model_construct(
            type=ItemType.DINNER_BREAK,
            start_time="17:30", end_time="18:30", duration_min=60,
            suggestions=[], label="The Cork",
        ),
        DayEndItem(time="18:30"),
    ]
    out = _svc()._defragment_micro_blocks(items, _ctx(), day_num=2)
    fts = [it for it in out if it.type == ItemType.FREE_TIME]
    hop = next(it for it in out if it.type == ItemType.TRANSIT)
    assert len(fts) == 1
    assert int(fts[0].duration_min) == (
        time_to_minutes(hop.start_time) - time_to_minutes("15:18")
    )
    assert fts[0].start_time == "15:18"
    assert hop.end_time == "17:30"
    assert fts[0].end_time == hop.start_time
