"""FIX #299 — leftover logistics: hops, ghost to, parked car, FT, no closed inject."""
from __future__ import annotations

from datetime import date

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    FreeTimeItem,
    ItemType,
    LunchBreakItem,
    TransitItem,
    TransitMode,
)


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur=60, *, lat=52.406, lng=16.925, city="Poznań"):
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
        address=city,
        city=city,
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


def test_ghost_antrejka_retargets_to_cytadela():
    items = [
        _attr("Park Adama Mickiewicza", "10:00", "11:00", 60),
        _tr("Park Adama Mickiewicza", "Antrejka", "11:00", "11:15", km=1.2, dur=15),
        _attr("Park Cytadela", "11:15", "12:30", 75, lat=52.422, lng=16.936),
    ]
    out = _svc()._retarget_all_legs_to_next_stop(items, day_num=3)
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert hops
    assert "ytadel" in (hops[0].to_location or "")


def test_empty_lunch_does_not_steal_next_hop():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="13:00",
        end_time="14:00",
        duration_min=60,
        suggestions=[],
        location_context="centrum",
    )
    items = [
        _attr("Park Adama Mickiewicza", "11:00", "12:50", 110),
        _tr("Park Adama Mickiewicza", "Antrejka", "12:50", "13:00", km=0.8, dur=10),
        lunch,
        _attr("Park Cytadela", "14:00", "15:00", 60, lat=52.422, lng=16.936),
    ]
    out = _svc()._retarget_all_legs_to_next_stop(items, day_num=3)
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert hops
    assert "ytadel" in (hops[0].to_location or "")


def test_missing_hop_between_attractions_is_inserted():
    items = [
        _attr(
            "Jezioro Strzeszyńskie", "10:00", "11:00", 60,
            lat=52.458, lng=16.850,
        ),
        _attr(
            "Park Adama Wodziczki", "11:20", "12:00", 40,
            lat=52.455, lng=16.848,
        ),
    ]
    ctx = {"requested_city": "Poznań", "has_car": True}
    out = _svc()._ensure_stop_to_stop_legs(items, {}, ctx, day_num=3)
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert hops, "must insert a hop between consecutive attractions"


def test_solacki_lunch_cytadela_gets_hops():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="13:00",
        end_time="14:00",
        duration_min=60,
        suggestions=[],
        location_context="centrum",
    )
    items = [
        _attr("Park Sołacki", "11:00", "12:50", 110, lat=52.424, lng=16.905),
        lunch,
        _attr("Park Cytadela", "14:10", "15:30", 80, lat=52.422, lng=16.936),
    ]
    ctx = {"requested_city": "Poznań", "has_car": True}
    out = _svc()._ensure_stop_to_stop_legs(items, {}, ctx, day_num=2)
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert len(hops) >= 1


def test_166min_gap_is_named():
    items = [
        _attr("A", "10:00", "11:00", 60),
        _attr("B", "13:46", "15:00", 74),
    ]
    out = _svc()._fill_anonymous_midday_gaps(items, {}, day_num=5)
    fts = [it for it in out if it.type == ItemType.FREE_TIME]
    assert fts
    assert int(fts[0].duration_min) >= 90


def test_tiny_free_time_buffers_merge():
    ft1 = FreeTimeItem.model_construct(
        type=ItemType.FREE_TIME,
        start_time="15:00",
        end_time="15:12",
        duration_min=12,
        label="Bufor",
        suggestions=[],
    )
    ft2 = FreeTimeItem.model_construct(
        type=ItemType.FREE_TIME,
        start_time="15:15",
        end_time="15:28",
        duration_min=13,
        label="Przerwa",
        suggestions=[],
    )
    out = _svc()._merge_abutting_free_time_hard(
        [ft1, ft2], day_num=3, max_gap=8,
    )
    fts = [it for it in out if it.type == ItemType.FREE_TIME]
    assert len(fts) == 1
    assert int(fts[0].duration_min) >= 20


def test_hole_fill_does_not_plant_monday_closed_palmiarnia():
    items = [
        _attr("Stary Rynek", "10:00", "12:00", 120),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME,
            start_time="12:00",
            end_time="14:00",
            duration_min=120,
            label="Wolne",
            suggestions=[],
        ),
    ]
    pool = [{
        "id": "palm",
        "name": "Palmiarnia Poznańska",
        "city": "Poznań",
        "lat": 52.401,
        "lng": 16.899,
        "time_min": 60,
        "must_see": 8,
        "opening_hours_seasonal": [{
            "date_from": "01-01",
            "date_to": "12-31",
            "mon": "closed",
            "tue": "09:00-16:00",
            "wed": "09:00-16:00",
            "thu": "09:00-16:00",
            "fri": "09:00-16:00",
            "sat": "09:00-17:00",
            "sun": "09:00-17:00",
        }],
    }]
    ctx = {
        "requested_city": "Poznań",
        "date": date(2026, 2, 16),
        "season": "winter",
        "hole_fill": True,
        "city_holes_only": True,
        "num_days": 3,
        "current_day_num": 1,
    }
    user = {
        "target_group": "family_kids",
        "travel_style": "balanced",
        "preferences": ["kids_attractions", "nature_landscape"],
    }
    out = _svc()._inject_attraction_into_free_time(
        items, pool, ctx, user, day_num=1,
    )
    names = [getattr(it, "name", "") for it in out]
    assert not any("almiarnia" in n for n in names)


def test_walk_then_car_returns_to_parked_car():
    items = [
        _attr("Park Cytadela", "10:00", "11:00", 60, lat=52.422, lng=16.936),
        _tr(
            "Park Cytadela", "Muzeum Iluzji",
            "11:00", "11:22", km=1.5, dur=22,
            mode=TransitMode.WALK, src="estimated_walk",
        ),
        _attr("Muzeum Iluzji", "11:22", "12:22", 60, lat=52.408, lng=16.934),
        _tr(
            "Muzeum Iluzji", "Termy Maltańskie",
            "12:22", "12:40", km=5.0, dur=18,
            mode=TransitMode.CAR, src="estimated_road",
        ),
        _attr("Termy Maltańskie", "12:40", "14:40", 120, lat=52.404, lng=16.973),
    ]
    coords = {
        "Park Cytadela": {"lat": 52.422, "lng": 16.936},
        "Muzeum Iluzji": {"lat": 52.408, "lng": 16.934},
        "Termy Maltańskie": {"lat": 52.404, "lng": 16.973},
    }
    out = _svc()._enforce_car_parking_logistics(
        items, coords, {"has_car": True, "requested_city": "Poznań"}, day_num=1,
    )
    car_hops = [
        it for it in out
        if it.type == ItemType.TRANSIT
        and "car" in str(getattr(it.mode, "value", it.mode)).lower()
    ]
    assert car_hops
    assert "iluzji" not in (car_hops[0].from_location or "").lower()
