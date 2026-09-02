"""FIX #311 — hops keep location; lunch/dinner floors stick after pull."""
from __future__ import annotations

from types import SimpleNamespace

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    DayEndItem,
    DayStartItem,
    DinnerBreakItem,
    FreeTimeItem,
    ItemType,
    LunchBreakItem,
    RestaurantSuggestion,
    TransitItem,
    TransitMode,
)
from app.domain.scoring.profile_poi_rules import poi_trip_repeat_key


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur=60, *, lat=51.110, lng=17.032, city="Wrocław"):
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


def _sug(name, *, lat=51.110, lng=17.032, city="Wrocław", address=""):
    return RestaurantSuggestion.model_construct(
        id=f"id-{name}",
        name=name,
        lat=lat,
        lng=lng,
        city=city,
        address=address or city,
    )


def _lunch(start, end, dur, sugs, *, ctx="centrum"):
    return LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time=start,
        end_time=end,
        duration_min=dur,
        suggestions=sugs,
        location_context=ctx,
    )


def _dinner(start, end, dur, sugs, *, ctx="centrum"):
    return DinnerBreakItem.model_construct(
        type=ItemType.DINNER_BREAK,
        start_time=start,
        end_time=end,
        duration_min=dur,
        suggestions=sugs,
        location_context=ctx,
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


def _ctx(**extra):
    base = {
        "requested_city": "Wrocław",
        "has_car": True,
        "day_start": "09:00",
        "day_end": "19:00",
    }
    base.update(extra)
    return base


def test_hop_after_bernard_starts_from_bernard():
    items = [
        _attr("Muzeum Świat Iluzji", "09:00", "10:05"),
        _tr("Muzeum Świat Iluzji", "Bernard", "10:05", "10:12", km=0.4, dur=7,
            mode=TransitMode.WALK, src="estimated_walk"),
        _ft("10:12", "10:22", 10, "bufor"),
        _tr("Muzeum Świat Iluzji", "Hydropolis", "10:22", "10:34", km=1.2, dur=12),
        _attr("Hydropolis", "10:34", "11:30"),
    ]
    out = _svc()._retarget_all_legs_to_prev_stop(items, day_num=2, context=_ctx())
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert "bernard" in (hops[-1].from_location or "").lower()
    assert "iluzji" not in (hops[-1].from_location or "").lower()


def test_stacked_hala_hops_collapse_to_next_stop():
    items = [
        _attr("Hala Stulecia", "09:00", "10:10"),
        _tr("Hala Stulecia", "House of Spices", "10:10", "10:20", km=2.0, dur=10),
        _tr("Hala Stulecia", "Kwatera Główna", "10:20", "10:30", km=3.0, dur=10),
        _attr("Kwatera Główna Centrum Laser Tag", "10:30", "12:30",
              lat=51.090, lng=17.020),
    ]
    out = _svc()._seal_day_hops_and_meals(items, _ctx(), {}, {}, day_num=2)
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert hops
    froms = [h.from_location for h in hops]
    assert sum("hala" in (f or "").lower() for f in froms) <= 1


def test_zero_km_self_hop_is_dropped_and_real_leg_inserted():
    items = [
        _attr("Aula Leopoldina", "12:14", "13:14", lat=51.114, lng=17.034),
        _tr("Aula Leopoldina", "Aula Leopoldina", "13:14", "13:24", km=0.0, dur=10),
        _attr("Wyspa Słodowa", "13:24", "14:20", lat=51.116, lng=17.038),
    ]
    out = _svc()._seal_day_hops_and_meals(items, _ctx(), {}, {}, day_num=4)
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert hops
    assert not any(
        (h.from_location or "").lower() == (h.to_location or "").lower()
        and float(h.distance_km or 0) < 0.15
        for h in hops
    )
    assert any(
        "słodow" in (h.to_location or "").lower()
        or "slodow" in (h.to_location or "").lower()
        for h in hops
    )


def test_ghost_bastion_hop_retargets_to_japonski():
    items = [
        _lunch("13:00", "13:45", 45, [_sug("IDA")]),
        _tr("IDA", "Bastion Sakwowy", "13:45", "14:08", km=1.2, dur=23),
        _attr("Ogród Japoński", "14:08", "15:08", lat=51.1083, lng=17.0780),
    ]
    out = _svc()._seal_day_hops_and_meals(items, _ctx(), {}, {}, day_num=1)
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert hops
    assert any(
        "japoń" in (h.to_location or "").lower()
        or "japon" in (h.to_location or "").lower()
        for h in hops
    )


def test_lunch_at_0950_is_pushed_and_not_pulled_back():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:30"),
        _ft("09:30", "09:50", 20),
        _lunch("09:50", "10:40", 50, [_sug("Bernard")]),
        _ft("10:40", "12:20", 100, "poranna przerwa"),
        _attr("Arboretum Wojsławice", "12:20", "14:00", lat=50.725, lng=16.852),
        DayEndItem(time="18:00"),
    ]
    ctx = _ctx(day_start="09:30", day_end="18:00")
    sealed = _svc()._seal_day_hops_and_meals(items, ctx, {}, {}, day_num=5)
    meals = [it for it in sealed if getattr(it, "type", None) == ItemType.LUNCH_BREAK]
    assert meals
    assert meals[0].start_time >= "12:00"


def test_noon_lunch_is_not_pulled_to_0950():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:30"),
        _ft("09:30", "12:00", 150),
        _lunch("12:00", "12:50", 50, [_sug("Bernard")]),
        _attr("Hala Stulecia", "13:00", "14:00"),
        DayEndItem(time="18:00"),
    ]
    ctx = _ctx(day_start="09:30", day_end="18:00")
    pulled = _svc()._pull_next_stop_over_large_gaps(items, ctx, day_num=3)
    meals = [it for it in pulled if getattr(it, "type", None) == ItemType.LUNCH_BREAK]
    assert meals
    assert meals[0].start_time >= "12:00"


def test_dinner_20min_after_lunch_is_pushed_to_evening():
    items = [
        _attr("Pergola przy Hali Stulecia", "11:00", "13:20"),
        _lunch("13:27", "14:12", 45, [_sug("The Cork")]),
        _dinner("14:32", "15:12", 40, [_sug("The Cork")]),
    ]
    out = _svc()._separate_lunch_and_dinner(items, _ctx(), day_num=1)
    dinners = [it for it in out if getattr(it, "type", None) == ItemType.DINNER_BREAK]
    assert dinners
    assert dinners[0].start_time >= "17:30"


def test_eat_long_ft_does_not_pull_dinner_before_1730():
    items = [
        _lunch("13:00", "13:45", 45, [_sug("Konspira")]),
        _ft("13:45", "17:30", 225),
        _dinner("17:30", "18:15", 45, [_sug("The Cork")]),
    ]
    out = _svc()._eat_long_free_time_before_attraction(items, day_num=1)
    dinners = [it for it in out if getattr(it, "type", None) == ItemType.DINNER_BREAK]
    assert dinners
    assert dinners[0].start_time >= "17:30"


def test_loopys_and_kwatera_repeat_keys():
    assert poi_trip_repeat_key("Loopy's World") == "wro_loopys"
    assert poi_trip_repeat_key("Loopys World") == "wro_loopys"
    assert poi_trip_repeat_key("Kwatera Główna Centrum Laser Tag") == "wro_kwatera"


def test_iluzja_loopys_kwatera_unique_across_days():
    days = [
        SimpleNamespace(day=1, items=[
            _attr("Muzeum Świat Iluzji", "10:00", "11:00"),
            _attr("Loopy's World", "12:00", "13:00"),
            _attr("Kwatera Główna Centrum Laser Tag", "14:00", "15:30"),
        ]),
        SimpleNamespace(day=2, items=[
            _attr("Muzeum Świat Iluzji", "10:00", "11:00"),
            _attr("Loopy's World", "12:00", "13:00"),
            _attr("Kwatera Główna Centrum Laser Tag", "14:00", "15:30"),
        ]),
        SimpleNamespace(day=3, items=[
            _attr("Muzeum Iluzji", "11:00", "12:00"),
        ]),
    ]
    out = _svc()._strip_cross_day_trip_repeats(days)
    names = [
        getattr(it, "name", "")
        for d in out for it in (d.items or [])
        if getattr(it, "type", None) == ItemType.ATTRACTION
    ]
    assert sum("iluzj" in n.lower() for n in names) == 1
    assert sum("loopy" in n.lower() for n in names) == 1
    assert sum("kwatera" in n.lower() or "laser" in n.lower() for n in names) == 1


def test_botaniczny_before_open_is_shifted():
    items = [_attr("Ogród Botaniczny", "09:47", "10:47")]
    out = _svc()._strip_after_hours_museums(
        items, day_num=1, trip_date="2026-02-20",
    )
    assert out
    assert out[0].start_time >= "10:00"


def test_movie_gate_before_open_is_shifted():
    items = [_attr("Movie Gate", "09:20", "10:20")]
    out = _svc()._strip_after_hours_museums(
        items, day_num=1, trip_date="2026-02-20",
    )
    assert out
    assert out[0].start_time >= "10:00"


def test_pana_tadeusza_after_last_entry_is_stripped():
    items = [_attr("Muzeum Pana Tadeusza", "16:31", "18:01", 90)]
    out = _svc()._strip_after_hours_museums(
        items, day_num=2, trip_date="2026-02-20",
    )
    assert not any("tadeusz" in (it.name or "").lower() for it in out)


def test_83m_haversine_walk_is_relabeled_and_shortened():
    items = [
        _tr(
            "Rynek", "Chinkalnia", "18:00", "18:18",
            km=0.083, dur=18, mode=TransitMode.WALK, src="haversine",
        ),
    ]
    out = _svc()._honest_transit_physics(items, day_num=2, context={"has_car": True})
    assert out[0].mode == TransitMode.WALK
    assert "haversine" not in str(out[0].routing_source or "").lower()
    assert int(out[0].duration_min) <= 8


def test_60min_unnamed_gap_is_labelled():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Panorama Racławicka", "10:00", "10:30"),
        _attr("Hala Stulecia", "11:30", "12:30"),
        DayEndItem(time="19:00"),
    ]
    out = _svc()._name_remaining_holes(items, _ctx(), day_num=3)
    fts = [it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME]
    assert fts
    covered = any(
        getattr(it, "start_time", "") <= "10:35"
        and getattr(it, "end_time", "") >= "11:10"
        for it in fts
    )
    assert covered or len(fts) >= 2


def test_stamp_geometry_drops_haversine_on_walk():
    hop = _tr(
        "Hala Targowa", "Emily", "11:55", "12:02",
        km=0.386, dur=7, mode=TransitMode.WALK, src="haversine",
    )
    out = _svc()._stamp_straight_geometry(hop, 51.11, 17.03, 51.112, 17.035)
    assert "haversine" not in str(out.routing_source or "").lower()
    assert "walk" in str(out.routing_source or "").lower()


def test_normalize_routing_item_drops_haversine_after_attach(monkeypatch):
    hop = _tr(
        "Hala Targowa", "Emily", "11:55", "12:02",
        km=0.386, dur=7, mode=TransitMode.WALK, src="haversine",
    )
    hop = hop.model_copy(update={"lat": None})
    cmap = {
        "Hala Targowa": {"name": "Hala Targowa", "lat": 51.111, "lng": 17.032},
        "Emily": {"name": "Emily", "lat": 51.113, "lng": 17.035},
    }

    class _Route:
        profile = "foot-walking"
        distance_km = 0.386

        def to_transit_extras(self):
            return {
                "routing_source": "haversine",
                "distance_km": 0.386,
                "duration_min": 7,
                "geometry": [[17.032, 51.111], [17.035, 51.113]],
                "geometry_latlng": [[51.111, 17.032], [51.113, 17.035]],
            }

    monkeypatch.setattr(
        "app.infrastructure.routing.get_travel_route",
        lambda *a, **k: _Route(),
    )
    out = _svc()._normalize_transit_routing_item(hop, cmap, {"has_car": True})
    assert "haversine" not in str(out.routing_source or "").lower()
    assert "walk" in str(out.routing_source or "").lower()
    items = [
        _tr(
            "Movie Gate", "Katedra", "11:00", "11:28",
            km=1.939, dur=28, mode=TransitMode.WALK, src="estimated_road",
        ),
    ]
    out = _svc()._normalize_transit_mode_source(items, day_num=1)
    assert out[0].mode == TransitMode.WALK
    assert "walk" in str(out[0].routing_source or "").lower()
    out2 = _svc()._downgrade_short_urban_cars(out, _ctx(), day_num=1)
    assert out2[0].mode == TransitMode.WALK


def test_panorama_gets_leading_hop():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _ft("09:00", "09:30", 30),
        _attr("Panorama Racławicka", "09:30", "10:00", 30, lat=51.110, lng=17.044),
    ]
    out = _svc()._ensure_leading_transit(items, {}, _ctx(), day_num=3)
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert hops


def test_wojslawice_after_wroclaw_lunch_gets_a_drive():
    items = [
        _lunch("12:00", "12:40", 40, [_sug("Bernard", lat=51.110, lng=17.032)]),
        _attr("Arboretum Wojsławice", "12:40", "14:00", lat=50.725, lng=16.852),
    ]
    out = _svc()._ensure_city_to_far_after_meal(items, {}, _ctx(), day_num=5)
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert hops
    blob = " ".join(f"{h.from_location} {h.to_location}" for h in hops).lower()
    assert "wojsław" in blob or "wojslaw" in blob or "arboretum" in blob
