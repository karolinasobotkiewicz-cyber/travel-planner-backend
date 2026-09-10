"""FIX #325 — the hub label is not a stop, and a ride needs somewhere to go.

Root cause of every "bufor zamiast dojazdu" remark: "Wrocław" is 7 chars
and sits inside "ZOO Wrocław", so _place_names_match called the leading
hop a 0 km self-hop, FIX #309 dropped it and the hole came back named
"Krótka przerwa / bufor". No generate_plan here.
"""
from __future__ import annotations

from app.application.services.plan_service import (
    PlanService,
    _is_hub_place_label,
    _place_names_match,
)
from app.domain.models.plan import (
    AttractionItem,
    DayEndItem,
    DayStartItem,
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


def test_city_hub_does_not_swallow_a_poi_that_carries_its_name():
    assert not _place_names_match("Wrocław", "ZOO Wrocław")
    assert not _place_names_match("Wrocław", "Aquapark Wrocław")
    assert not _place_names_match("Wrocław", "Muzeum Narodowe we Wrocławiu")
    assert not _place_names_match("Wrocław", "Rynek we Wrocławiu")
    assert not _place_names_match("Wrocław", "Katedra Wrocławska")


def test_hub_labels_still_match_each_other():
    assert _place_names_match("Wrocław", "Wrocław centrum")
    assert _place_names_match("Wrocław centrum", "Wrocław")
    assert _is_hub_place_label("Wrocław")
    assert _is_hub_place_label("Wrocław centrum")
    assert not _is_hub_place_label("ZOO Wrocław")


def test_real_stop_names_still_match_loosely():
    assert _place_names_match("Pergola", "Pergola przy Hali Stulecia")
    assert _place_names_match("GAMARDŻOBA", "Gamardżoby")
    assert not _place_names_match("Wyspa Słodowa", "Most Tumski")


def test_leading_hop_to_zoo_survives_the_self_hop_strip():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "ZOO Wrocław", "09:00", "09:15", km=4.2, dur=15,
            mode=TransitMode.CAR, src="estimated_road"),
        _attr("ZOO Wrocław", "09:15", "12:00", 165, lat=51.105, lng=17.075),
        DayEndItem(time="12:00"),
    ]
    out = _svc()._drop_hops_not_to_next_stop(items, day_num=1)
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert hops, "Wrocław → ZOO Wrocław is a 4 km drive, not a self-hop"


def test_hop_to_a_stop_that_no_longer_exists_is_dropped():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="10:00"),
        _attr("Muzeum Świat Iluzji we Wrocławiu", "15:20", "16:05", 45,
              lat=51.110, lng=17.033),
        _tr("Muzeum Świat Iluzji we Wrocławiu", "Most Tumski",
            "17:16", "17:34", km=1.4, dur=18),
        DayEndItem(time="17:34"),
    ]
    out = _svc()._drop_hops_not_to_next_stop(items, day_num=1)
    assert not [it for it in out if it.type == ItemType.TRANSIT]


def test_return_leg_to_the_city_still_closes_the_day():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Rynek w Oławie", "10:00", "15:00", 300, lat=50.94, lng=17.29),
        _tr("Rynek w Oławie", "Wrocław centrum", "15:00", "15:40", km=28.0,
            dur=40, mode=TransitMode.CAR, src="estimated_road"),
        DayEndItem(time="15:40"),
    ]
    out = _svc()._drop_hops_not_to_next_stop(items, day_num=6)
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert hops, "the drive home is the point of a satellite day"


def test_lunch_that_cannot_move_is_left_alone():
    """Stretching a 27 min lunch to 30 min overlapped the next hop."""
    items = [
        DayStartItem(type=ItemType.DAY_START, time="10:00"),
        _attr("Hala Targowa", "13:42", "14:22", 40, lat=51.114, lng=17.041),
        _tr("Hala Targowa", "Warzywniak", "14:22", "14:40", km=1.2, dur=18),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="14:40", end_time="15:07", duration_min=27,
            suggestions=[], label="Warzywniak",
        ),
        _tr("Warzywniak", "Muzeum Świat Iluzji we Wrocławiu",
            "15:07", "15:20", km=1.0, dur=13),
        _attr("Muzeum Świat Iluzji we Wrocławiu", "15:20", "16:05", 45,
              lat=51.110, lng=17.033),
        DayEndItem(time="16:05"),
    ]
    out = _svc()._pull_lunch_hop_before_latest(items, {}, day_num=1)
    lunch = next(it for it in out if it.type == ItemType.LUNCH_BREAK)
    nxt = next(
        it for it in out
        if it.type == ItemType.TRANSIT and it.start_time == "15:07"
    )
    assert time_to_minutes(lunch.end_time) <= time_to_minutes(nxt.start_time)
