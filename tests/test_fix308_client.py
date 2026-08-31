"""FIX #308 — Katowice leftover: first hops, hours, uniqueness, profile."""
from __future__ import annotations

from types import SimpleNamespace

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    DayStartItem,
    FreeTimeItem,
    ItemType,
    LunchBreakItem,
    TransitItem,
    TransitMode,
)
from app.domain.scoring.profile_poi_rules import should_deny_poi_for_profile


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur=60, *, lat=50.265, lng=19.024):
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
        address="Katowice",
        city="Katowice",
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
        "requested_city": "Katowice",
        "has_car": True,
        "day_start": "09:00",
        "day_end": "21:00",
    }
    base.update(extra)
    return base


def test_park_slaski_gets_leading_hop_at_day_start():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Park Śląski", "09:00", "10:30", 90, lat=50.2878, lng=18.9745),
    ]
    out = _svc()._ensure_leading_transit(items, {}, _ctx(), day_num=1)
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert hops
    assert "śląsk" in (hops[0].to_location or "").lower() or "slask" in (
        hops[0].to_location or ""
    ).lower()


def test_etnograficzny_gets_leading_hop_without_coords():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="10:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION,
            poi_id="etno",
            name="Górnośląski Park Etnograficzny",
            description_short="",
            start_time="10:00",
            end_time="12:00",
            duration_min=120,
            lat=0,
            lng=0,
            address="Chorzów",
            city="Chorzów",
            cost_estimate=0,
        ),
    ]
    out = _svc()._ensure_leading_transit(
        items, {}, _ctx(day_start="10:00"), day_num=2,
    )
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert hops
    assert "etnograficzn" in (hops[0].to_location or "").lower()


def test_etnograficzny_late_entry_is_stripped():
    items = [
        _attr("Górnośląski Park Etnograficzny", "17:42", "19:12", 90),
    ]
    out = _svc()._strip_after_hours_museums(
        items, day_num=2, trip_date="2026-06-01",
    )
    assert not any("etnograficzn" in (it.name or "").lower() for it in out)


def test_etnograficzny_unique_across_days():
    days = [
        SimpleNamespace(day=2, items=[
            _attr("Górnośląski Park Etnograficzny", "10:00", "12:00"),
        ]),
        SimpleNamespace(day=3, items=[
            _attr("Górnośląski Park Etnograficzny", "11:00", "13:00"),
        ]),
    ]
    out = _svc()._strip_cross_day_trip_repeats(days)
    names = [
        getattr(it, "name", "")
        for d in out for it in (d.items or [])
        if getattr(it, "type", None) == ItemType.ATTRACTION
    ]
    assert sum("etnograficzn" in n.lower() for n in names) == 1


def test_park_slaski_unique_across_days():
    days = [
        SimpleNamespace(day=2, items=[_attr("Park Śląski", "10:00", "11:30")]),
        SimpleNamespace(day=5, items=[_attr("Park Śląski", "14:00", "15:30")]),
    ]
    out = _svc()._strip_cross_day_trip_repeats(days)
    names = [
        getattr(it, "name", "")
        for d in out for it in (d.items or [])
        if getattr(it, "type", None) == ItemType.ATTRACTION
    ]
    assert sum("śląsk" in n.lower() or "slask" in n.lower() for n in names) == 1


def test_park_chopina_unique_across_days():
    days = [
        SimpleNamespace(day=2, items=[
            _attr("Park im. Fryderyka Chopina", "16:00", "17:00"),
        ]),
        SimpleNamespace(day=3, items=[
            _attr("Park im. Fryderyka Chopina", "11:00", "12:00"),
        ]),
    ]
    out = _svc()._strip_cross_day_trip_repeats(days)
    names = [
        getattr(it, "name", "")
        for d in out for it in (d.items or [])
        if getattr(it, "type", None) == ItemType.ATTRACTION
    ]
    assert sum("chopina" in n.lower() for n in names) == 1


def test_muzeum_slaskie_shifted_to_1000():
    items = [
        _attr("Muzeum Śląskie", "09:15", "11:08", 113),
    ]
    out = _svc()._strip_after_hours_museums(
        items, day_num=2, trip_date="2026-02-20",
    )
    assert out
    assert out[0].start_time >= "10:00"


def test_cybermagia_denied_for_cultural():
    poi = {"name": "Cybermagia VR", "city": "Katowice"}
    user = {"target_group": "friends", "travel_style": "cultural", "preferences": []}
    assert should_deny_poi_for_profile(poi, user) is True


def test_szyb_wilson_denied_for_family_kids():
    poi = {"name": "Galeria Szyb Wilson", "city": "Katowice"}
    user = {
        "target_group": "family_kids",
        "children_age": 8,
        "preferences": ["kids_attractions"],
    }
    assert should_deny_poi_for_profile(poi, user) is True


def test_park_chopina_denied_for_friends_adventure():
    poi = {"name": "Park im. Fryderyka Chopina", "city": "Gliwice"}
    user = {
        "target_group": "friends",
        "travel_style": "adventure",
        "preferences": ["history_mystery"],
    }
    assert should_deny_poi_for_profile(poi, user) is True


def test_ghost_restaurant_hop_retargets_to_muzeum():
    items = [
        _attr("Park Śląski", "10:00", "12:00", 120, lat=50.2878, lng=18.9745),
        _tr("Park Śląski", "Restauracja Aperitif", "12:00", "12:12", km=3.0, dur=12),
        _attr("Muzeum Śląskie", "12:20", "14:00", 100, lat=50.264, lng=18.993),
    ]
    out = _svc()._retarget_all_legs_to_next_stop(items, day_num=1)
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert hops
    assert "śląsk" in (hops[0].to_location or "").lower() or "slask" in (
        hops[0].to_location or ""
    ).lower()
    assert "aperitif" not in (hops[0].to_location or "").lower()


def test_ghost_szyb_maciej_hop_dropped_when_next_is_sensoryczny():
    items = [
        _attr("Pogoria", "13:00", "14:30", 90),
        _tr("Pogoria", "Szyb Maciej", "14:30", "15:45", km=47.87, dur=75),
        _attr(
            "Park Sensoryczny Przy Radiostacji",
            "15:45", "16:30", 45, lat=50.307, lng=18.676,
        ),
    ]
    out = _svc()._drop_hops_not_to_next_stop(items, day_num=4)
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert not hops or "sensorycz" in (hops[0].to_location or "").lower()


def test_dolina_to_chrobrego_gets_a_drive():
    items = [
        _attr("Dolina Trzech Stawów", "09:30", "11:00", 90, lat=50.237, lng=19.038),
        FreeTimeItem(
            type=ItemType.FREE_TIME,
            start_time="11:00",
            end_time="11:31",
            duration_min=31,
            label="Czas dla siebie",
            suggestions=[],
        ),
        _attr(
            "Park Chrobrego", "11:31", "12:20", 49, lat=50.297, lng=18.665,
        ),
    ]
    out = _svc()._ensure_city_to_far_after_meal(
        items, {}, _ctx(), day_num=4,
    )
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert hops
    assert "chrobrego" in (hops[0].to_location or "").lower()


def test_tychy_to_willa_caro_gets_a_drive():
    items = [
        _attr("Wodny Park Tychy", "13:30", "15:00", 90, lat=50.123, lng=19.007),
        _attr("Willa Caro", "15:00", "16:30", 90, lat=50.294, lng=18.671),
    ]
    out = _svc()._ensure_city_to_far_after_meal(items, {}, _ctx(), day_num=4)
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert hops
    assert "caro" in (hops[0].to_location or "").lower()


def test_paprocany_29km_10min_clock_is_expanded():
    items = [
        _tr(
            "Paprocany", "Park Śląski",
            "13:08", "13:18", km=29.75, dur=42,
        ),
    ]
    out = _svc()._honest_transit_physics(items, day_num=5, context={"has_car": True})
    assert int(out[0].duration_min) >= 35
    assert out[0].end_time > "13:18"


def test_haversine_walk_becomes_estimated_walk():
    items = [
        _tr(
            "Muzeum Historii Katowic", "Olio",
            "12:00", "12:11", km=0.42, dur=11,
            mode=TransitMode.WALK, src="haversine",
        ),
    ]
    out = _svc()._honest_transit_physics(items, day_num=3, context={"has_car": True})
    assert "walk" in str(out[0].routing_source or "").lower()
    assert "haversine" not in str(out[0].routing_source or "").lower()


def test_hop_during_muzeum_visit_is_snapped():
    items = [
        _attr("Muzeum Śląskie", "10:48", "12:03", 75),
        _tr(
            "Muzeum Śląskie", "Ciao Italia",
            "11:52", "12:05", km=0.8, dur=13,
            mode=TransitMode.WALK, src="estimated_walk",
        ),
    ]
    out = _svc()._snap_transits_to_previous_stop_end(items, day_num=2)
    hop = next(it for it in out if it.type == ItemType.TRANSIT)
    assert hop.start_time >= "12:03"


def test_crushed_funhouse_is_dropped():
    items = [
        _attr("FunHouse", "10:00", "10:23", 23),
    ]
    out = _svc()._cap_stretched_attraction_durations(
        items, day_num=1, user={"target_group": "family_kids"},
    )
    assert not any("funhouse" in (it.name or "").lower() for it in out)


def test_48min_hole_is_named():
    items = [
        _attr("Kościół św. Michała", "11:00", "11:55", 55),
        _tr("Kościół św. Michała", "Spodek", "12:43", "12:55", km=2.0, dur=12),
        _attr("Spodek", "12:55", "13:40", 45),
    ]
    out = _svc()._name_remaining_holes(items, _ctx(), day_num=3)
    named = [it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME]
    assert named


def test_62min_morning_hole_is_named():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Browar Mariacki", "10:02", "11:00", 58),
    ]
    out = _svc()._name_remaining_holes(
        items, _ctx(day_start="09:00", day_end="20:00"), day_num=2,
    )
    named = [it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME]
    assert named


def test_lunch_context_follows_sensoryczny_arrival():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="13:26",
        end_time="14:06",
        duration_min=40,
        suggestions=[],
        location_context="Paprocany",
    )
    items = [
        _attr("Paprocany", "11:00", "12:30", 90, lat=50.096, lng=19.020),
        _tr("Paprocany", "Park Sensoryczny Przy Radiostacji", "12:30", "13:26", km=47.0, dur=56),
        lunch,
    ]
    out = _svc()._reset_stale_meal_location_context(items, day_num=4)
    meal = next(it for it in out if it.type == ItemType.LUNCH_BREAK)
    ctx = (getattr(meal, "location_context", "") or "").lower()
    assert "paprocan" not in ctx
    assert "sensorycz" in ctx
