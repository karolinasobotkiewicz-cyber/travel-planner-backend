"""FIX #287 — Warszawa client notes: quota, pin, durations, walk, regions."""
from __future__ import annotations

from app.application.services.plan_service import (
    PlanService,
    _is_czersk_stop_name,
    _is_kampinos_stop_name,
    _is_sochaczew_stop_name,
    _timeline_satellite_kind,
)
from app.domain.models.plan import (
    AttractionItem,
    FreeTimeItem,
    ItemType,
    LunchBreakItem,
    ParkingInfo,
    RestaurantSuggestion,
    TransitItem,
    TransitMode,
)
from app.domain.planner.engine import (
    choose_duration,
    city_daytrip_quota,
    is_afternoon_only_poi,
    is_water_attraction_poi,
    should_block_city_daytrip_poi,
    visit_duration_hard_cap,
)
from app.domain.scoring.preference_coverage import poi_covers_preference_report
from app.domain.scoring.profile_poi_rules import should_deny_poi_for_profile


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(
    name,
    start,
    end,
    dur=60,
    *,
    lat=52.23,
    lng=21.01,
    address="Warszawa",
    city="Warszawa",
):
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
        address=address,
        city=city,
        cost_estimate=0,
    )


def test_warsaw_quota_matches_wroclaw():
    assert city_daytrip_quota({"requested_city": "Warszawa", "num_days": 2}) == 0
    assert city_daytrip_quota({"requested_city": "Warszawa", "num_days": 3}) == 0
    assert city_daytrip_quota({"requested_city": "Warszawa", "num_days": 5}) == 1
    assert city_daytrip_quota({"requested_city": "Warszawa", "num_days": 7}) == 2


def test_three_day_blocks_czersk_and_kampinos():
    ctx = {
        "requested_city": "Warszawa",
        "num_days": 3,
        "current_day_num": 2,
        "trip_type": "city_tourism",
        "preferences": ["museum_heritage", "relaxation"],
    }
    assert should_block_city_daytrip_poi(
        {"name": "Zamek w Czersku", "city": "Czersk"}, ctx,
    ) is True
    assert should_block_city_daytrip_poi(
        {"name": "Kampinoski Park Narodowy", "city": "Kampinos"}, ctx,
    ) is True


def test_five_day_kampinos_from_day_three():
    ctx = {
        "requested_city": "Warszawa",
        "num_days": 5,
        "current_day_num": 3,
        "trip_type": "city_tourism",
        "preferences": ["nature_landscape", "museum_heritage", "history_mystery"],
    }
    kampinos = {"name": "Kampinoski Park Narodowy", "city": "Kampinos"}
    assert should_block_city_daytrip_poi(kampinos, ctx) is False
    assert should_block_city_daytrip_poi(
        kampinos, {**ctx, "current_day_num": 1},
    ) is True
    assert should_block_city_daytrip_poi(
        kampinos, {**ctx, "current_day_num": 2},
    ) is True


def test_satellite_kinds_warsaw():
    assert _is_kampinos_stop_name("Kampinoski Park Narodowy")
    assert _is_czersk_stop_name("Zamek w Czersku")
    assert _is_sochaczew_stop_name("Ruiny Zamku Książąt Mazowieckich w Sochaczewie")
    assert _timeline_satellite_kind("Kampinoski Park Narodowy") == "kampinos"
    assert _timeline_satellite_kind("Zamek w Czersku") == "czersk"
    assert _timeline_satellite_kind("Ruiny Zamku w Sochaczewie") == "sochaczew"
    assert _timeline_satellite_kind("Zamek Królewski") is None


def test_force_warsaw_iluzja_keeps_rynek():
    item = _attr(
        "Muzeum Świat Iluzji",
        "11:00",
        "12:30",
        90,
        lat=51.1070,
        lng=17.0325,
        address="Świdnicka 36, 50-066 Wrocław",
        city="Warszawa",
    )
    item = item.model_copy(update={
        "parking": ParkingInfo.model_construct(
            name="Parking na Bugaja",
            walk_time_min=4,
            lat=52.2516,
            lng=21.0124,
        ),
    })
    out = _svc()._force_known_good_poi_coords([item], day_num=1)
    assert abs(float(out[0].lng) - 21.0119) < 0.01
    assert abs(float(out[0].lat) - 52.2495) < 0.01
    assert "warszaw" in (out[0].address or "").lower() or "rynek" in (out[0].address or "").lower()


def test_force_wroclaw_iluzja_still_swidnicka():
    item = _attr(
        "Muzeum Świat Iluzji we Wrocławiu",
        "11:00",
        "12:00",
        60,
        lat=51.1069,
        lng=17.0773,
        address="Hala Stulecia",
        city="Wrocław",
    )
    out = _svc()._force_known_good_poi_coords([item], day_num=1)
    assert abs(float(out[0].lng) - 17.0325) < 0.01
    assert "świdnicka" in (out[0].address or "").lower() or "swidnicka" in (out[0].address or "").lower()


def test_duration_floors_and_caps():
    assert visit_duration_hard_cap({"name": "Smart Kids Planet"}) == 120
    assert visit_duration_hard_cap({"name": "Hala Koszyki"}) == 75
    assert visit_duration_hard_cap(
        {"name": "Ruiny Zamku Książąt Mazowieckich w Sochaczewie"}
    ) == 90
    assert choose_duration(
        {"name": "Pijalnia Czekolady E.Wedel", "time_min": 10, "time_max": 180},
        10 * 60, 19 * 60, True,
    ) >= 45
    assert choose_duration(
        {"name": "Muzeum Powstania Warszawskiego", "time_min": 10, "time_max": 180, "type": "museum"},
        10 * 60, 19 * 60, True,
    ) >= 75
    assert choose_duration(
        {"name": "Muzeum Wojska Polskiego", "time_min": 10, "time_max": 180, "type": "museum"},
        10 * 60, 19 * 60, True,
    ) >= 60
    assert choose_duration(
        {"name": "Państwowe Muzeum Etnograficzne", "time_min": 10, "time_max": 180, "type": "museum"},
        10 * 60, 19 * 60, True,
    ) >= 60
    assert choose_duration(
        {"name": "Zamek Królewski", "city": "Warszawa", "time_min": 20, "time_max": 180},
        10 * 60, 18 * 60, True,
    ) >= 90
    assert choose_duration(
        {"name": "Zamek Królewski", "city": "Poznań", "time_min": 20, "time_max": 180},
        10 * 60, 18 * 60, True,
    ) <= 75


def test_koszyki_not_water_and_not_morning_opener():
    poi = {"name": "Hala Koszyki", "tags": ["food_hall", "local_food_experience"]}
    assert poi_covers_preference_report(poi, "water_attractions") is False
    assert is_water_attraction_poi(poi) is False
    assert is_afternoon_only_poi(poi) is True


def test_powazki_denied_for_nature_relax():
    assert should_deny_poi_for_profile(
        {"name": "Cmentarz Powązkowski"},
        {
            "target_group": "solo",
            "travel_style": "relax",
            "preferences": ["nature_landscape", "relaxation"],
        },
    ) is True


def test_car_chain_keeps_sub_1_5km_walk():
    items = [
        TransitItem(
            type=ItemType.TRANSIT,
            start_time="10:00",
            end_time="10:20",
            duration_min=20,
            mode=TransitMode.CAR,
            from_location="Hotel",
            to_location="Nonna Pizzeria",
            routing_source="estimated_road",
            distance_km=8.0,
        ),
        TransitItem(
            type=ItemType.TRANSIT,
            start_time="13:00",
            end_time="13:42",
            duration_min=42,
            mode=TransitMode.WALK,
            from_location="Nonna Pizzeria",
            to_location="Bazylika",
            routing_source="estimated_walk",
            distance_km=1.19,
        ),
    ]
    out = _svc()._enforce_day_transport_consistency(
        items,
        {"transport_modes": ["car"]},
        {"transport_modes": ["car"], "has_car": True},
        day_num=1,
    )
    hop = next(
        it for it in out
        if getattr(it, "to_location", "") == "Bazylika"
    )
    mode = getattr(getattr(hop, "mode", None), "value", hop.mode)
    assert str(mode).lower() == "walk"


def test_force_short_hops_walk():
    hop = TransitItem(
        type=ItemType.TRANSIT,
        start_time="16:00",
        end_time="16:41",
        duration_min=41,
        mode=TransitMode.CAR,
        from_location="Ogród Krasińskich",
        to_location="Ogrody Zamku Królewskiego",
        routing_source="estimated_road",
        distance_km=0.957,
    )
    out = _svc()._force_short_city_hops_walk([hop], day_num=7)
    mode = getattr(getattr(out[0], "mode", None), "value", out[0].mode)
    assert str(mode).lower() == "walk"
    assert int(out[0].duration_min) <= 25


def test_strip_mixed_kampinos_czersk_keeps_one_region():
    items = [
        _attr("Kampinoski Park Narodowy", "10:00", "12:00", 120, lat=52.32, lng=20.85),
        _attr("Zamek w Czersku", "14:00", "15:00", 60, lat=51.95, lng=21.23),
    ]
    out = _svc()._strip_mixed_opn_krakow_attractions(items, None, day_num=5)
    names = [it.name for it in out if _is_attr(it)]
    assert not (
        any("kampinos" in n.lower() for n in names)
        and any("czersk" in n.lower() for n in names)
    )


def test_strip_mixed_kampinos_drops_wilanow_same_day():
    items = [
        _attr("Kampinoski Park Narodowy", "10:00", "12:00", 120, lat=52.32, lng=20.85),
        _attr("Pałac w Wilanowie", "14:00", "16:00", 120, lat=52.165, lng=21.090),
    ]
    out = _svc()._strip_mixed_opn_krakow_attractions(items, None, day_num=5)
    names = [it.name for it in out if _is_attr(it)]
    assert any("kampinos" in n.lower() for n in names)
    assert not any("wilanow" in n.lower() or "wilanów" in n.lower() for n in names)


def test_lunch_transit_stale_from_retargeted():
    items = [
        _attr("Zamek w Czersku", "11:00", "12:00", 60, lat=51.95, lng=21.23),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="12:10",
            end_time="13:10",
            duration_min=60,
            label="Lunch",
            suggestions=[
                RestaurantSuggestion.model_construct(
                    id="r1", name="Karczma", lat=51.95, lng=21.23,
                ),
            ],
        ),
        TransitItem(
            type=ItemType.TRANSIT,
            start_time="13:10",
            end_time="14:40",
            duration_min=90,
            mode=TransitMode.CAR,
            from_location="Zamek w Czersku",
            to_location="Zamek Królewski",
            routing_source="estimated_road",
            distance_km=40.0,
        ),
    ]
    out = _svc()._retarget_all_legs_to_prev_stop(items, day_num=2)
    hop = next(it for it in out if getattr(it, "type", None) == ItemType.TRANSIT)
    assert hop.from_location == "Karczma"


def test_free_time_overlapping_transit_trimmed():
    items = [
        TransitItem(
            type=ItemType.TRANSIT,
            start_time="13:18",
            end_time="13:40",
            duration_min=22,
            mode=TransitMode.WALK,
            from_location="Zamek",
            to_location="Park",
            routing_source="estimated_walk",
            distance_km=1.2,
        ),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME,
            start_time="11:58",
            end_time="13:23",
            duration_min=85,
            label="Spokojny poranek",
            suggestions=[],
        ),
    ]
    out = _svc()._remove_timeline_overlaps(items, 2)
    ft = next(it for it in out if getattr(it.type, "value", it.type) == "free_time")
    tr = next(it for it in out if getattr(it.type, "value", it.type) == "transit")
    assert ft.end_time <= tr.start_time or ft.start_time >= tr.end_time


def test_scrub_norblin_warning_when_not_in_plan():
    days = [
        type("D", (), {
            "items": [_attr("Zamek Królewski", "10:00", "12:00", 120)],
        })()
    ]
    warnings = [
        {
            "type": "closed_attraction",
            "message": "Muzeum Fabryki Norblina jest zamknięte w poniedziałek.",
            "poi": "Muzeum Fabryki Norblina",
        }
    ]
    out = _svc()._scrub_unscheduled_poi_warnings(warnings, days)
    assert out == []


def test_warsaw_restaurant_max_one_use():
    jakub = RestaurantSuggestion.model_construct(
        id="r1", name="Restauracja U Jakuba", lat=52.23, lng=21.01,
    )
    other = RestaurantSuggestion.model_construct(
        id="r2", name="Nonna Pizzeria", lat=52.24, lng=21.01,
    )
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="13:00",
        end_time="14:00",
        duration_min=60,
        label="Restauracja U Jakuba",
        suggestions=[jakub, other],
    )
    ctx = {
        "requested_city": "Warszawa",
        "num_days": 3,
        "trip_used_restaurants": set(),
        "trip_restaurant_counts": {"restauracja u jakuba": 1},
        "restaurants_available": [],
    }
    out = _svc()._diversify_meal_suggestions([lunch], ctx, day_num=2)
    assert out[0].suggestions[0].name == "Nonna Pizzeria"


def test_strip_ft_before_long_far_hop():
    items = [
        _attr("Łazienki Królewskie", "10:00", "12:00", 120),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME,
            start_time="12:00",
            end_time="12:57",
            duration_min=57,
            label="Czas dla siebie",
            suggestions=[],
        ),
        TransitItem(
            type=ItemType.TRANSIT,
            start_time="12:57",
            end_time="14:27",
            duration_min=90,
            mode=TransitMode.CAR,
            from_location="Łazienki Królewskie",
            to_location="Kampinoski Park Narodowy",
            routing_source="estimated_road",
            distance_km=56.0,
        ),
        _attr("Kampinoski Park Narodowy", "14:27", "16:00", 93, lat=52.32, lng=20.85),
    ]
    out = _svc()._strip_free_time_before_long_far_hop(items, {}, day_num=5)
    assert not any(
        getattr(it.type, "value", it.type) == "free_time" for it in out
    )


def _is_attr(it) -> bool:
    return getattr(it, "type", None) == ItemType.ATTRACTION
