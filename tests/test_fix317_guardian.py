"""FIX #317 — guardian hop chain: stop-to-stop, physics, overlap-shift, holes.

Does not call generate_plan. Live JSON 1–10 is test_fix317_wroclaw_json.py.
"""
from __future__ import annotations

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    DayEndItem,
    DayStartItem,
    FreeTimeItem,
    ItemType,
    LunchBreakItem,
    RestaurantSuggestion,
    TransitItem,
    TransitMode,
)
from app.domain.planner.time_utils import time_to_minutes
from app.domain.validators.client_invariants import audit_day


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


def _sug(name, *, lat=51.11, lng=17.03):
    return RestaurantSuggestion.model_construct(
        id=f"id-{name}", name=name, lat=lat, lng=lng,
        city="Wrocław", address="",
    )


def _lunch(start, end, dur, sugs, label="Lunch / przerwa regeneracyjna"):
    return LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time=start, end_time=end, duration_min=dur,
        suggestions=sugs, label=label, location_context="",
    )


def _ctx(**extra):
    base = {
        "requested_city": "Wrocław",
        "has_car": True,
        "day_start": "09:00",
        "day_end": "19:00",
    }
    base.update(extra)
    return base


def _p0(items):
    return {
        d.code for d in audit_day(items, day=1, context=_ctx())
        if d.code in {
            "anonymous_gap", "missing_hop", "dishonest_leg",
            "urban_car", "overlap", "after_day_end",
        }
    }


def test_overlap_shifts_destination_instead_of_squeezing_hop():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Panorama Racławicka", "11:00", "12:00", 60,
              lat=51.110, lng=17.044),
        _tr("Panorama Racławicka", "Warzywniak", "11:59", "12:24",
            km=2.127, dur=25),
        _lunch("12:00", "12:45", 45, [_sug("Warzywniak")]),
        DayEndItem(time="12:45"),
    ]
    out = _svc()._remove_timeline_overlaps(items, 1)
    hops = [it for it in out if _item_is_transit(it)]
    assert hops
    hop = hops[0]
    assert int(hop.duration_min) >= 20
    lunch = next(it for it in out if getattr(it, "type", None) == ItemType.LUNCH_BREAK)
    hop_en = time_to_minutes(hop.end_time)
    lunch_st = time_to_minutes(lunch.start_time)
    assert lunch_st >= hop_en - 1


def test_seal_expands_one_minute_two_km_walk():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Panorama Racławicka", "11:00", "12:00", 60,
              lat=51.110, lng=17.044),
        _tr("Panorama Racławicka", "Warzywniak", "11:59", "12:00",
            km=2.127, dur=1),
        _lunch("12:00", "12:45", 45, [_sug("Warzywniak", lat=51.109, lng=17.032)]),
        DayEndItem(time="12:45"),
    ]
    out = _svc()._seal_client_hops_and_physics(items, _ctx(), day_num=1)
    hops = [
        it for it in out
        if _item_is_transit(it)
        and "warzywniak" in (getattr(it, "to_location", "") or "").lower()
    ]
    assert hops, "Panorama → Warzywniak hop must remain"
    hop = hops[0]
    clock = time_to_minutes(hop.end_time) - time_to_minutes(hop.start_time)
    assert max(int(hop.duration_min), clock) >= 20
    assert "dishonest_leg" not in _p0(out)
    assert "overlap" not in _p0(out)


def test_seal_inserts_hop_on_same_minute_teleport():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław", "Muzeum Przyrodnicze we Wrocławiu", "09:00", "09:20",
            km=1.5, dur=20),
        _attr("Muzeum Przyrodnicze we Wrocławiu", "09:20", "10:40", 80,
              lat=51.111, lng=17.047),
        _attr("GoJump", "10:40", "12:00", 80, lat=51.10, lng=17.08),
        DayEndItem(time="12:00"),
    ]
    out = _svc()._seal_client_hops_and_physics(items, _ctx(), day_num=1)
    assert "missing_hop" not in _p0(out)
    hops = [
        it for it in out
        if _item_is_transit(it)
        and "gojump" in (getattr(it, "to_location", "") or "").lower()
    ]
    assert hops, "Przyrodnicze → GoJump must get a hop"


def test_seal_downgrades_150m_car_to_walk():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Muzeum Pana Tadeusza", "10:00", "11:00", 60,
              lat=51.110, lng=17.032),
        _tr("Muzeum Pana Tadeusza", "Rynek we Wrocławiu", "11:00", "11:16",
            km=0.15, dur=16, mode=TransitMode.CAR, src="estimated_road"),
        _attr("Rynek we Wrocławiu", "11:16", "12:00", 44,
              lat=51.110, lng=17.031),
        DayEndItem(time="12:00"),
    ]
    out = _svc()._seal_client_hops_and_physics(items, _ctx(), day_num=2)
    assert "urban_car" not in _p0(out)


def test_seal_names_134min_anonymous_gap():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Pixel XL", "13:00", "14:30", 90, lat=51.09, lng=17.02),
        _tr("Pixel XL", "Restauracja Česká", "14:30", "14:59", km=2.0, dur=29),
        _lunch("14:59", "15:44", 45, [_sug("Restauracja Česká")]),
        _attr("Aquapark Wrocław", "17:13", "18:30", 77, lat=51.09, lng=17.01),
        DayEndItem(time="19:00"),
    ]
    out = _svc()._seal_client_hops_and_physics(items, _ctx(), day_num=3)
    assert "anonymous_gap" not in _p0(out)


def test_seal_adds_leading_hop_for_citypaintball():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("CityPaintball", "09:00", "10:30", 90, lat=51.085, lng=17.010),
        DayEndItem(time="10:30"),
    ]
    out = _svc()._seal_client_hops_and_physics(items, _ctx(), day_num=1)
    assert "missing_hop" not in _p0(out)
    hops = [it for it in out if _item_is_transit(it)]
    assert hops, "CityPaintball at day_start needs an approach hop"


def test_seal_meal_identity_loopy_vs_bernard():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Loopy's World", "10:00", "12:00", 120, lat=51.08, lng=17.05),
        _tr("Loopy's World", "Bernard", "12:00", "12:10", km=0.4, dur=10),
        _lunch(
            "12:10", "12:55", 45, [_sug("Bernard")],
            label="Bernard",
        ),
        _tr("Restauracja (obiad)", "Hydropolis", "12:55", "13:10",
            km=3.0, dur=15, mode=TransitMode.CAR, src="estimated_road"),
        _attr("Hydropolis", "13:10", "14:00", 50, lat=51.104, lng=17.056),
        DayEndItem(time="14:00"),
    ]
    lunch = items[3]
    lunch = lunch.model_copy(
        update={"location_context": "Park Rozrywki Loopy's World"},
    )
    items[3] = lunch
    out = _svc()._align_meal_identity(items, _ctx(), day_num=1)
    meal = next(
        it for it in out if getattr(it, "type", None) == ItemType.LUNCH_BREAK
    )
    assert "loopy" not in (meal.location_context or "").lower()
    assert "bernard" in (meal.label or "").lower()
    hops_after = [
        it for it in out
        if _item_is_transit(it)
        and "hydropolis" in (getattr(it, "to_location", "") or "").lower()
    ]
    assert hops_after
    assert "restauracja" not in (hops_after[0].from_location or "").lower()
    from app.domain.validators.client_invariants import audit_day
    codes = {d.code for d in audit_day(out, day=1, context=_ctx())}
    assert "meal_identity" not in codes


def test_seal_names_gap_before_evening_free_time():
    """JSON8 D6 leftover: attraction 15:24, unnamed 15:24–15:49, FT 15:49."""
    from app.domain.models.plan import FreeTimeItem

    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Rynek w Oławie", "13:54", "15:24", 90, lat=50.945, lng=17.293),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME,
            start_time="15:49", end_time="16:34", duration_min=45,
            label="Czas dla siebie", suggestions=[],
        ),
        DayEndItem(time="16:34"),
    ]
    out = _svc()._seal_client_hops_and_physics(items, _ctx(), day_num=6)
    assert "anonymous_gap" not in _p0(out)


def test_one_satellite_region_drops_later_brzeg():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Zamek w Ząbkowicach Śląskich", "10:00", "12:00", 120,
              lat=50.589, lng=16.810),
        _attr("Zamek Piastów Śląskich w Brzegu", "13:00", "14:30", 90,
              lat=50.861, lng=17.467),
        DayEndItem(time="14:30"),
    ]
    out = _svc()._keep_one_satellite_region(items, day_num=3)
    names = [
        (getattr(it, "name", "") or "").lower()
        for it in out if getattr(it, "type", None) == ItemType.ATTRACTION
    ]
    assert any("ząbkow" in n or "zabkow" in n for n in names)
    assert not any("brzeg" in n for n in names)
    assert "mixed_regions" not in {
        d.code for d in audit_day(out, day=3, context=_ctx())
    }


def test_empty_day_is_shortened_not_213min_free_time():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME,
            start_time="09:00", end_time="12:00", duration_min=180,
            label="Czas dla siebie", suggestions=[],
        ),
        _lunch("12:00", "12:45", 45, [_sug("IDA")], label="IDA"),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME,
            start_time="12:45", end_time="16:18", duration_min=213,
            label="Czas dla siebie", suggestions=[],
        ),
        DayEndItem(time="16:18"),
    ]
    out = _svc()._close_empty_day_if_needed(items, _ctx(), day_num=7)
    fts = [
        it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME
    ]
    assert all(int(getattr(it, "duration_min", 0) or 0) < 60 for it in fts)
    assert any(
        getattr(it, "type", None) == ItemType.DAY_END
        or getattr(getattr(it, "type", None), "value", None) == "day_end"
        for it in out
    )


def _item_is_transit(it) -> bool:
    t = getattr(it, "type", None)
    return t == ItemType.TRANSIT or getattr(t, "value", t) == ItemType.TRANSIT.value
