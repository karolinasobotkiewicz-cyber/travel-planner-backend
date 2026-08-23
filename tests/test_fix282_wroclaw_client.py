"""FIX #282 — Wrocław json 1–10: day-trips, durations, transits, winter copy."""
from __future__ import annotations

from app.application.services.plan_service import (
    PlanService,
    _day_note_matches_timeline,
    _early_close_enabled,
    _generate_day_title,
    _quality_first_trip,
    _sanitize_winter_attraction_copy,
)
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
from app.domain.planner.engine import (
    choose_duration,
    city_daytrip_quota,
    should_block_city_daytrip_poi,
    visit_duration_hard_cap,
)
from app.domain.scoring.profile_poi_rules import should_deny_poi_for_profile


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur, *, lat=51.11, lng=17.03, tip="", desc=""):
    return AttractionItem.model_construct(
        type=ItemType.ATTRACTION,
        poi_id=f"id-{name}",
        name=name,
        description_short=desc,
        start_time=start,
        end_time=end,
        duration_min=dur,
        lat=lat,
        lng=lng,
        address="",
        cost_estimate=0,
        pro_tip=tip or None,
    )


def _ft(start, end, dur, label="Czas dla siebie"):
    return FreeTimeItem(
        type=ItemType.FREE_TIME,
        start_time=start,
        end_time=end,
        duration_min=dur,
        label=label,
        suggestions=[],
    )


def _transit(start, end, dur, frm, to, mode, src, *, km=None):
    return TransitItem(
        type=ItemType.TRANSIT,
        start_time=start,
        end_time=end,
        duration_min=dur,
        mode=mode,
        from_location=frm,
        to_location=to,
        routing_source=src,
        distance_km=km,
    )


def test_wroclaw_daytrip_quota():
    assert city_daytrip_quota({"requested_city": "Wrocław", "num_days": 2}) == 0
    assert city_daytrip_quota({"requested_city": "Wrocław", "num_days": 3}) == 0
    assert city_daytrip_quota({"requested_city": "Wrocław", "num_days": 5}) == 1
    assert city_daytrip_quota({"requested_city": "Wrocław", "num_days": 7}) == 2
    assert city_daytrip_quota({"requested_city": "Kraków", "num_days": 3}) == 0
    assert city_daytrip_quota({"requested_city": "Kraków", "num_days": 2}) == 0
    assert city_daytrip_quota({"requested_city": "Kraków", "num_days": 5}) == 1
    assert city_daytrip_quota({"requested_city": "Kraków", "num_days": 7}) == 2
    assert city_daytrip_quota({"requested_city": "Katowice", "num_days": 2}) == 0
    assert city_daytrip_quota({"requested_city": "Katowice", "num_days": 3}) == 0
    assert city_daytrip_quota({"requested_city": "Katowice", "num_days": 5}) == 1
    assert city_daytrip_quota({"requested_city": "Katowice", "num_days": 7}) == 2


def test_two_day_wroclaw_blocks_zabkowice():
    p = {"name": "Laboratorium dr. Frankensteina", "city": "Ząbkowice Śląskie"}
    ctx = {
        "requested_city": "Wrocław",
        "num_days": 2,
        "current_day_num": 1,
        "trip_type": "city_tourism",
    }
    assert should_block_city_daytrip_poi(p, ctx) is True


def test_five_day_second_region_blocked():
    p = {"name": "Zamek Piastów Śląskich w Brzegu", "city": "Brzeg"}
    ctx = {
        "requested_city": "Wrocław",
        "num_days": 5,
        "current_day_num": 4,
        "trip_type": "city_tourism",
        "global_geo_region_use_count": {"region_wojslawice": 1},
    }
    assert should_block_city_daytrip_poi(p, ctx) is True


def test_named_duration_caps_and_floors():
    assert visit_duration_hard_cap({"name": "ZOO TEAM"}) == 60
    assert visit_duration_hard_cap({"name": "Kolejkowo"}) == 60
    assert visit_duration_hard_cap({"name": "Panorama Racławicka"}) == 30
    assert visit_duration_hard_cap({"name": "Baszta Miejska"}) == 60
    dur = choose_duration(
        {"name": "Kolejkowo", "time_min": 30, "time_max": 90, "type": "museum"},
        10 * 60,
        18 * 60,
        True,
    )
    assert dur >= 60
    dur_p = choose_duration(
        {"name": "Panorama Racławicka", "time_min": 20, "time_max": 90, "type": "museum"},
        11 * 60,
        18 * 60,
        True,
    )
    assert dur_p == 30
    dur_z = choose_duration(
        {"name": "ZOO TEAM Wrocław", "time_min": 60, "time_max": 180, "type": "activity"},
        10 * 60,
        19 * 60,
        True,
        user={"target_group": "family_kids", "children_age": 8},
    )
    assert dur_z <= 60


def test_laser_tag_denied_for_cultural_couples():
    poi = {"name": "Laser Tag Factory Wrocław", "tags": ["active_sport"]}
    user = {
        "target_group": "couples",
        "travel_style": "cultural",
        "preferences": ["museum_heritage", "relaxation", "local_food_experience"],
    }
    assert should_deny_poi_for_profile(poi, user) is True


def test_water_park_denied_for_solo_heritage():
    poi = {"name": "Słoneczny Park Wodny", "tags": ["water_park"]}
    user = {
        "target_group": "solo",
        "travel_style": "balanced",
        "preferences": ["nature_landscape", "museum_heritage", "history_mystery"],
    }
    assert should_deny_poi_for_profile(poi, user) is True


def test_winter_wyspa_tip_is_rewritten():
    desc, tip = _sanitize_winter_attraction_copy(
        "Wyspa Słodowa",
        "Letni spacer",
        "W ciepłe dni zabierz koc, znajdź cień pod drzewem i food trucki.",
        user={"start_date": "2026-02-20"},
    )
    assert "koc" not in (tip or "").lower()
    assert "food truck" not in (tip or "").lower()
    assert "zim" in (tip or "").lower()


def test_micro_walk_is_rebuilt_even_at_35_min():
    coords = {
        "izba muzealna": {"lat": 51.1100, "lng": 17.0320},
        "rynek we wrocławiu": {"lat": 51.1101, "lng": 17.0322},
    }
    items = [
        _transit(
            "17:10", "17:45", 35,
            "Izba Muzealna", "Rynek we Wrocławiu",
            TransitMode.WALK, "estimated_walk", km=0.038,
        ),
    ]
    out = _svc()._sanitize_walk_leg_durations(items, coords, day_num=7)
    assert out[0].duration_min <= 12


def test_iluzja_coords_match_swidnicka():
    items = [
        _attr(
            "Muzeum Świat Iluzji we Wrocławiu",
            "13:30", "14:30", 60,
            lat=51.1069, lng=17.0773,
        ),
    ]
    out = _svc()._force_known_good_poi_coords(items, day_num=2)
    assert abs(out[0].lat - 51.1070) < 0.002
    assert abs(out[0].lng - 17.0325) < 0.003


def test_short_satellite_hop_is_not_inflated_to_50_min():
    it = _transit(
        "14:00", "14:50", 50,
        "Dolina Tatarska", "Pod Łabędziem",
        TransitMode.CAR, "estimated_road", km=2.94,
    )
    out = _svc()._fix_implausible_transit_duration(it, {}, {"has_car": True})
    assert out.duration_min <= 25


def test_midday_zabkowice_hop_is_stripped_for_city():
    items = [
        _attr("Hydropolis", "09:30", "11:30", 120),
        _attr("Park Wodny Ząbkowice", "14:00", "16:00", 120, lat=50.59, lng=16.81),
        _attr("Park Mamuta", "16:30", "17:30", 60),
    ]
    # Name markers: "ząbkowice" in the water-park name.
    items[1] = _attr(
        "Park Wodny w Ząbkowicach Śląskich", "14:00", "16:00", 120,
        lat=50.59, lng=16.81,
    )
    out = _svc()._strip_mixed_opn_krakow_attractions(items, None, day_num=3)
    names = [it.name for it in out if it.type == ItemType.ATTRACTION]
    assert "Park Mamuta" in names
    assert not any("Ząbkowic" in n for n in names)


def test_early_close_runs_on_short_city_trips():
    ctx3 = {"num_days": 3, "requested_city": "Wrocław", "trip_type": "city_tourism"}
    assert _quality_first_trip(ctx3) is False
    assert _early_close_enabled(ctx3) is True
    items = [
        DayStartItem(time="10:00"),
        _attr("Hydropolis", "10:00", "12:00", 120),
        _ft("12:00", "20:00", 480),
        DayEndItem(time="20:00"),
    ]
    out, note, end = _svc()._apply_quality_first_early_close(
        items, {**ctx3, "day_end": "20:00"}, day_num=2,
    )
    assert end is not None
    last = None
    for it in out:
        tv = getattr(it, "type", None)
        if tv == ItemType.DAY_END:
            last = it.time
    assert last is not None
    assert last < "18:00"


def test_day_note_dropped_when_afternoon_pois_remain():
    items = [
        _attr("Rynek we Wrocławiu", "10:00", "12:00", 120),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="12:30",
            end_time="13:10",
            duration_min=40,
            suggestions=[],
        ),
        _attr("Bastion Sakwowy", "13:20", "14:00", 40),
        _attr("Wyspa Słodowa", "14:10", "15:00", 50),
    ]
    note = "Po lunchu zostawiamy Ci resztę dnia na odpoczynek."
    assert _day_note_matches_timeline(note, items) is None


def test_title_follows_real_attractions():
    items = [
        _ft("09:00", "11:30", 150),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="11:30",
            end_time="12:10",
            duration_min=40,
            suggestions=[],
        ),
        _attr("Muzeum Świat Iluzji we Wrocławiu", "13:30", "14:30", 60),
    ]
    title = _generate_day_title(items, 4)
    assert "Frankenstein" not in title
    assert "Iluzji" in title


def test_strip_disallowed_daytrip_on_2_day():
    items = [
        _attr(
            "Laboratorium dr. Frankensteina", "10:00", "12:00", 120,
            lat=50.59, lng=16.81,
        ),
        _attr("Krzywa Wieża w Ząbkowicach Śląskich", "12:30", "13:30", 60,
              lat=50.59, lng=16.81),
    ]
    out = _svc()._strip_disallowed_wro_daytrips(
        items,
        {"requested_city": "Wrocław", "num_days": 2, "trip_type": "city_tourism"},
        day_num=1,
    )
    assert not any(
        getattr(it, "type", None) == ItemType.ATTRACTION for it in out
    )
