"""FIX #284 — Kraków client notes: quota, mines, Wawel, Bulwary, deny."""
from __future__ import annotations

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    FreeTimeItem,
    ItemType,
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


def _attr(name, start, end, dur=60, *, lat=50.06, lng=19.94, address="Kraków"):
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
        cost_estimate=0,
    )


def test_krakow_daytrip_quota_matches_wroclaw():
    assert city_daytrip_quota({"requested_city": "Kraków", "num_days": 2}) == 0
    assert city_daytrip_quota({"requested_city": "Kraków", "num_days": 3}) == 0
    assert city_daytrip_quota({"requested_city": "Kraków", "num_days": 5}) == 1
    assert city_daytrip_quota({"requested_city": "Kraków", "num_days": 7}) == 2


def test_three_day_krakow_blocks_ojcow():
    p = {"name": "Zamek w Ojcowie", "city": "Ojców"}
    ctx = {
        "requested_city": "Kraków",
        "num_days": 3,
        "current_day_num": 2,
        "trip_type": "city_tourism",
    }
    assert should_block_city_daytrip_poi(p, ctx) is True


def test_five_day_krakow_blocks_day2_tenczyn():
    p = {"name": "Zamek Tenczyn", "city": "Rudno"}
    ctx = {
        "requested_city": "Kraków",
        "num_days": 5,
        "current_day_num": 2,
        "trip_type": "city_tourism",
    }
    assert should_block_city_daytrip_poi(p, ctx) is True
    ctx["current_day_num"] = 3
    assert should_block_city_daytrip_poi(p, ctx) is False


def test_salt_mines_are_separate_regions():
    assert poi_geo_region_key({"name": "Kopalnia Soli Wieliczka"}) == "region_wieliczka"
    assert poi_geo_region_key({"name": "Kopalnia Soli w Bochni"}) == "region_bochnia"
    assert poi_geo_region_key({"name": "Zamek Tenczyn"}) == "region_tenczyn"
    assert poi_geo_region_key({"name": "Zamek w Wiśniczu"}) == "region_wisnicz"


def test_wawel_floor_90():
    dur = choose_duration(
        {"name": "Zamek Królewski na Wawelu", "time_min": 50, "time_max": 180, "type": "landmark"},
        10 * 60,
        19 * 60,
        True,
    )
    assert dur >= 90


def test_kopiec_wandy_capped_60():
    assert visit_duration_hard_cap({"name": "Kopiec Wandy"}) == 60
    dur = choose_duration(
        {"name": "Kopiec Wandy", "time_min": 40, "time_max": 180, "type": "park"},
        9 * 60,
        21 * 60,
        True,
    )
    assert dur <= 60


def test_pilsudski_floor_45():
    dur = choose_duration(
        {"name": "Kopiec Piłsudskiego", "time_min": 20, "time_max": 90, "type": "park"},
        10 * 60,
        18 * 60,
        True,
    )
    assert dur >= 45


def test_lotnictwa_floor_75():
    dur = choose_duration(
        {"name": "Muzeum Lotnictwa Polskiego", "time_min": 40, "time_max": 120, "type": "museum"},
        10 * 60,
        18 * 60,
        True,
    )
    assert dur >= 75


def test_gojump_denied_without_active():
    poi = {"name": "GOjump Kraków"}
    relax = {
        "target_group": "solo",
        "travel_style": "relax",
        "preferences": ["nature_landscape", "relaxation"],
    }
    balanced = {
        "target_group": "couples",
        "travel_style": "balanced",
        "preferences": ["nature_landscape", "local_food_experience", "museum_heritage"],
    }
    adventure = {
        "target_group": "friends",
        "travel_style": "adventure",
        "preferences": ["active_sport", "history_mystery"],
    }
    assert should_deny_poi_for_profile(poi, relax) is True
    assert should_deny_poi_for_profile(poi, balanced) is True
    assert should_deny_poi_for_profile(poi, adventure) is False


def test_bricks_denied_without_kids():
    poi = {"name": "Bricks & Figs"}
    couples = {
        "target_group": "couples",
        "travel_style": "balanced",
        "preferences": ["nature_landscape", "museum_heritage"],
    }
    family = {
        "target_group": "family_kids",
        "travel_style": "balanced",
        "preferences": ["kids_attractions"],
    }
    assert should_deny_poi_for_profile(poi, couples) is True
    assert should_deny_poi_for_profile(poi, family) is False


def test_bulwary_normalizer_krakow_address():
    poi = normalize_poi({
        "Name": "Bulwary Wiślane",
        "City": "Kraków",
        "lat": 52.2390,
        "lng": 21.0280,
        "Address": "Wybrzeże Kościuszkowskie, 00-390 Warszawa",
    }, 0)
    assert "warszaw" not in (poi.get("address") or "").lower()
    assert "krak" in (poi.get("address") or "").lower()
    assert abs(float(poi["lat"]) - 50.0520) < 0.01


def test_bulwary_force_rewrites_warsaw_address_on_krakow_pin():
    items = [
        _attr(
            "Bulwary Wiślane",
            "11:00", "12:00", 60,
            lat=50.0528, lng=19.9356,
            address="Wybrzeże Kościuszkowskie, Warszawa",
        ),
    ]
    out = _svc()._force_known_good_poi_coords(items, day_num=1)
    assert "warszaw" not in (out[0].address or "").lower()
    assert "krak" in (out[0].address or "").lower()


def test_strip_keeps_city_on_afternoon_tenczyn():
    out = _svc()._strip_mixed_opn_krakow_attractions(
        [
            _attr("Las Wolski", "10:00", "11:30"),
            _attr("Zamek Tenczyn", "14:00", "14:30", 30),
            _attr("Muzeum Lotnictwa Polskiego", "16:00", "16:25", 25),
        ],
        None,
        2,
    )
    names = [it.name for it in out if hasattr(it, "name")]
    assert "Zamek Tenczyn" not in names
    assert "Las Wolski" in names
    assert "Muzeum Lotnictwa Polskiego" in names


def test_strip_still_keeps_morning_ojcow_day():
    out = _svc()._strip_mixed_opn_krakow_attractions(
        [
            _attr("Muzeum Galicji", "10:00", "11:00"),
            _attr("Zamek w Ojcowie", "11:48", "13:03"),
            _attr("MOCAK", "17:00", "18:00"),
        ],
        None,
        6,
    )
    names = [it.name for it in out if hasattr(it, "name")]
    assert names == ["Zamek w Ojcowie"]


def test_wawel_hill_cluster_adjacent():
    items = [
        _attr("Zamek Królewski na Wawelu", "10:00", "11:30", 90),
        _attr("Rynek Główny", "11:45", "13:00", 75),
        _attr("Katedra Wawelska", "13:15", "14:00", 45),
    ]
    out = _svc()._cluster_wawel_hill_stops(items, day_num=1)
    attrs = [it for it in out if getattr(it, "type", None) == ItemType.ATTRACTION]
    names = [it.name for it in attrs]
    wawel_i = names.index("Zamek Królewski na Wawelu")
    katedra_i = names.index("Katedra Wawelska")
    assert abs(wawel_i - katedra_i) == 1


def test_free_time_overlapping_transit_is_dropped():
    items = [
        _attr("Sukiennice", "11:00", "12:35", 95),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME,
            start_time="12:35",
            end_time="12:48",
            duration_min=13,
            label="Czas dla siebie",
            suggestions=[],
        ),
        TransitItem(
            type=ItemType.TRANSIT,
            start_time="12:35",
            end_time="12:48",
            duration_min=13,
            mode=TransitMode.WALK,
            from_location="Sukiennice",
            to_location="Wawel",
            routing_source="estimated_walk",
            distance_km=0.8,
        ),
        _attr("Zamek Królewski na Wawelu", "12:48", "14:18", 90),
    ]
    out = _svc()._remove_timeline_overlaps(items, 1)
    types = [getattr(it.type, "value", it.type) for it in out]
    assert types.count("free_time") == 0 or not any(
        getattr(it, "start_time", None) == "12:35"
        and getattr(it.type, "value", it.type) == "free_time"
        for it in out
    )
    assert any(getattr(it.type, "value", it.type) == "transit" for it in out)
