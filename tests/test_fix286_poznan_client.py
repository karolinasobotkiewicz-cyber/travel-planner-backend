"""FIX #286 — Poznań client notes: quota, regions, durations, castle pin."""
from __future__ import annotations

from app.application.services.plan_service import (
    PlanService,
    _is_puszczykowo_stop_name,
    _is_rogalin_stop_name,
    _timeline_satellite_kind,
)
from app.domain.models.plan import (
    AttractionItem,
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
    poi_geo_region_key,
    should_block_city_daytrip_poi,
    visit_duration_hard_cap,
)
from app.domain.scoring.profile_poi_rules import should_deny_poi_for_profile
from app.infrastructure.repositories.normalizer import normalize_poi


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur=60, *, lat=52.406, lng=16.925, address="Poznań", city="Poznań"):
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


def test_poznan_quota_matches_wroclaw():
    assert city_daytrip_quota({"requested_city": "Poznań", "num_days": 2}) == 0
    assert city_daytrip_quota({"requested_city": "Poznań", "num_days": 3}) == 0
    assert city_daytrip_quota({"requested_city": "Poznań", "num_days": 5}) == 1
    assert city_daytrip_quota({"requested_city": "Poznań", "num_days": 7}) == 2


def test_three_day_blocks_rogalin_and_puszczykowo():
    ctx = {
        "requested_city": "Poznań",
        "num_days": 3,
        "current_day_num": 2,
        "trip_type": "city_tourism",
        "preferences": ["kids_attractions", "nature_landscape"],
    }
    assert should_block_city_daytrip_poi(
        {"name": "Muzeum Pałac w Rogalinie", "city": "Rogalin"}, ctx,
    ) is True
    assert should_block_city_daytrip_poi(
        {"name": "Plaża miejska nad Wartą", "city": "Puszczykowo"}, ctx,
    ) is True


def test_five_day_gniezno_from_day_three():
    ctx = {
        "requested_city": "Poznań",
        "num_days": 5,
        "current_day_num": 3,
        "trip_type": "city_tourism",
        "preferences": ["nature_landscape", "museum_heritage", "history_mystery"],
    }
    gniezno = {"name": "Muzeum Początków Państwa Polskiego", "city": "Gniezno"}
    assert should_block_city_daytrip_poi(gniezno, ctx) is False
    assert should_block_city_daytrip_poi(
        gniezno, {**ctx, "current_day_num": 1},
    ) is True
    assert should_block_city_daytrip_poi(
        gniezno, {**ctx, "current_day_num": 2},
    ) is True


def test_regions_rogalin_puszczykowo():
    assert poi_geo_region_key(
        {"name": "Muzeum Pałac w Rogalinie", "city": "Rogalin"}
    ) == "region_rogalin"
    assert poi_geo_region_key(
        {"name": "Plaża miejska nad Wartą", "city": "Puszczykowo"}
    ) == "region_puszczykowo"
    assert poi_geo_region_key(
        {"name": "Plaża Malta", "city": "Poznań"}
    ) != "region_puszczykowo"
    assert _is_rogalin_stop_name("Muzeum Pałac w Rogalinie")
    assert _is_puszczykowo_stop_name("Plaża miejska nad Wartą")
    assert _timeline_satellite_kind("Muzeum Pałac w Rogalinie") == "rogalin"
    assert _timeline_satellite_kind("Plaża miejska nad Wartą") == "puszczykowo"
    assert _timeline_satellite_kind("Muzeum Początków Państwa Polskiego") == "gniezno"


def test_duration_floors_and_caps():
    assert choose_duration(
        {"name": "Palmiarnia Poznańska", "time_min": 10, "time_max": 180},
        10 * 60, 19 * 60, True,
    ) >= 60
    assert choose_duration(
        {"name": "Park Cytadela", "time_min": 15, "time_max": 180, "type": "park"},
        10 * 60, 19 * 60, True,
    ) >= 45
    assert choose_duration(
        {"name": "Szachty", "time_min": 10, "time_max": 180},
        10 * 60, 19 * 60, True,
    ) >= 45
    assert choose_duration(
        {"name": "Muzeum Początków Państwa Polskiego", "time_min": 20, "time_max": 180, "type": "museum"},
        10 * 60, 19 * 60, True,
    ) >= 75
    assert visit_duration_hard_cap({"name": "Pręgierz"}, for_scheduling=True) == 20
    assert visit_duration_hard_cap({"name": "Rezerwat Genius Loci"}, for_scheduling=True) == 75
    assert visit_duration_hard_cap(
        {"name": "Stary Rynek w Poznaniu"}, for_scheduling=True,
    ) == 75
    assert visit_duration_hard_cap(
        {"name": "Zamek Królewski", "city": "Poznań"}, for_scheduling=True,
    ) == 75
    assert visit_duration_hard_cap(
        {"name": "Zamek Królewski", "city": "Warszawa"}, for_scheduling=True,
    ) == 120


def test_poznan_castle_normalizer_not_warsaw():
    poi = normalize_poi({
        "Name": "Zamek Królewski",
        "City": "Poznań",
        "lat": 52.409141,
        "lng": 16.931046,
        "Address": "plac Zamkowy 4, 00-277 Warszawa",
        "Description_short": "Siedziba królów na placu Zamkowym w Warszawie.",
    }, 0)
    addr = (poi.get("address") or "").lower()
    assert "warszaw" not in addr
    assert "przemysł" in addr or "przemysl" in addr
    assert "warszaw" not in (poi.get("description_short") or "").lower()
    assert "poznań" in (poi.get("city") or "").lower() or "poznan" in (poi.get("city") or "").lower()


def test_warsaw_castle_row_unchanged():
    poi = normalize_poi({
        "Name": "Zamek Królewski",
        "City": "Warszawa",
        "lat": 52.2478,
        "lng": 21.0145,
        "Address": "plac Zamkowy 4, 00-277 Warszawa",
    }, 0)
    assert "warszaw" in (poi.get("address") or "").lower() or "zamkowy" in (poi.get("address") or "").lower()
    assert abs(float(poi["lng"]) - 21.0145) < 0.02


def test_force_poznan_castle_address():
    item = _attr(
        "Zamek Królewski",
        "10:00",
        "11:00",
        60,
        lat=52.409141,
        lng=16.931046,
        address="plac Zamkowy 4, 00-277 Warszawa",
        city="Poznań",
    )
    item = item.model_copy(update={
        "description_short": "Zamek na placu Zamkowym w Warszawie.",
    })
    out = _svc()._force_known_good_poi_coords([item], day_num=1)
    assert "warszaw" not in (out[0].address or "").lower()
    assert "przemysł" in (out[0].address or "").lower() or "przemysl" in (out[0].address or "").lower()


def test_force_warsaw_castle_kept():
    item = _attr(
        "Zamek Królewski",
        "10:00",
        "12:00",
        120,
        lat=52.2478,
        lng=21.0145,
        address="plac Zamkowy 4, 00-277 Warszawa",
        city="Warszawa",
    )
    out = _svc()._force_known_good_poi_coords([item], day_num=1)
    assert abs(float(out[0].lng) - 21.0145) < 0.02
    assert "warszaw" in (out[0].address or "").lower() or "zamkowy" in (out[0].address or "").lower()


def test_cesarski_denied_for_water_food_relax():
    assert should_deny_poi_for_profile(
        {"name": "Zamek Cesarski"},
        {
            "target_group": "couples",
            "travel_style": "relax",
            "preferences": [
                "water_attractions", "local_food_experience", "relaxation",
            ],
        },
    ) is True


def test_bazylika_denied_for_friends_adventure():
    assert should_deny_poi_for_profile(
        {"name": "Bazylika Archikatedralna"},
        {
            "target_group": "friends",
            "travel_style": "adventure",
            "preferences": ["active_sport", "history_mystery"],
        },
    ) is True


def test_parks_denied_on_underground_history_day():
    assert should_deny_poi_for_profile(
        {"name": "Park Wilsona"},
        {
            "target_group": "friends",
            "travel_style": "adventure",
            "preferences": ["underground", "history_mystery", "museum_heritage"],
        },
    ) is True


def test_cluster_ratusz_and_stary_rynek():
    items = [
        _attr("Ratusz w Poznaniu", "10:00", "11:00", 60),
        _attr("Muzeum Narodowe", "11:10", "13:10", 120),
        _attr("Stary Rynek w Poznaniu", "13:20", "14:55", 95),
    ]
    out = _svc()._cluster_poznan_old_town_stops(items, day_num=1)
    names = [it.name for it in out if getattr(it, "name", None)]
    r_i = names.index("Ratusz w Poznaniu")
    s_i = names.index("Stary Rynek w Poznaniu")
    assert abs(r_i - s_i) == 1


def test_lunch_transit_overlap_shifts_transit():
    items = [
        TransitItem(
            type=ItemType.TRANSIT,
            start_time="13:14",
            end_time="14:09",
            duration_min=55,
            mode=TransitMode.CAR,
            from_location="Plaża miejska nad Wartą",
            to_location="NOOKS",
            routing_source="estimated_road",
            distance_km=18.0,
        ),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="13:14",
            end_time="14:14",
            duration_min=60,
            label="Lunch",
            suggestions=[],
        ),
    ]
    out = _svc()._remove_timeline_overlaps(items, 2)
    lunch = next(it for it in out if getattr(it.type, "value", it.type) == "lunch_break")
    transit = next(it for it in out if getattr(it.type, "value", it.type) == "transit")
    assert lunch.start_time == "13:14"
    assert transit.end_time <= lunch.start_time


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
            suggestions=["Śniadanie kawowe w okolicy"],
        ),
    ]
    out = _svc()._remove_timeline_overlaps(items, 3)
    ft = next(it for it in out if getattr(it.type, "value", it.type) == "free_time")
    tr = next(it for it in out if getattr(it.type, "value", it.type) == "transit")
    assert ft.end_time <= tr.start_time or ft.start_time >= tr.end_time


def test_meal_label_follows_primary_suggestion():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="13:00",
        end_time="14:00",
        duration_min=60,
        label="Lavenda",
        suggestions=[
            RestaurantSuggestion.model_construct(
                id="r1",
                name="Just Friends",
                lat=52.4,
                lng=16.9,
            ),
        ],
    )
    transit = TransitItem(
        type=ItemType.TRANSIT,
        start_time="12:20",
        end_time="13:00",
        duration_min=40,
        mode=TransitMode.WALK,
        from_location="Stary Rynek",
        to_location="Lavenda",
        routing_source="estimated_walk",
        distance_km=0.8,
    )
    out = _svc()._sync_meal_label_to_primary([transit, lunch], day_num=1)
    meal = next(it for it in out if getattr(it.type, "value", it.type) == "lunch_break")
    hop = next(it for it in out if getattr(it.type, "value", it.type) == "transit")
    assert meal.label == "Just Friends"
    assert hop.to_location == "Just Friends"


def test_duplicate_plaza_nooks_leg_dropped():
    a = TransitItem(
        type=ItemType.TRANSIT,
        start_time="13:14",
        end_time="14:09",
        duration_min=55,
        mode=TransitMode.CAR,
        from_location="Plaża miejska nad Wartą",
        to_location="NOOKS",
        routing_source="estimated_road",
        distance_km=18.0,
    )
    b = TransitItem(
        type=ItemType.TRANSIT,
        start_time="13:52",
        end_time="14:47",
        duration_min=55,
        mode=TransitMode.CAR,
        from_location="Plaża miejska nad Wartą",
        to_location="NOOKS",
        routing_source="estimated_road",
        distance_km=18.0,
    )
    out = _svc()._strip_duplicate_same_leg([a, b], day_num=3)
    legs = [it for it in out if getattr(it.type, "value", it.type) == "transit"]
    assert len(legs) == 1


def test_strip_cytadela_wilson_same_day():
    out = _svc()._strip_similar_poznan_parks(
        [
            _attr("Park Cytadela", "10:00", "11:00", 60),
            _attr("Park Wilsona", "11:20", "12:20", 60),
        ],
        {"target_group": "couples", "travel_style": "cultural",
         "preferences": ["museum_heritage", "relaxation"]},
        day_num=2,
    )
    names = [it.name for it in out]
    assert "Park Cytadela" in names
    assert "Park Wilsona" not in names


def test_seven_day_restaurant_swaps_repeat():
    nooks = RestaurantSuggestion.model_construct(
        id="r1", name="NOOKS", lat=52.4, lng=16.9,
    )
    other = RestaurantSuggestion.model_construct(
        id="r2", name="Just Friends", lat=52.4, lng=16.93,
    )
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="13:00",
        end_time="14:00",
        duration_min=60,
        label="NOOKS",
        suggestions=[nooks, other],
    )
    ctx = {
        "num_days": 7,
        "trip_used_restaurants": set(),
        "trip_restaurant_counts": {"nooks": 1},
        "restaurants_available": [],
    }
    out = _svc()._diversify_meal_suggestions([lunch], ctx, day_num=3)
    meal = out[0]
    assert meal.suggestions[0].name == "Just Friends"
