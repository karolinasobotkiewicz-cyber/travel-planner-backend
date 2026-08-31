"""FIX #309 — Kraków leftover: clocks, first hops, hours, uniqueness, profile."""
from __future__ import annotations

from types import SimpleNamespace

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    DayStartItem,
    ItemType,
    LunchBreakItem,
    RestaurantSuggestion,
    TransitItem,
    TransitMode,
)
from app.domain.scoring.profile_poi_rules import (
    poi_trip_repeat_key,
    should_deny_poi_for_profile,
)


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur=60, *, lat=50.065, lng=19.945):
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
        address="Kraków",
        city="Kraków",
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


def _ctx(**extra):
    base = {
        "requested_city": "Kraków",
        "has_car": True,
        "day_start": "09:00",
        "day_end": "19:00",
    }
    base.update(extra)
    return base


def test_duration_30_vs_clock_5_expands_clock():
    items = [
        _tr(
            "Kopiec Piłsudskiego", "Pixel XL",
            "13:55", "14:00", km=8.5, dur=30,
        ),
    ]
    out = _svc()._honest_transit_physics(items, day_num=1, context={"has_car": True})
    assert int(out[0].duration_min) >= 25
    assert out[0].end_time > "14:00"


def test_zakrzowek_5min_clock_expands():
    items = [
        _tr(
            "Zakrzówek", "Wioski Świata",
            "13:10", "13:15", km=1.195, dur=18,
            mode=TransitMode.WALK, src="estimated_walk",
        ),
    ]
    out = _svc()._honest_transit_physics(items, day_num=3, context={"has_car": True})
    assert out[0].end_time > "13:15"
    assert int(out[0].duration_min) >= 12


def test_micro_walk_15min_is_shortened():
    items = [
        _tr(
            "Muzeum Obwarzanka", "Royal Curry",
            "12:00", "12:15", km=0.191, dur=15,
            mode=TransitMode.WALK, src="estimated_walk",
        ),
    ]
    out = _svc()._honest_transit_physics(items, day_num=2, context={"has_car": True})
    assert int(out[0].duration_min) <= 8


def test_09km_walk_8min_is_slowed():
    items = [
        _tr(
            "Plac Bohaterów Getta", "Restauracja Polska",
            "13:00", "13:08", km=0.914, dur=8,
            mode=TransitMode.WALK, src="haversine",
        ),
    ]
    out = _svc()._honest_transit_physics(items, day_num=2, context={"has_car": True})
    assert int(out[0].duration_min) >= 12
    assert "haversine" not in str(out[0].routing_source or "").lower()


def test_walk_estimated_road_becomes_estimated_walk():
    items = [
        _tr(
            "Muzeum Obwarzanka", "Muzeum Narodowe",
            "11:00", "11:10", km=2.034, dur=10,
            mode=TransitMode.WALK, src="estimated_road",
        ),
    ]
    out = _svc()._honest_transit_physics(items, day_num=1, context={"has_car": True})
    assert out[0].mode == TransitMode.WALK
    assert "walk" in str(out[0].routing_source or "").lower()
    assert int(out[0].duration_min) >= 18


def test_lotnictwa_gets_leading_hop():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION,
            poi_id="lot",
            name="Muzeum Lotnictwa Polskiego",
            description_short="",
            start_time="09:00",
            end_time="11:00",
            duration_min=120,
            lat=0,
            lng=0,
            address="Kraków",
            city="Kraków",
            cost_estimate=0,
        ),
    ]
    out = _svc()._ensure_leading_transit(items, {}, _ctx(), day_num=2)
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert hops
    assert "lotnictw" in (hops[0].to_location or "").lower()


def test_gojump_gets_leading_hop():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("GOjump Park Trampolin Mateczny", "09:00", "10:30", 90, lat=50.0385, lng=19.9380),
    ]
    out = _svc()._ensure_leading_transit(items, {}, _ctx(), day_num=1)
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert hops


def test_narodowe_past_1800_is_clipped_or_stripped():
    items = [
        _attr("Muzeum Narodowe w Krakowie", "17:40", "19:10", 90),
    ]
    out = _svc()._strip_after_hours_museums(
        items, day_num=2, trip_date="2026-06-01",
    )
    assert not any("narodowe" in (it.name or "").lower() for it in out)


def test_archeologiczne_shifted_to_1000():
    items = [
        _attr("Muzeum Archeologiczne w Krakowie", "09:26", "10:56", 90),
    ]
    out = _svc()._strip_after_hours_museums(
        items, day_num=7, trip_date="2026-06-01",
    )
    assert out
    assert out[0].start_time >= "10:00"


def test_motyl_unique_across_days():
    days = [
        SimpleNamespace(day=1, items=[_attr("Muzeum Żywego Motyla", "15:00", "16:00")]),
        SimpleNamespace(day=2, items=[_attr("Muzeum Żywego Motyla", "11:00", "12:00")]),
    ]
    out = _svc()._strip_cross_day_trip_repeats(days)
    names = [
        getattr(it, "name", "")
        for d in out for it in (d.items or [])
        if getattr(it, "type", None) == ItemType.ATTRACTION
    ]
    assert sum("motyl" in n.lower() for n in names) == 1


def test_botaniczny_uj_unique_across_days():
    assert poi_trip_repeat_key("Ogród Botaniczny UJ") == "krk_botaniczny"
    days = [
        SimpleNamespace(day=4, items=[_attr("Ogród Botaniczny UJ", "11:00", "12:00")]),
        SimpleNamespace(day=7, items=[_attr("Ogród Botaniczny UJ", "10:00", "11:00")]),
    ]
    out = _svc()._strip_cross_day_trip_repeats(days)
    names = [
        getattr(it, "name", "")
        for d in out for it in (d.items or [])
        if getattr(it, "type", None) == ItemType.ATTRACTION
    ]
    assert sum("botanicz" in n.lower() for n in names) == 1


def test_motyl_denied_for_underground_adventure():
    poi = {"name": "Muzeum Żywego Motyla", "city": "Kraków"}
    user = {
        "target_group": "friends",
        "travel_style": "adventure",
        "preferences": ["underground", "history_mystery", "museum_heritage"],
    }
    assert should_deny_poi_for_profile(poi, user) is True


def test_ghost_barbakan_hop_retargets_to_planty():
    items = [
        _attr("Błonia Krakowskie", "14:00", "15:11", 71),
        _tr("Błonia Krakowskie", "Barbakan", "15:11", "15:20", km=2.0, dur=9),
        _attr("Planty Krakowskie", "15:21", "16:36", 75),
    ]
    out = _svc()._retarget_all_legs_to_next_stop(items, day_num=1)
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert hops
    assert "planty" in (hops[0].to_location or "").lower()


def test_wawel_hop_retargets_to_nolio_lunch():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="12:49",
        end_time="13:34",
        duration_min=45,
        suggestions=[
            RestaurantSuggestion.model_construct(
                id="nolio", name="Restauracja Nolio", lat=50.064, lng=19.940,
            )
        ],
        location_context="Ogród Botaniczny",
    )
    items = [
        _attr("Wawel", "11:00", "12:39", 99),
        _tr("Wawel", "Ogród Botaniczny", "12:39", "12:49", km=2.0, dur=10),
        lunch,
    ]
    out = _svc()._retarget_all_legs_to_next_stop(items, day_num=1)
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert hops
    assert "nolio" in (hops[0].to_location or "").lower()


def test_lunch_context_follows_pixel_xl():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="14:00",
        end_time="14:45",
        duration_min=45,
        suggestions=[],
        location_context="Kopiec Józefa Piłsudskiego",
    )
    items = [
        _attr("Kopiec Józefa Piłsudskiego", "12:00", "13:55", 115),
        _tr("Kopiec Józefa Piłsudskiego", "Pixel XL", "13:55", "14:00", km=8.5, dur=30),
        lunch,
    ]
    out = _svc()._reset_stale_meal_location_context(items, day_num=1)
    meal = next(it for it in out if it.type == ItemType.LUNCH_BREAK)
    ctx = (getattr(meal, "location_context", "") or "").lower()
    assert "kopiec" not in ctx
    assert "pixel" in ctx


def test_self_hop_restaurant_is_dropped():
    items = [
        _tr(
            "Restauracja Pod Bocianem", "Restauracja Pod Bocianem",
            "15:03", "15:17", km=0.0, dur=14,
            mode=TransitMode.WALK, src="estimated_walk",
        ),
    ]
    out = _svc()._drop_hops_not_to_next_stop(items, day_num=6)
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert not hops


def test_skalki_266min_is_capped():
    items = [
        _attr("Skałki Twardowskiego", "10:00", "14:26", 266),
    ]
    out = _svc()._cap_stretched_attraction_durations(
        items, day_num=3, user={"target_group": "friends"},
    )
    assert out
    assert int(out[0].duration_min) <= 90


def test_kopiec_krakusa_163min_is_capped():
    items = [
        _attr("Kopiec Krakusa", "11:00", "13:43", 163),
    ]
    out = _svc()._cap_stretched_attraction_durations(
        items, day_num=2, user={"target_group": "friends"},
    )
    assert out
    assert int(out[0].duration_min) <= 60


def test_50min_hole_after_katedra_is_named():
    items = [
        _attr("Katedra Wawelska", "09:00", "09:40", 40),
        _tr("Katedra Wawelska", "Zamek Wawelski", "10:30", "10:40", km=0.3, dur=10,
            mode=TransitMode.WALK, src="estimated_walk"),
        _attr("Zamek Wawelski", "10:40", "12:10", 90),
    ]
    out = _svc()._name_remaining_holes(items, _ctx(), day_num=3)
    named = [it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME]
    assert named
