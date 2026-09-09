"""FIX #320 — lunch always, eat 20–60 min FT, morning outdoor pull.

Does not call generate_plan. Hala 10:00 stays in test_fix305_client.py.
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


def _ft(start, end, dur, label="Czas dla siebie"):
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


def _lunch(start, end, dur=40):
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
        "day_end": "16:00",
    }
    base.update(extra)
    return base


def test_55min_ft_before_dinner_is_eaten():
    items = [
        _attr("Warzywniak", "15:10", "16:05", 55, lat=51.109, lng=17.032),
        _ft("16:05", "17:00", 55),
        _dinner("17:00", "17:45"),
    ]
    out = _svc()._eat_long_free_time_before_attraction(
        items, day_num=2, min_ft=20, keep=10, pull_lunch=True,
        skip_first_attraction=True,
    )
    fts = [it for it in out if it.type == ItemType.FREE_TIME]
    assert fts
    assert int(fts[0].duration_min) <= 15
    dinners = [it for it in out if it.type == ItemType.DINNER_BREAK]
    assert dinners
    assert dinners[0].start_time <= "16:30"


def test_60min_after_hala_before_lunch_is_eaten():
    items = [
        _attr("Hala Stulecia", "10:00", "11:00", 60, lat=51.107, lng=17.077),
        _ft("11:00", "12:00", 60),
        _lunch("12:00", "12:40"),
    ]
    out = _svc()._eat_long_free_time_before_attraction(
        items, day_num=1, min_ft=20, keep=10, pull_lunch=True,
        skip_first_attraction=True,
    )
    fts = [it for it in out if it.type == ItemType.FREE_TIME]
    assert fts
    assert int(fts[0].duration_min) <= 15
    lunches = [it for it in out if it.type == ItemType.LUNCH_BREAK]
    assert lunches
    assert lunches[0].start_time <= "11:30"


def test_20min_crumbs_before_iluzja_are_eaten():
    items = [
        _attr("Hydropolis", "13:00", "14:00", 60, lat=51.104, lng=17.056),
        _ft("14:00", "14:20", 20),
        _tr("Hydropolis", "Muzeum Świat Iluzji", "14:20", "14:37", km=2.0, dur=17),
        _ft("14:37", "14:57", 20),
        _attr("Muzeum Świat Iluzji we Wrocławiu", "14:57", "15:42", 45,
              lat=51.109, lng=17.032),
    ]
    out = _svc()._eat_long_free_time_before_attraction(
        items, day_num=4, min_ft=20, keep=10, pull_lunch=True,
        skip_first_attraction=True,
    )
    iluzja = next(
        it for it in out
        if "iluzj" in (getattr(it, "name", "") or "").lower()
    )
    assert iluzja.start_time < "14:57"
    long_ft = [
        it for it in out
        if it.type == ItemType.FREE_TIME and int(it.duration_min) >= 20
    ]
    assert not long_ft


def test_lunch_on_short_family_window():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="10:00"),
        _attr("Hydropolis", "10:00", "11:40", 100, lat=51.104, lng=17.056),
        _attr("Kolejkowo", "11:50", "13:00", 70, lat=51.107, lng=17.077),
        DayEndItem(time="16:00"),
    ]
    out = _svc()._guarantee_lunch_slot(
        items, _ctx(day_start="10:00", day_end="16:00"), day_num=2,
    )
    lunches = [it for it in out if it.type == ItemType.LUNCH_BREAK]
    assert lunches, "10:00–16:00 family day must get lunch"


def test_outdoor_morning_idle_is_pulled():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _ft("09:00", "09:43", 43),
        _attr("Ostrów Tumski", "09:43", "10:40", 57, lat=51.114, lng=17.047),
        _lunch("12:00", "12:40"),
        DayEndItem(time="16:00"),
    ]
    out = _svc()._pull_day_forward_to_start(
        items, _ctx(day_start="09:00", day_end="18:00"), day_num=2,
    )
    first = next(it for it in out if it.type == ItemType.ATTRACTION)
    assert first.start_time <= "09:20"
    lunch = next(it for it in out if it.type == ItemType.LUNCH_BREAK)
    assert lunch.start_time == "12:00"


def test_hala_stays_at_1000_after_morning_pull():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _ft("09:00", "10:00", 60, label="Spokojny poranek"),
        _attr("Hala Stulecia", "10:00", "11:00", 60, lat=51.107, lng=17.077),
        DayEndItem(time="16:00"),
    ]
    out = _svc()._pull_day_forward_to_start(
        items, _ctx(day_start="09:00", day_end="18:00"), day_num=1,
    )
    hala = next(it for it in out if it.type == ItemType.ATTRACTION)
    assert hala.start_time == "10:00"


def test_3h_afternoon_ft_keeps_dinner_at_1730():
    items = [
        _attr("Hydropolis", "13:00", "14:30", 90, lat=51.104, lng=17.056),
        _ft("14:30", "17:30", 180),
        _dinner("17:30", "18:15"),
    ]
    out = _svc()._eat_long_free_time_before_attraction(
        items, day_num=2, min_ft=20, keep=10, pull_lunch=True,
        skip_first_attraction=True,
    )
    dinners = [it for it in out if it.type == ItemType.DINNER_BREAK]
    assert dinners
    assert dinners[0].start_time >= "17:30"
