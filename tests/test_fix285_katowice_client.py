"""FIX #285 — Katowice client notes: quota, mines, Wedel, deny, overlaps."""
from __future__ import annotations

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    FreeTimeItem,
    ItemType,
    LunchBreakItem,
    TransitItem,
    TransitMode,
)
from app.domain.planner.engine import (
    choose_duration,
    city_daytrip_quota,
    poi_geo_region_key,
    should_block_city_daytrip_poi,
    should_skip_poi_candidate,
)
from app.domain.scoring.profile_poi_rules import should_deny_poi_for_profile
from app.infrastructure.repositories.normalizer import normalize_poi


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur=60, *, lat=50.26, lng=19.02, address="Katowice", city="Katowice"):
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


def test_katowice_quota_matches_wroclaw():
    assert city_daytrip_quota({"requested_city": "Katowice", "num_days": 2}) == 0
    assert city_daytrip_quota({"requested_city": "Katowice", "num_days": 3}) == 0
    assert city_daytrip_quota({"requested_city": "Katowice", "num_days": 5}) == 1
    assert city_daytrip_quota({"requested_city": "Katowice", "num_days": 7}) == 2


def test_three_day_blocks_gliwice_kolejkowo():
    ctx = {
        "requested_city": "Katowice",
        "num_days": 3,
        "current_day_num": 2,
        "trip_type": "city_tourism",
        "preferences": ["kids_attractions", "nature_landscape"],
    }
    assert should_block_city_daytrip_poi(
        {"name": "Kolejkowo", "city": "Gliwice"}, ctx,
    ) is True
    assert should_block_city_daytrip_poi(
        {"name": "Park Chopina", "city": "Gliwice"}, ctx,
    ) is True


def test_two_day_allows_guido_when_underground():
    ctx = {
        "requested_city": "Katowice",
        "num_days": 2,
        "current_day_num": 2,
        "trip_type": "cluster",
        "preferences": ["underground", "history_mystery", "museum_heritage"],
    }
    assert should_block_city_daytrip_poi(
        {"name": "Kopalnia Guido", "city": "Zabrze"}, ctx,
    ) is False
    assert should_block_city_daytrip_poi(
        {"name": "Kopalnia Guido", "city": "Zabrze"},
        {**ctx, "current_day_num": 1},
    ) is True


def test_two_day_tychy_only_with_water():
    base = {
        "requested_city": "Katowice",
        "num_days": 2,
        "current_day_num": 2,
        "trip_type": "cluster",
    }
    tychy = {"name": "Wodny Park Tychy", "city": "Tychy"}
    assert should_block_city_daytrip_poi(
        tychy, {**base, "preferences": ["kids_attractions", "relaxation"]},
    ) is True
    assert should_block_city_daytrip_poi(
        tychy, {**base, "preferences": ["water_attractions", "relaxation"]},
    ) is False


def test_regions_split_silesia():
    assert poi_geo_region_key({"name": "Kolejkowo", "city": "Katowice"}) == "region_gliwice"
    assert poi_geo_region_key({"name": "Kopalnia Guido", "city": "Katowice"}) == "region_zabrze"
    assert poi_geo_region_key({"name": "Willa Caro"}) == "region_gliwice"
    assert poi_geo_region_key({"name": "Wodny Park Tychy", "city": "Tychy"}) == "region_tychy"
    assert poi_geo_region_key({"name": "Park Wodny Nemo"}) == "region_dabrowa"


def test_muzeum_slaskie_floor_75():
    dur = choose_duration(
        {"name": "Muzeum Śląskie", "time_min": 25, "time_max": 180, "type": "museum"},
        10 * 60,
        19 * 60,
        True,
    )
    assert dur >= 75


def test_guido_floor_90():
    dur = choose_duration(
        {"name": "Kopalnia Guido", "time_min": 40, "time_max": 180, "type": "museum"},
        9 * 60,
        19 * 60,
        True,
    )
    assert dur >= 90


def test_willa_caro_and_guliwer_floors():
    assert choose_duration(
        {"name": "Muzeum Willa Caro", "time_min": 20, "time_max": 90, "type": "museum"},
        10 * 60, 18 * 60, True,
    ) >= 45
    assert choose_duration(
        {"name": "Centrum Rozrywki Guliwer", "time_min": 20, "time_max": 90, "type": "attraction"},
        10 * 60, 16 * 60, True,
    ) >= 60


def test_funzeum_denied_for_adults():
    poi = {"name": "Funzeum - Centrum Dziecięcej Wyobraźni"}
    couples = {
        "target_group": "couples",
        "travel_style": "cultural",
        "preferences": ["museum_heritage", "relaxation"],
    }
    family = {
        "target_group": "family_kids",
        "travel_style": "balanced",
        "preferences": ["kids_attractions"],
    }
    assert should_deny_poi_for_profile(poi, couples) is True
    assert should_deny_poi_for_profile(poi, family) is False
    assert should_deny_poi_for_profile(
        {"name": "FunHouse – Interaktywne Muzeum Flipperów"},
        {
            "target_group": "solo",
            "travel_style": "relax",
            "preferences": ["nature_landscape", "relaxation"],
        },
    ) is True


def test_papugarnia_and_aquapark_and_luiza_denies():
    couples = {
        "target_group": "couples",
        "travel_style": "cultural",
        "preferences": ["museum_heritage", "relaxation", "local_food_experience"],
    }
    assert should_deny_poi_for_profile({"name": "Papugarnia Carmen"}, couples) is True
    assert should_deny_poi_for_profile(
        {"name": "Wodny Park Tychy"},
        {
            "target_group": "couples",
            "travel_style": "balanced",
            "preferences": ["nature_landscape", "museum_heritage"],
        },
    ) is True
    assert should_deny_poi_for_profile(
        {"name": "Sztolnia Królowa Luiza"},
        {
            "target_group": "couples",
            "travel_style": "balanced",
            "preferences": ["mountain_trails", "nature_landscape"],
        },
    ) is True
    assert should_deny_poi_for_profile(
        {"name": "Kopalnia Guido"},
        {
            "target_group": "family_kids",
            "travel_style": "relax",
            "preferences": ["kids_attractions"],
        },
    ) is True


def test_muzeum_slaskie_off_family_relax():
    assert should_deny_poi_for_profile(
        {"name": "Muzeum Śląskie"},
        {
            "target_group": "family_kids",
            "travel_style": "relax",
            "preferences": ["kids_attractions", "relaxation"],
        },
    ) is True


def test_skip_warsaw_wedel_on_katowice_trip():
    ctx = {"requested_city": "Katowice", "num_days": 3}
    assert should_skip_poi_candidate(
        {
            "name": "Pijalnia Czekolady E.Wedel",
            "city": "Warszawa",
            "lat": 52.2465,
            "lng": 21.0509,
        },
        ctx,
    ) is True
    assert should_skip_poi_candidate(
        {
            "name": "Pijalnia Czekolady E.Wedel",
            "city": "Katowice",
            "lat": 50.2587,
            "lng": 19.0180,
        },
        ctx,
    ) is False


def test_wedel_normalizer_katowice_pin():
    poi = normalize_poi({
        "Name": "Pijalnia Czekolady E.Wedel",
        "City": "Katowice",
        "lat": 52.2465,
        "lng": 21.0509,
        "Address": "aleja Wedla 5, 03-822 Warszawa",
    }, 0)
    assert "warszaw" not in (poi.get("address") or "").lower()
    assert "katowic" in (poi.get("address") or "").lower()
    assert abs(float(poi["lat"]) - 50.2584) < 0.01


def test_strip_second_water_same_day():
    out = _svc()._strip_extra_water_parks(
        [
            _attr("Park Wodny Nemo", "11:00", "13:00", 120),
            _attr("Wodny Park Tychy", "15:00", "16:30", 90, city="Tychy"),
        ],
        {},
        day_num=1,
    )
    names = [it.name for it in out]
    assert "Park Wodny Nemo" in names
    assert "Wodny Park Tychy" not in names


def test_strip_guido_keeps_one_mine():
    out = _svc()._strip_guido_luiza_same_day(
        [
            _attr("Kopalnia Guido", "10:00", "12:00", 120, city="Zabrze"),
            _attr("Sztolnia Królowa Luiza", "13:00", "15:00", 120, city="Zabrze"),
        ],
        day_num=2,
    )
    names = [it.name for it in out]
    assert "Kopalnia Guido" in names
    assert "Sztolnia Królowa Luiza" not in names


def test_strip_third_green():
    out = _svc()._strip_excess_green_stops(
        [
            _attr("Park Śląski", "10:00", "11:00", 60),
            _attr("Dolina Trzech Stawów", "11:30", "12:30", 60),
            _attr("Park Kościuszki", "13:00", "14:00", 60),
        ],
        day_num=1,
    )
    names = [it.name for it in out]
    assert len([n for n in names if "Park" in n or "Dolina" in n]) == 2


def test_lunch_transit_overlap_shifts_transit():
    items = [
        TransitItem(
            type=ItemType.TRANSIT,
            start_time="12:14",
            end_time="12:54",
            duration_min=40,
            mode=TransitMode.CAR,
            from_location="Spodek",
            to_location="Restauracja",
            routing_source="estimated_road",
            distance_km=5.1,
        ),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="12:14",
            end_time="12:54",
            duration_min=40,
            label="Lunch",
            suggestions=[],
        ),
    ]
    out = _svc()._remove_timeline_overlaps(items, 3)
    lunch = next(it for it in out if getattr(it.type, "value", it.type) == "lunch_break")
    transit = next(it for it in out if getattr(it.type, "value", it.type) == "transit")
    assert lunch.start_time == "12:14"
    assert transit.end_time <= lunch.start_time
