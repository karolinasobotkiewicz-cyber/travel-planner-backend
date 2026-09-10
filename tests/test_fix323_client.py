"""FIX #323 — first hop instead of morning buffer, long FT, thin Topacz.

Does not call generate_plan.
"""
from __future__ import annotations

from app.application.services.plan_service import (
    PlanService,
    _fix_late_lunch,
    _item_clock_floor_min,
)
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
        "day_start": "09:30",
        "day_end": "18:00",
    }
    base.update(extra)
    return base


def test_morning_buffer_before_botanic_becomes_a_hop():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:30"),
        _ft("09:30", "10:00", 30),
        _attr("Ogród Botaniczny Uniwersytetu Wrocławskiego", "10:00", "11:00", 60),
        DayEndItem(time="16:00"),
    ]
    out = _svc()._seal_first_approach(items, _ctx(), coord_map={}, day_num=1)
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert hops, "09:30 buffer then Botanic at 10:00 must become a first hop"
    assert "botanic" in (hops[0].to_location or "").lower() or "ogród" in (
        hops[0].to_location or ""
    ).lower() or "ogrod" in (hops[0].to_location or "").lower()
    botanic = next(it for it in out if it.type == ItemType.ATTRACTION)
    hop_end = hops[0].end_time
    assert hop_end <= botanic.start_time


def test_cap_drops_items_past_window():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="10:00"),
        _attr("Galeria Neon Side", "19:32", "20:22", 50, lat=51.11, lng=17.03),
        _tr("Galeria Neon Side", "Most Tumski", "20:22", "20:39", km=1.0, dur=17),
        _attr("Most Tumski", "20:48", "21:08", 20, lat=51.115, lng=17.042),
        _tr("Most Tumski", "The Cork", "21:09", "21:22", km=0.8, dur=13),
        DinnerBreakItem.model_construct(
            type=ItemType.DINNER_BREAK,
            start_time="21:28",
            end_time="22:00",
            duration_min=32,
            suggestions=[],
            label="The Cork",
        ),
        DayEndItem(time="20:50"),
    ]
    out = _svc()._cap_timeline_to_window(
        items, _ctx(day_end="20:00"), day_num=1,
    )
    names = " ".join(
        (getattr(it, "name", "") or getattr(it, "label", "") or "").lower()
        for it in out
    )
    assert "tumski" not in names
    assert "cork" not in names
    marker = next(it for it in out if it.type == ItemType.DAY_END)
    assert time_to_minutes(marker.time) <= 20 * 60
    neon = next(it for it in out if it.type == ItemType.ATTRACTION)
    assert time_to_minutes(neon.start_time) < 20 * 60
    assert time_to_minutes(neon.end_time) <= 20 * 60


def test_rynek_eight_minutes_after_start_gets_a_hop():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr(
            "Rynek we Wrocławiu", "09:08", "10:10", 62,
            lat=51.1107, lng=17.0324,
        ),
        DayEndItem(time="16:00"),
    ]
    out = _svc()._seal_first_approach(
        items, _ctx(day_start="09:00"), coord_map={}, day_num=2,
    )
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert hops, "Rynek at 09:08 is not a courtyard teleport"


def test_glued_rynek_at_day_start_stays_courtyard():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr(
            "Rynek we Wrocławiu", "09:00", "10:00", 60,
            lat=51.1079, lng=17.0385,
        ),
        DayEndItem(time="16:00"),
    ]
    out = _svc()._ensure_leading_transit(items, {}, _ctx(day_start="09:00"), day_num=1)
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert not hops


def test_outdoor_floor_is_day_start_not_1000():
    ostrow = _attr("Ostrów Tumski", "09:43", "10:40", 57, lat=51.114, lng=17.047)
    assert _item_clock_floor_min(ostrow, 9 * 60) == 9 * 60
    zaj = _attr("Zajezdnia", "10:00", "11:30", 90, lat=51.094, lng=17.021)
    assert _item_clock_floor_min(zaj, 9 * 60) == 10 * 60


def test_lonely_topacz_60min_is_thin():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:30"),
        _tr(
            "Wrocław", "Muzeum Motoryzacji i Techniki Zamek Topacz",
            "09:30", "10:07", km=18.0, dur=25, mode=TransitMode.CAR,
            src="estimated_road",
        ),
        _attr(
            "Muzeum Motoryzacji i Techniki Zamek Topacz",
            "10:07", "11:07", 60, lat=51.02, lng=16.95,
        ),
        DayEndItem(time="12:31"),
    ]
    out = _svc()._complete_thin_daytrip(items, [], _ctx(), {}, day_num=3)
    names = " ".join(
        (getattr(it, "name", "") or "").lower()
        for it in out if it.type == ItemType.ATTRACTION
    )
    assert "topacz" not in names


def test_seniors_lunch_1448_moves_before_1430():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="10:00"),
        _attr(
            "Muzeum Uniwersytetu Wrocławskiego", "10:11", "12:00", 109,
            lat=51.114, lng=17.034,
        ),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="14:48",
            end_time="15:28",
            duration_min=40,
            suggestions=[],
            label="Lunch",
        ),
        DayEndItem(time="16:00"),
    ]
    user = {"target_group": "seniors"}
    svc = _svc()
    out = svc._resit_late_lunch_after_morning_stop(items, user, day_num=2)
    out = _fix_late_lunch(out, latest_min=14 * 60 + 30)
    lunch = next(it for it in out if it.type == ItemType.LUNCH_BREAK)
    assert time_to_minutes(lunch.start_time) <= 14 * 60 + 30


def test_lunch_hop_does_not_push_seniors_past_1430():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="10:00"),
        _attr(
            "Muzeum Przyrodnicze we Wrocławiu", "13:06", "14:30", 84,
            lat=51.111, lng=17.047,
        ),
        _tr(
            "Muzeum Przyrodnicze we Wrocławiu",
            "Le Barometre Bistro & Cocktail Bar",
            "14:30", "14:47", km=1.15, dur=17,
        ),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="14:47",
            end_time="15:15",
            duration_min=28,
            suggestions=[],
            label="Le Barometre Bistro & Cocktail Bar",
        ),
        DayEndItem(time="18:00"),
    ]
    out = _svc()._pull_lunch_hop_before_latest(
        items, {"target_group": "seniors"}, day_num=2,
    )
    lunch = next(it for it in out if it.type == ItemType.LUNCH_BREAK)
    assert time_to_minutes(lunch.start_time) <= 14 * 60 + 30
    museum = next(it for it in out if it.type == ItemType.ATTRACTION)
    hop = next(it for it in out if it.type == ItemType.TRANSIT)
    assert hop.end_time <= lunch.start_time
    assert museum.end_time <= hop.start_time
    assert time_to_minutes(museum.end_time) - time_to_minutes(museum.start_time) >= 40
    items = [
        DayStartItem(type=ItemType.DAY_START, time="10:00"),
        _attr(
            "Muzeum Uniwersytetu Wrocławskiego", "10:11", "12:00", 109,
            lat=51.114, lng=17.034,
        ),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="14:48",
            end_time="15:28",
            duration_min=40,
            suggestions=[],
            label="Lunch",
        ),
        DayEndItem(time="16:00"),
    ]
    user = {"target_group": "seniors"}
    svc = _svc()
    out = svc._resit_late_lunch_after_morning_stop(items, user, day_num=2)
    out = _fix_late_lunch(out, latest_min=14 * 60 + 30)
    lunch = next(it for it in out if it.type == ItemType.LUNCH_BREAK)
    assert time_to_minutes(lunch.start_time) <= 14 * 60 + 30


def test_named_lunch_label_gets_hop_instead_of_next_attraction():
    """JSON6 D2: Muzeum → Most hop while lunch is Le Barometre by label."""
    items = [
        DayStartItem(type=ItemType.DAY_START, time="10:00"),
        _attr(
            "Muzeum Przyrodnicze we Wrocławiu", "13:06", "14:30", 84,
            lat=51.111, lng=17.047,
        ),
        _tr(
            "Muzeum Przyrodnicze we Wrocławiu", "Most Tumski",
            "14:30", "14:37", km=0.8, dur=7,
        ),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="14:42",
            end_time="15:10",
            duration_min=28,
            suggestions=[],
            label="Le Barometre Bistro & Cocktail Bar",
        ),
        _tr(
            "Le Barometre Bistro & Cocktail Bar", "Most Tumski",
            "15:10", "15:22", km=0.6, dur=12,
        ),
        _attr("Most Tumski", "15:22", "15:42", 20, lat=51.115, lng=17.042),
        DayEndItem(time="18:00"),
    ]
    svc = _svc()
    items = svc._drop_hops_not_to_next_stop(items, day_num=2)
    items = svc._ensure_stop_to_stop_legs(items, {}, _ctx(day_start="10:00"), day_num=2)
    hops_after_museum = []
    lunch_seen = False
    for it in items:
        if it.type == ItemType.LUNCH_BREAK:
            lunch_seen = True
            continue
        if lunch_seen:
            break
        if it.type == ItemType.TRANSIT:
            hops_after_museum.append(it.to_location or "")
    assert hops_after_museum, "Muzeum must hop to the named lunch"
    assert any("barometre" in (h or "").lower() for h in hops_after_museum)
    assert not any("tumski" in (h or "").lower() for h in hops_after_museum)


def test_stacked_afternoon_ft_collapses_before_inject():
    items = [
        _attr("Park World", "13:00", "14:00", 60, lat=51.11, lng=17.03),
        _ft("14:00", "14:53", 53, label="Oddech"),
        _ft("14:53", "16:23", 90, label="Czas dla siebie"),
        _ft("16:23", "17:58", 95, label="Czas dla siebie"),
        DinnerBreakItem.model_construct(
            type=ItemType.DINNER_BREAK,
            start_time="17:58",
            end_time="18:40",
            duration_min=42,
            suggestions=[],
            label="Kolacja",
        ),
    ]
    out = _svc()._collapse_adjacent_free_time(items, day_num=3, force=True)
    fts = [it for it in out if it.type == ItemType.FREE_TIME]
    assert len(fts) == 1
    assert int(fts[0].duration_min) >= 230
