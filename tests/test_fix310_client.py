"""FIX #310 — Wrocław leftover: coords, meal floors, satellite food, hours."""
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


def _ctx(**extra):
    base = {
        "requested_city": "Wrocław",
        "has_car": True,
        "day_start": "10:00",
        "day_end": "19:00",
    }
    base.update(extra)
    return base


def test_botaniczny_pergola_pin_moves_to_sienkiewicza():
    items = [
        _attr(
            "Ogród Botaniczny", "11:00", "12:00", 60,
            lat=51.108056, lng=17.073056,
        ),
    ]
    out = _svc()._correct_wroclaw_botaniczny_coords(
        items, _ctx(), day_num=1,
    )
    assert abs(float(out[0].lat) - 51.1163) < 0.001
    assert abs(float(out[0].lng) - 17.0478) < 0.001


def test_warsaw_botaniczny_coords_untouched():
    items = [
        _attr(
            "Ogród Botaniczny UW", "11:00", "12:00", 60,
            lat=52.2156, lng=21.0270, city="Warszawa",
        ),
    ]
    out = _svc()._correct_wroclaw_botaniczny_coords(
        items, {"requested_city": "Warszawa"}, day_num=1,
    )
    assert abs(float(out[0].lat) - 52.2156) < 0.001


def test_krakow_uj_botaniczny_coords_untouched():
    items = [
        _attr(
            "Ogród Botaniczny UJ", "11:00", "12:00", 60,
            lat=50.0636, lng=19.9578, city="Kraków",
        ),
    ]
    out = _svc()._correct_wroclaw_botaniczny_coords(
        items, {"requested_city": "Kraków"}, day_num=4,
    )
    assert abs(float(out[0].lat) - 50.0636) < 0.001


def test_botaniczny_japonski_pergola_unique_across_days():
    assert poi_trip_repeat_key(
        "Ogród Botaniczny Uniwersytetu Wrocławskiego"
    ) == "wro_ogrod_botaniczny"
    assert poi_trip_repeat_key("Ogród Botaniczny UW") == "waw_ogrod_botaniczny"
    days = [
        SimpleNamespace(day=1, items=[
            _attr("Ogród Botaniczny", "11:00", "12:00"),
            _attr("Ogród Japoński", "14:00", "15:00"),
            _attr("Pergola przy Hali Stulecia", "16:00", "16:45"),
        ]),
        SimpleNamespace(day=2, items=[
            _attr("Ogród Botaniczny", "10:30", "11:30"),
        ]),
        SimpleNamespace(day=3, items=[
            _attr("Pergola przy Hali Stulecia", "11:00", "12:00"),
        ]),
        SimpleNamespace(day=4, items=[
            _attr("Ogród Japoński", "10:00", "11:00"),
        ]),
    ]
    out = _svc()._strip_cross_day_trip_repeats(days)
    names = [
        getattr(it, "name", "")
        for d in out for it in (d.items or [])
        if getattr(it, "type", None) == ItemType.ATTRACTION
    ]
    assert sum("botanicz" in n.lower() for n in names) == 1
    assert sum("japoń" in n.lower() or "japon" in n.lower() for n in names) == 1
    assert sum("pergola" in n.lower() for n in names) == 1


def test_zoo_team_before_open_is_shifted():
    items = [
        _attr("ZOO TEAM", "09:20", "10:50", 90, lat=51.105, lng=17.074),
    ]
    out = _svc()._strip_after_hours_museums(
        items, day_num=1, trip_date="2026-06-01",
    )
    assert out
    assert out[0].start_time >= "10:00"


def test_panorama_before_open_is_shifted():
    items = [
        _attr("Panorama Racławicka", "09:20", "10:00", 40),
    ]
    out = _svc()._strip_after_hours_museums(
        items, day_num=3, trip_date="2026-06-01",
    )
    assert out
    assert out[0].start_time >= "09:30"


def test_early_lunch_is_pushed_to_noon():
    items = [
        _lunch("09:20", "10:00", 40, [_sug("Olio Pizza Napoletana")]),
    ]
    out = _svc()._push_lunch_not_before_noon(items, day_num=3)
    assert out[0].start_time >= "12:00"


def test_early_dinner_is_pushed_to_1730():
    items = [
        _dinner("11:20", "12:05", 45, [_sug("Konspira")]),
    ]
    out = _svc()._push_dinner_not_before(
        items, earliest=17 * 60 + 30, day_num=3,
    )
    assert out[0].start_time >= "17:30"


def test_brzeg_and_zabkowice_meals_stripped_on_wroclaw_day():
    items = [
        _attr("Rynek we Wrocławiu", "10:00", "11:00"),
        _lunch(
            "10:20", "11:00", 40,
            [_sug(
                "Bar na Długiej",
                lat=50.861, lng=17.467,
                city="Brzeg",
                address="Długa 41, Brzeg",
            )],
        ),
        _dinner(
            "11:20", "12:05", 45,
            [_sug(
                "Mała Grecja",
                lat=50.589, lng=16.812,
                city="Ząbkowice Śląskie",
                address="Ząbkowice Śląskie",
            )],
        ),
    ]
    out = _svc()._strip_satellite_meals_on_city_days(items, day_num=3)
    meals = [
        it for it in out
        if getattr(it, "type", None) in (ItemType.LUNCH_BREAK, ItemType.DINNER_BREAK)
    ]
    assert meals == []
    assert any("rynek" in (it.name or "").lower() for it in out)


def test_zabkowice_meal_kept_on_real_daytrip():
    items = [
        _attr("Krzywa Wieża", "11:00", "12:00", lat=50.590, lng=16.812),
        _lunch(
            "12:10", "12:50", 40,
            [_sug(
                "Mała Grecja",
                lat=50.589, lng=16.812,
                city="Ząbkowice Śląskie",
                address="Ząbkowice Śląskie",
            )],
        ),
    ]
    out = _svc()._strip_satellite_meals_on_city_days(items, day_num=6)
    meals = [
        it for it in out
        if getattr(it, "type", None) == ItemType.LUNCH_BREAK
    ]
    assert meals
    assert meals[0].suggestions


def test_meal_only_zabkowice_day_is_cleared():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME,
            start_time="09:30",
            end_time="09:50",
            duration_min=20,
            label="Czas dla siebie",
            suggestions=[],
        ),
        _lunch(
            "09:50", "10:15", 25,
            [_sug(
                "Restauracja Olimpijska",
                lat=50.589, lng=16.812,
                city="Ząbkowice Śląskie",
                address="Powstańców Warszawy 8i, Ząbkowice Śląskie",
            )],
        ),
        DayEndItem(time="10:15"),
    ]
    out = _svc()._strip_satellite_meals_on_city_days(items, day_num=5)
    assert not any(
        getattr(it, "type", None) == ItemType.LUNCH_BREAK for it in out
    )


def test_203m_car_becomes_walk():
    items = [
        _tr(
            "Rynek", "Chinkalnia", "13:00", "13:05",
            km=0.203, dur=5, mode=TransitMode.CAR, src="estimated_road",
        ),
    ]
    out = _svc()._downgrade_short_urban_cars(items, _ctx(), day_num=1)
    assert out[0].mode == TransitMode.WALK
    src = str(out[0].routing_source or "").lower()
    assert "walk" in src


def test_walk_haversine_becomes_estimated_walk():
    items = [
        _tr(
            "Rynek", "Chinkalnia", "13:00", "13:03",
            km=0.083, dur=3, mode=TransitMode.WALK, src="haversine",
        ),
    ]
    out = _svc()._honest_transit_physics(
        items, day_num=2, context={"has_car": True},
    )
    assert out[0].mode == TransitMode.WALK
    assert "haversine" not in str(out[0].routing_source or "").lower()
    assert "walk" in str(out[0].routing_source or "").lower()


def test_honest_19km_city_walk_is_untouched():
    items = [
        _tr(
            "Hydropolis", "Rynek", "16:00", "16:28",
            km=1.9, dur=28, mode=TransitMode.WALK, src="estimated_walk",
        ),
    ]
    out = _svc()._downgrade_short_urban_cars(items, _ctx(), day_num=1)
    assert out[0].mode == TransitMode.WALK
    assert abs(float(out[0].distance_km) - 1.9) < 0.01
    out2 = _svc()._honest_transit_physics(
        out, day_num=1, context={"has_car": True},
    )
    assert out2[0].mode == TransitMode.WALK


def test_neon_side_inverted_clock_is_repaired():
    items = [
        _attr("Galeria Neon Side", "18:00", "16:55", 55),
    ]
    out = _svc()._fix_inverted_item_clocks(items, day_num=2)
    assert out[0].end_time >= out[0].start_time


def test_wyspa_overlap_hop_snaps_after_visit():
    items = [
        _attr("Wyspa Słodowa", "12:39", "13:54", 75),
        _tr(
            "Wyspa Słodowa", "Konspira", "13:46", "13:54",
            km=0.4, dur=8, mode=TransitMode.WALK, src="estimated_walk",
        ),
        _lunch("13:54", "14:34", 40, [_sug("Konspira")]),
    ]
    out = _svc()._snap_transits_to_previous_stop_end(items, day_num=2)
    hop = next(it for it in out if getattr(it, "type", None) == ItemType.TRANSIT)
    assert hop.start_time >= "13:54"


def test_ghost_bastion_hop_retargets_to_japonski():
    items = [
        _lunch("13:00", "13:57", 57, [_sug("IDA")]),
        _tr("IDA", "Bastion Sakwowy", "13:57", "14:13", km=1.2, dur=16),
        _attr("Ogród Japoński", "14:13", "15:13", 60, lat=51.1083, lng=17.0780),
    ]
    out = _svc()._retarget_all_legs_to_next_stop(items, day_num=1)
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert hops
    assert "japoń" in (hops[0].to_location or "").lower() or "japon" in (
        hops[0].to_location or ""
    ).lower()


def test_30min_hole_after_hala_is_named():
    items = [
        _attr("Hala Stulecia", "13:00", "14:02", 62),
        _tr(
            "Hala Stulecia", "Muzeum Pana Tadeusza", "14:32", "14:50",
            km=3.2, dur=18,
        ),
        _attr("Muzeum Pana Tadeusza", "14:50", "16:00", 70),
    ]
    out = _svc()._name_remaining_holes(items, _ctx(), day_num=5)
    named = [it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME]
    assert named


def test_wroclaw_lunch_is_kept_on_city_day():
    items = [
        _attr("Pergola przy Hali Stulecia", "10:00", "10:35"),
        _lunch("12:00", "12:40", 40, [_sug("Olio Pizza Napoletana")]),
    ]
    out = _svc()._strip_satellite_meals_on_city_days(items, day_num=6)
    meals = [
        it for it in out
        if getattr(it, "type", None) == ItemType.LUNCH_BREAK
    ]
    assert meals
    assert meals[0].suggestions
