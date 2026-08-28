"""FIX #300 — ghost hops, impossible times, hub-lunch in satellites, uniqueness."""
from __future__ import annotations

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    DinnerBreakItem,
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


def _attr(name, start, end, dur=60, *, lat=52.23, lng=21.01, city="Warszawa"):
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


def test_stacked_lunch_hops_keep_only_next_poi():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="13:00",
        end_time="14:00",
        duration_min=60,
        suggestions=[
            RestaurantSuggestion.model_construct(
                id="sloik",
                name="Restauracja Słoik",
                lat=52.24,
                lng=21.02,
                city="Warszawa",
            )
        ],
        location_context="centrum",
    )
    items = [
        lunch,
        _tr("Restauracja Słoik", "Manufaktura Cukierków", "14:00", "14:10", km=1.2, dur=10),
        _tr("Restauracja Słoik", "Ogrody Zamku Królewskiego", "14:10", "14:20", km=2.6, dur=10),
        _attr("Ogrody Zamku Królewskiego", "14:20", "15:20", 60),
    ]
    out = _svc()._collapse_stacked_transits(items, day_num=2)
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert len(hops) == 1
    assert "ogrod" in (hops[0].to_location or "").lower()
    assert "manufaktura" not in (hops[0].to_location or "").lower()


def test_city_name_ghost_hop_is_dropped():
    items = [
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="13:00",
            end_time="14:00",
            duration_min=60,
            suggestions=[
                RestaurantSuggestion.model_construct(
                    id="tutti", name="Tutti Santi", lat=52.23, lng=21.01, city="Warszawa",
                )
            ],
        ),
        _tr("Tutti Santi", "Warszawa", "14:00", "14:10", km=3.2, dur=10, mode=TransitMode.WALK),
        _tr("Tutti Santi", "Muzeum Wojska Polskiego", "14:10", "14:20", km=4.2, dur=10),
        _attr("Muzeum Wojska Polskiego", "14:20", "15:20", 60),
    ]
    out = _svc()._collapse_stacked_transits(items, day_num=2)
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert len(hops) == 1
    assert "wojska" in (hops[0].to_location or "").lower()


def test_self_transit_zero_km_is_stripped():
    items = [
        _attr("Centrum Nauki Kopernik", "10:00", "11:00", 60),
        _tr("Centrum Nauki Kopernik", "Centrum Nauki Kopernik", "11:00", "11:13", km=0, dur=13),
        _attr("Ogród Botaniczny UW", "11:20", "12:20", 60),
    ]
    out = _svc()._strip_self_transits(items, day_num=1)
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert hops == []


def test_too_fast_city_car_is_stretched():
    items = [
        _tr("Restauracja Słoik", "Ogrody Zamku Królewskiego", "14:00", "14:01", km=2.665, dur=1),
    ]
    out = _svc()._sync_transit_duration_to_clock(items, day_num=2)
    assert int(out[0].duration_min) >= 8
    assert out[0].end_time > out[0].start_time


def test_too_fast_walk_is_stretched():
    items = [
        _tr(
            "Muzeum X Pawilonu", "Zamek Królewski",
            "11:00", "11:05", km=3.352, dur=5,
            mode=TransitMode.WALK, src="estimated_walk",
        ),
    ]
    out = _svc()._sync_transit_duration_to_clock(items, day_num=1)
    assert int(out[0].duration_min) >= 20


def test_opening_hop_does_not_start_from_future_poi():
    items = [
        _tr("Ogród Saski", "Stare Miasto", "09:35", "09:49", km=1.2, dur=14, mode=TransitMode.WALK),
        _attr("Stare Miasto", "09:49", "11:00", 71),
        _attr("Ogród Saski", "12:00", "13:00", 60),
    ]
    out = _svc()._retarget_all_legs_to_prev_stop(
        items, day_num=1, context={"requested_city": "Warszawa"},
    )
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert hops
    assert "saski" not in (hops[0].from_location or "").lower()


def test_transit_cannot_start_before_attraction_ends():
    items = [
        _attr("Smart Kids Planet", "11:51", "13:51", 120),
        _tr("Smart Kids Planet", "Restauracja Słoik", "13:41", "13:55", km=1.0, dur=14),
    ]
    out = _svc()._snap_transits_to_previous_stop_end(items, day_num=1)
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert hops[0].start_time >= "13:51"


def test_krakow_hub_lunch_in_ojcow_is_cleared():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="13:00",
        end_time="13:45",
        duration_min=45,
        suggestions=[
            RestaurantSuggestion.model_construct(
                id="bocian",
                name="Restauracja Pod Bocianem",
                lat=50.210,
                lng=19.829,
                city="Ojców",
            )
        ],
    )
    items = [
        _attr("Zakrzówek", "10:00", "12:30", 150, lat=50.045, lng=19.915, city="Kraków"),
        lunch,
        _attr("Błonia", "14:30", "15:30", 60, lat=50.060, lng=19.920, city="Kraków"),
    ]
    out = _svc()._strip_far_meal_only_hops(items, day_num=2)
    meals = [it for it in out if it.type == ItemType.LUNCH_BREAK]
    assert meals
    assert not (getattr(meals[0], "suggestions", None) or [])


def test_post_dinner_return_to_visited_is_dropped():
    dinner = DinnerBreakItem.model_construct(
        type=ItemType.DINNER_BREAK,
        start_time="19:00",
        end_time="20:00",
        duration_min=60,
        suggestions=[
            RestaurantSuggestion.model_construct(
                id="d", name="Sioux", lat=50.06, lng=19.94, city="Kraków",
            )
        ],
    )
    items = [
        _attr("Barbakan", "16:00", "17:00", 60, lat=50.065, lng=19.941, city="Kraków"),
        dinner,
        _tr("Sioux", "Barbakan", "20:00", "20:15", km=0.8, dur=15, mode=TransitMode.WALK),
    ]
    out = _svc()._drop_post_dinner_return_to_visited(items, day_num=7)
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert hops == []


def test_powstanie_and_bednarski_are_trip_unique():
    assert poi_trip_repeat_key("Muzeum Powstania Warszawskiego") == "waw_powstanie"
    assert poi_trip_repeat_key("Park Bednarskiego") == "krk_bednarskiego"


def test_tepfactor_denied_for_solo_relax():
    assert should_deny_poi_for_profile(
        {"name": "Tepfactor"},
        {"target_group": "solo", "travel_style": "relax", "preferences": ["relaxation"]},
    )


def test_return_to_car_is_stamped():
    items = [
        _attr("Park Cytadela", "10:00", "11:00", 60, lat=52.422, lng=16.936),
        _tr(
            "Park Cytadela", "Muzeum Iluzji",
            "11:00", "11:22", km=1.5, dur=22,
            mode=TransitMode.WALK, src="estimated_walk",
        ),
        _attr("Muzeum Iluzji", "11:22", "12:22", 60, lat=52.408, lng=16.934),
        _tr(
            "Muzeum Iluzji", "Park Cytadela",
            "12:22", "12:40", km=1.5, dur=18,
            mode=TransitMode.WALK, src="estimated_walk",
        ),
        _tr(
            "Park Cytadela", "Termy Maltańskie",
            "12:40", "13:00", km=5.0, dur=20,
        ),
        _attr("Termy Maltańskie", "13:00", "15:00", 120, lat=52.404, lng=16.973),
    ]
    coords = {
        "Park Cytadela": {"lat": 52.422, "lng": 16.936},
        "Muzeum Iluzji": {"lat": 52.408, "lng": 16.934},
        "Termy Maltańskie": {"lat": 52.404, "lng": 16.973},
    }
    parked = _svc()._enforce_car_parking_logistics(
        items, coords, {"has_car": True, "requested_city": "Warszawa"}, day_num=3,
    )
    out = _svc()._relabel_return_to_car_transits(parked, day_num=3)
    stamped = [
        it for it in out
        if it.type == ItemType.TRANSIT
        and str(getattr(it, "routing_source", "")).lower() == "return_to_car"
    ]
    assert stamped
