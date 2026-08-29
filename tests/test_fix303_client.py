"""FIX #303 — Wrocław leftover: day_end, clocks, micro-hops, winter Arboretum."""
from __future__ import annotations

from app.application.services.plan_service import PlanService
from app.domain.filters.seasonality import filter_by_season
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


def test_dinner_after_day_end_is_dropped():
    dinner = DinnerBreakItem.model_construct(
        type=ItemType.DINNER_BREAK,
        start_time="20:36",
        end_time="21:21",
        duration_min=45,
        suggestions=[],
    )
    items = [
        _attr("Loopy's World", "18:30", "20:00", 90, lat=51.10, lng=17.04),
        _tr("Loopy's World", "Kolacja", "20:00", "20:36", km=4.0, dur=36),
        dinner,
    ]
    out = _svc()._clamp_timeline_to_day_end(
        items, {"day_end": "19:00"}, day_num=3,
    )
    assert not any(it.type == ItemType.DINNER_BREAK for it in out)
    assert not any(
        it.type == ItemType.TRANSIT and (it.start_time or "") >= "19:10"
        for it in out
    )


def test_on_time_dinner_overrun_is_kept():
    dinner = DinnerBreakItem.model_construct(
        type=ItemType.DINNER_BREAK,
        start_time="18:30",
        end_time="19:20",
        duration_min=50,
        suggestions=[],
    )
    out = _svc()._clamp_timeline_to_day_end(
        [dinner], {"day_end": "19:00"}, day_num=1,
    )
    assert any(it.type == ItemType.DINNER_BREAK for it in out)


def test_clock_wins_over_stale_duration_min():
    items = [
        _tr("Hala Stulecia", "Sky Tower", "13:27", "13:37", km=2.0, dur=19),
    ]
    out = _svc()._sync_transit_duration_to_clock(items, day_num=4)
    assert int(out[0].duration_min) == 10
    assert out[0].start_time == "13:27"
    assert out[0].end_time == "13:37"


def test_short_walk_is_not_26_min():
    items = [
        _tr(
            "Wyspa Słodowa", "Między Mostami",
            "12:00", "12:26", km=0.471, dur=26,
            mode=TransitMode.WALK, src="estimated_walk",
        ),
    ]
    out = _svc()._force_short_city_hops_walk(items, day_num=2)
    assert int(out[0].duration_min) <= 12
    mode = str(getattr(out[0].mode, "value", out[0].mode) or "").lower()
    assert "walk" in mode


def test_318m_car_becomes_short_walk():
    items = [
        _tr(
            "Bernard", "Movie Gate",
            "16:00", "16:54", km=0.318, dur=54,
        ),
    ]
    out = _svc()._force_short_city_hops_walk(items, day_num=3)
    mode = str(getattr(out[0].mode, "value", out[0].mode) or "").lower()
    assert "walk" in mode
    assert int(out[0].duration_min) <= 10


def test_387km_walk_becomes_car():
    items = [
        _tr(
            "GoJump", "Movie Gate",
            "10:00", "10:10", km=3.87, dur=10,
            mode=TransitMode.WALK, src="estimated_road",
        ),
    ]
    out = _svc()._normalize_transit_mode_source(items, day_num=1)
    mode = str(getattr(out[0].mode, "value", out[0].mode) or "").lower()
    assert "walk" not in mode


def test_honest_19km_walk_untouched():
    items = [
        _tr(
            "Taste", "Hydropolis",
            "12:46", "13:22", km=1.9, dur=36,
            mode=TransitMode.WALK, src="estimated_walk",
        ),
    ]
    out = _svc()._normalize_transit_mode_source(items, day_num=1)
    mode = str(getattr(out[0].mode, "value", out[0].mode) or "").lower()
    assert "walk" in mode
    assert int(out[0].duration_min) == 36


def test_arboretum_closed_in_february():
    kept = filter_by_season(
        [
            {"name": "Arboretum Wojsławice"},
            {"name": "Dolina Tatarska"},
            {"name": "Rynek w Niemczy"},
        ],
        "2026-02-25",
    )
    names = " ".join(p["name"].lower() for p in kept)
    assert "arboretum" not in names
    assert "tatarska" in names or "rynek" in names


def test_ghost_hop_after_lunch_retargets_to_next_poi():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="13:00",
        end_time="14:00",
        duration_min=60,
        suggestions=[
            RestaurantSuggestion.model_construct(
                id="ida", name="IDA", lat=51.11, lng=17.03, city="Wrocław",
            )
        ],
    )
    items = [
        lunch,
        _tr("IDA", "Bastion Sakwowy", "14:00", "14:12", km=1.2, dur=12),
        _attr("Ogród Japoński", "14:20", "15:20", 60, lat=51.11, lng=17.08),
    ]
    out = _svc()._retarget_all_legs_to_next_stop(items, day_num=1)
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert hops
    assert "japoń" in (hops[0].to_location or "").lower() or "japon" in (
        hops[0].to_location or ""
    ).lower()


def test_eat_free_time_pulls_late_day_back():
    items = [
        _attr("Hydropolis", "10:00", "11:30", 90),
        FreeTimeItem(
            type=ItemType.FREE_TIME,
            start_time="11:30",
            end_time="12:35",
            duration_min=65,
            label="Czas dla siebie",
            suggestions=[],
        ),
        _attr("Hala Stulecia", "12:35", "19:27", 412, lat=51.107, lng=17.077),
    ]
    out = _svc()._eat_free_time_to_fit_day_end(
        items, {"day_end": "19:00"}, day_num=2,
    )
    last = max(
        time_to_m(getattr(it, "end_time", None))
        for it in out
        if getattr(it, "end_time", None)
    )
    assert last <= 19 * 60 + 8


def time_to_m(hhmm):
    from app.domain.planner.time_utils import time_to_minutes
    return time_to_minutes(hhmm)
