"""FIX #306 — Warszawa leftover: hours, ghost hops, clocks, meal context."""
from __future__ import annotations

from types import SimpleNamespace

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    ItemType,
    LunchBreakItem,
    TransitItem,
    TransitMode,
)


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur=60, *, lat=52.23, lng=21.01):
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
        address="Warszawa",
        city="Warszawa",
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


def test_wilanow_sunday_after_1600_is_stripped():
    items = [
        _attr(
            "Muzeum Pałacu Króla Jana III w Wilanowie",
            "16:10", "17:40", 90,
        ),
    ]
    out = _svc()._strip_after_hours_museums(
        items, day_num=2, trip_date="2026-02-22",
    )
    assert not any("wilanow" in (it.name or "").lower() or "wilanów" in (it.name or "").lower() for it in out)


def test_powstanie_shifted_to_1000_opening():
    items = [
        _attr("Muzeum Powstania Warszawskiego", "09:00", "11:00", 120),
    ]
    out = _svc()._strip_after_hours_museums(
        items, day_num=1, trip_date="2026-02-20",
    )
    assert out
    assert out[0].start_time >= "10:00"


def test_stacja_muzeum_shifted_to_1000_opening():
    items = [
        _attr("Stacja Muzeum", "09:12", "10:17", 65),
    ]
    out = _svc()._strip_after_hours_museums(
        items, day_num=1, trip_date="2026-02-20",
    )
    assert out
    assert out[0].start_time >= "10:00"


def test_stary_dom_hop_retargets_to_zamek():
    items = [
        _attr("Warszawianka", "10:00", "11:35", 95),
        _tr("Warszawianka", "Stary Dom", "11:35", "11:40", km=2.0, dur=5),
        _attr("Zamek Królewski", "11:48", "13:00", 72, lat=52.248, lng=21.014),
    ]
    out = _svc()._retarget_all_legs_to_next_stop(items, day_num=1)
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert hops
    assert "zamek" in (hops[0].to_location or "").lower()


def test_archikatedra_not_two_days_in_a_row():
    days = [
        SimpleNamespace(day=1, items=[
            _attr("Bazylika Archikatedralna św. Jana Chrzciciela", "10:00", "11:00"),
        ]),
        SimpleNamespace(day=2, items=[
            _attr("Bazylika Archikatedralna św. Jana Chrzciciela", "12:00", "13:00"),
        ]),
    ]
    out = _svc()._strip_cross_day_trip_repeats(days)
    names = [
        getattr(it, "name", "")
        for d in out for it in (d.items or [])
        if it.type == ItemType.ATTRACTION
    ]
    assert sum("archikatedral" in n.lower() for n in names) == 1


def test_powstanie_not_repeated_next_day():
    days = [
        SimpleNamespace(day=1, items=[
            _attr("Muzeum Powstania Warszawskiego", "10:00", "12:00"),
        ]),
        SimpleNamespace(day=2, items=[
            _attr("Muzeum Powstania Warszawskiego", "12:25", "14:10"),
        ]),
    ]
    out = _svc()._strip_cross_day_trip_repeats(days)
    names = [
        getattr(it, "name", "")
        for d in out for it in (d.items or [])
        if it.type == ItemType.ATTRACTION
    ]
    assert sum("powstania" in n.lower() for n in names) == 1


def test_ogrod_na_dachu_unique_across_days():
    days = [
        SimpleNamespace(day=6, items=[
            _attr("Ogród na dachu Biblioteki Uniwersyteckiej", "15:00", "16:00"),
        ]),
        SimpleNamespace(day=7, items=[
            _attr("Ogród na dachu Biblioteki Uniwersyteckiej", "11:00", "12:00"),
        ]),
    ]
    out = _svc()._strip_cross_day_trip_repeats(days)
    names = [
        getattr(it, "name", "")
        for d in out for it in (d.items or [])
        if it.type == ItemType.ATTRACTION
    ]
    assert sum("dachu" in n.lower() for n in names) == 1


def test_kampinos_return_12min_clock_is_expanded():
    items = [
        _tr(
            "Ścieżka Skrajem Puszczy", "Warszawa centrum",
            "15:09", "15:21", km=38.6, dur=45,
        ),
    ]
    out = _svc()._honest_transit_physics(items, day_num=5, context={"has_car": True})
    assert int(out[0].duration_min) >= 40
    assert out[0].end_time > "15:21"


def test_lunch_context_resets_after_return_to_warsaw():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="15:21",
        end_time="16:21",
        duration_min=60,
        suggestions=[],
        location_context='Ścieżka „Skrajem Puszczy”',
    )
    items = [
        _attr("Ścieżka Skrajem Puszczy", "13:00", "15:00", 120),
        _tr("Ścieżka Skrajem Puszczy", "Warszawa centrum", "15:09", "15:21", km=38.6, dur=45),
        lunch,
    ]
    out = _svc()._reset_stale_meal_location_context(items, day_num=5)
    meal = next(it for it in out if it.type == ItemType.LUNCH_BREAK)
    ctx = (getattr(meal, "location_context", "") or "").lower()
    assert "skrajem" not in ctx
    assert "warszawa" in ctx or "centrum" in ctx


def test_217km_walk_10min_is_slowed():
    items = [
        _tr(
            "Ogrody Zamku Królewskiego", "Tutti Santi",
            "13:00", "13:10", km=2.17, dur=10,
            mode=TransitMode.WALK, src="estimated_road",
        ),
    ]
    out = _svc()._honest_transit_physics(items, day_num=1, context={"has_car": True})
    assert int(out[0].duration_min) >= 18


def test_haversine_walk_becomes_estimated_walk():
    items = [
        _tr(
            "Warszawa", "Stare Miasto",
            "09:00", "09:15", km=0.966, dur=15,
            mode=TransitMode.WALK, src="haversine",
        ),
    ]
    out = _svc()._honest_transit_physics(items, day_num=1, context={"has_car": True})
    assert "walk" in str(out[0].routing_source or "").lower()
    assert "haversine" not in str(out[0].routing_source or "").lower()


def test_saski_hop_does_not_start_during_visit():
    items = [
        _attr("Ogród Saski", "13:24", "14:14", 50),
        _tr(
            "Ogród Saski", "Primitivo",
            "14:00", "14:10", km=0.8, dur=10,
            mode=TransitMode.WALK, src="haversine",
        ),
    ]
    out = _svc()._snap_transits_to_previous_stop_end(items, day_num=2)
    hop = next(it for it in out if it.type == ItemType.TRANSIT)
    assert hop.start_time >= "14:14"
