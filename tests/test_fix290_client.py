"""FIX #290 — WAWA/KRK/KAT/POZ leftover: dupes, meals, hours, walk/car, transits."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.application.services.plan_service import PlanService
from app.domain.filters.seasonality import filter_by_season
from app.domain.models.plan import (
    AttractionItem,
    DayEndItem,
    DinnerBreakItem,
    ItemType,
    LunchBreakItem,
    RestaurantSuggestion,
    TransitItem,
    TransitMode,
)
from app.domain.planner.engine import (
    _meal_restaurant_geo_ok,
    poi_geo_region_key,
    visit_duration_hard_cap,
)
from app.domain.scoring.preference_coverage import poi_covers_preference_report
from app.domain.scoring.profile_poi_rules import (
    poi_trip_repeat_key,
    should_deny_poi_for_profile,
)


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur=60, *, lat=52.23, lng=21.01, city="Warszawa", cost=0):
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
        cost_estimate=cost,
    )


def _tr(frm, to, start, end, *, km, dur, mode=TransitMode.WALK, src="estimated_walk"):
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


def test_archikatedra_cap_is_45():
    assert visit_duration_hard_cap({"name": "Archikatedra św. Jana"}) == 45


def test_park_chopina_cap_is_45():
    assert visit_duration_hard_cap({"name": "Park Chopina"}) == 45


def test_cross_day_strips_archikatedra_and_ujazdowski():
    d1 = SimpleNamespace(day=1, items=[
        _attr("Archikatedra św. Jana", "11:00", "11:45", 45),
        _attr("Zamek Ujazdowski", "13:00", "14:30", 90),
    ], quality_badges=None, date=None, weekday=None)
    d2 = SimpleNamespace(day=2, items=[
        _attr("Archikatedra św. Jana", "10:00", "10:45", 45),
        _attr("Zamek Ujazdowski", "12:00", "13:30", 90),
    ], quality_badges=None, date=None, weekday=None)
    out = _svc()._strip_cross_day_trip_repeats([d1, d2])
    names2 = [getattr(it, "name", "") for it in out[1].items]
    assert "Archikatedra św. Jana" not in names2
    assert "Zamek Ujazdowski" not in names2


def test_wawel_castle_repeat_key_distinct_from_cathedral():
    assert poi_trip_repeat_key("Zamek Królewski na Wawelu") == "krk_wawel"
    assert poi_trip_repeat_key("Katedra Wawelska") == "krk_katedra_wawel"


def test_funzeum_denied_for_friends_and_couples():
    poi = {"name": "Funzeum", "city": "Gliwice"}
    assert should_deny_poi_for_profile(poi, {
        "target_group": "friends", "preferences": ["museum_heritage"],
        "travel_style": "cultural",
    })
    assert should_deny_poi_for_profile(poi, {
        "target_group": "couples", "preferences": ["relaxation"],
        "travel_style": "relax",
    })
    assert not should_deny_poi_for_profile(poi, {
        "target_group": "family_kids", "preferences": ["kids_attractions"],
        "travel_style": "balanced", "children_age": 8,
    })


def test_jumpcity_denied_for_cultural():
    assert should_deny_poi_for_profile(
        {"name": "JUMPCITY"},
        {"target_group": "couples", "preferences": ["museum_heritage"],
         "travel_style": "cultural"},
    )


def test_grawitacja_is_not_relaxation_coverage():
    assert not poi_covers_preference_report(
        {"name": "Stacja Grawitacja", "tags": ["relaxation"]},
        "relaxation",
    )


def test_park_cytadela_is_not_underground():
    assert not poi_covers_preference_report(
        {"name": "Park Cytadela", "tags": ["underground", "citadel"]},
        "underground",
    )


def test_polin_denied_without_museum_pref():
    assert should_deny_poi_for_profile(
        {"name": "POLIN Muzeum Historii Żydów Polskich"},
        {"target_group": "friends",
         "preferences": ["nature_landscape", "local_food_experience", "relaxation"],
         "travel_style": "relax"},
    )


def test_winter_blocks_doswiadczen_and_lokietka():
    winter = date(2026, 2, 23)
    pois = [
        {"id": "1", "name": "Ogród Doświadczeń", "season_fit": {"winter": 1, "spring": 1}},
        {"id": "2", "name": "Jaskinia Łokietka", "season_fit": {"winter": 1, "spring": 1}},
        {"id": "3", "name": "Wawel", "season_fit": {"winter": 1, "spring": 1}},
    ]
    kept = {p["name"] for p in filter_by_season(pois, "2026-02-23")}
    assert "Ogród Doświadczeń" not in kept
    assert "Jaskinia Łokietka" not in kept
    assert "Wawel" in kept


def test_monday_strips_sukiennice_and_brama():
    items = [
        _attr("MNK Sukiennice", "11:00", "12:00", 60, city="Kraków"),
        _attr("Brama Poznania", "15:50", "17:25", 95, city="Poznań"),
        _attr("Rynek Główny", "12:30", "13:30", 60, city="Kraków"),
    ]
    out = _svc()._strip_closed_on_weekday(items, date(2026, 7, 20), day_num=1)
    names = [getattr(it, "name", "") for it in out]
    assert "MNK Sukiennice" not in names
    assert "Brama Poznania" not in names
    assert "Rynek Główny" in names


def test_podziemia_fary_only_saturday():
    items = [_attr("Podziemia Fary", "11:57", "12:40", 43, city="Poznań")]
    mon = _svc()._strip_closed_on_weekday(items, date(2026, 7, 20), day_num=1)
    sat = _svc()._strip_closed_on_weekday(items, date(2026, 7, 25), day_num=1)
    assert mon == []
    assert sat and sat[0].name == "Podziemia Fary"


def test_powstania_clamped_to_18():
    items = [_attr("Muzeum Powstania Warszawskiego", "17:25", "18:40", 75)]
    out = _svc()._strip_after_hours_museums(items, day_num=3)
    assert out and out[0].end_time == "18:00"
    assert int(out[0].duration_min) == 35


def test_late_katedra_stripped():
    items = [_attr("Katedra Wawelska", "20:57", "21:37", 40, city="Kraków")]
    out = _svc()._strip_after_hours_museums(items, day_num=2)
    assert out == []


def test_dinner_capped_to_75():
    items = [
        DinnerBreakItem.model_construct(
            type=ItemType.DINNER_BREAK,
            start_time="19:00",
            end_time="21:16",
            duration_min=136,
            suggestions=[],
        ),
    ]
    out = _svc()._enforce_dinner_min_duration(
        items, {"day_end": "21:00"}, day_num=1,
    )
    assert int(out[0].duration_min) == 75


def test_family_1km_stays_walk_but_2km_becomes_car():
    short = _tr(
        "Archikatedra", "Ogród Saski", "14:00", "14:16",
        km=1.0, dur=16, mode=TransitMode.WALK,
    )
    long = _tr(
        "Smart Kids", "Lunch", "12:00", "12:26",
        km=1.96, dur=26, mode=TransitMode.WALK,
    )
    ctx = {
        "has_car": True,
        "user": {
            "target_group": "family_kids",
            "travel_style": "relax",
            "preferences": ["kids_attractions", "relaxation"],
            "children_age": 5,
        },
    }
    out = _svc()._downgrade_short_urban_cars([short, long], ctx, day_num=1)
    assert "walk" in str(getattr(out[0].mode, "value", out[0].mode)).lower()
    assert "car" in str(getattr(out[1].mode, "value", out[1].mode)).lower()


def test_self_transit_palmiarnia_stripped():
    hop = _tr(
        "Palmiarnia", "Palmiarnia", "11:00", "11:31",
        km=0.0, dur=31, mode=TransitMode.CAR, src="estimated_road",
    )
    out = _svc()._strip_self_transits([hop], day_num=1)
    assert out == []


def test_retarget_transit_to_next_poi_not_later_museum():
    items = [
        _attr("Kampinoski Park Narodowy", "10:00", "14:00", 240),
        _tr(
            "Kampinoski Park Narodowy", "Muzeum Powstania Warszawskiego",
            "14:00", "15:00", km=18.0, dur=60, mode=TransitMode.CAR,
            src="estimated_road",
        ),
        _attr("Multimedialny Park Fontann", "15:10", "15:40", 30),
        _attr("Muzeum Powstania Warszawskiego", "16:00", "17:30", 90),
    ]
    out = _svc()._retarget_all_legs_to_next_stop(items, day_num=3)
    legs = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert legs and legs[0].to_location == "Multimedialny Park Fontann"


def test_sync_duration_min_to_clock_when_short_hop():
    hop = _tr(
        "Katedra Wawelska", "MIŁA", "14:09", "14:14",
        km=0.8, dur=18, mode=TransitMode.WALK,
    )
    out = _svc()._sync_transit_duration_to_clock([hop], day_num=1)
    assert int(out[0].duration_min) == 5


def test_dangling_ojcow_restaurant_transit_dropped():
    items = [
        _attr("Zamek w Ojcowie", "15:00", "16:30", 90, city="Ojców"),
        _tr(
            "Zamek w Ojcowie", "Restauracja Pod Bocianem",
            "16:30", "17:10", km=8.0, dur=40, mode=TransitMode.CAR,
            src="estimated_road",
        ),
        DayEndItem(time="20:00"),
    ]
    out = _svc()._drop_dangling_meal_transits(items, day_num=4)
    assert not any(getattr(it, "type", None) == ItemType.TRANSIT for it in out)


def test_meal_geo_refuses_wieliczka_after_blonia():
    last = {"name": "Błonia", "lat": 50.059, "lng": 19.907, "city": "Kraków"}
    rest = {
        "name": "Restauracja w Wieliczce",
        "lat": 49.987, "lng": 20.065, "city": "Wieliczka",
        "address": "Wieliczka",
    }
    assert _meal_restaurant_geo_ok(rest, last, {"requested_city": "Kraków"}) is False


def test_wilanow_family_preschooler_capped():
    item = _attr("Pałac w Wilanowie", "15:00", "16:30", 90)
    out = _svc()._cap_stretched_attraction_durations(
        [item], day_num=1,
        user={"target_group": "family_kids", "children_age": 5, "travel_style": "relax"},
    )
    assert 60 <= int(out[0].duration_min) <= 70


def test_schindler_crushed_is_dropped():
    item = _attr("Fabryka Schindlera", "16:00", "16:28", 28, city="Kraków")
    out = _svc()._drop_crushed_named_visits([item], day_num=2)
    assert out == []


def test_attraction_overrun_is_clipped():
    items = [
        _attr("POLIN", "18:00", "19:57", 117),
        DayEndItem(time="19:00"),
    ]
    out = _svc()._clamp_timeline_to_day_end(items, {"day_end": "19:00"}, day_num=1)
    polin = [it for it in out if getattr(it, "name", "") == "POLIN"]
    assert polin and polin[0].end_time == "19:00"


def test_thin_park_orientacji_dropped():
    items = [
        _attr("Stary Rynek", "10:00", "11:00", 60, lat=52.408, lng=16.934, city="Poznań"),
        _tr(
            "Stary Rynek", "Park Orientacji Przestrzennej",
            "11:00", "11:47", km=18.0, dur=47, mode=TransitMode.CAR,
            src="estimated_road",
        ),
        _attr(
            "Park Orientacji Przestrzennej", "11:47", "12:07", 20,
            lat=52.51, lng=16.97, city="Owińska",
        ),
        DayEndItem(time="19:00"),
    ]
    out = _svc()._drop_thin_lonely_far_stops(items, day_num=2)
    names = [getattr(it, "name", "") for it in out]
    assert "Park Orientacji Przestrzennej" not in names


def test_funzeum_is_gliwice_region():
    assert poi_geo_region_key({"name": "Funzeum", "city": "Katowice"}) == "region_gliwice"


def test_owińska_park_is_far_region():
    assert poi_geo_region_key(
        {"name": "Park Orientacji Przestrzennej", "city": "Owińska"}
    ) == "region_lednica"
