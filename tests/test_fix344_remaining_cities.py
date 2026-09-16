"""FIX #344 — remaining cities get Wrocław-style centres, satellites, hop caps."""
from __future__ import annotations

from app.application.services.plan_service import (
    _capped_named_hop_minutes,
    _city_center_coords,
)
from app.domain.planner.city_copy import (
    hub_poi_load_cities,
    hub_restaurant_cities,
    is_city_tourism_trip,
    wroclaw_poi_load_cities,
)
from app.domain.planner.engine import city_daytrip_quota


def test_wroclaw_load_list_unchanged():
    wro = wroclaw_poi_load_cities("Wrocław")
    assert wro[0] == "Wrocław"
    assert "Oława" in wro and "Niemcza" in wro
    assert wroclaw_poi_load_cities("Kraków") == ["Kraków"]
    assert "Oława" in hub_poi_load_cities("Wrocław")


def test_zakopane_stays_out_of_city_tourism():
    assert not is_city_tourism_trip(
        {"is_zakopane_trip": True, "requested_city": "Zakopane"}
    )
    assert city_daytrip_quota(
        {"is_zakopane_trip": True, "requested_city": "Zakopane", "num_days": 5}
    ) == 99


def test_hub_satellites_and_restaurants():
    kat = hub_poi_load_cities("Katowice")
    assert "Gliwice" in kat and "Zabrze" in kat
    gdn = hub_poi_load_cities("Gdańsk")
    assert "Gdynia" in gdn and "Sopot" in gdn
    assert "Sopot" in hub_restaurant_cities("Gdańsk")
    assert "Gliwice" in hub_restaurant_cities("Katowice")
    kar = hub_poi_load_cities("Karpacz")
    assert "Jelenia Góra" in kar and "Szklarska Poręba" in kar
    kld = hub_poi_load_cities("Kłodzko")
    assert "Kudowa-Zdrój" in kld and "Polanica-Zdrój" in kld
    assert "Wieliczka" in hub_poi_load_cities("Kraków")


def test_city_centres_cover_remaining_hubs():
    assert _city_center_coords("Gdynia") == (54.5189, 18.5305)
    assert _city_center_coords("Sopot")
    assert _city_center_coords("Karpacz")
    assert _city_center_coords("Szklarska Poręba")
    assert _city_center_coords("Jelenia Góra")
    assert _city_center_coords("Kłodzko")
    assert _city_center_coords("Kudowa-Zdrój")
    assert _city_center_coords("Polanica-Zdrój")
    assert _city_center_coords("Wrocław") == (51.1079, 17.0385)


def test_named_hop_caps_other_cities_keep_olawa():
    assert _capped_named_hop_minutes("Wrocław", "Rynek w Oławie", 26.0, 8) == 30
    assert _capped_named_hop_minutes("Kraków", "Kopalnia Soli Wieliczka", 14.0, 8) == 25
    assert _capped_named_hop_minutes("Poznań", "Katedra w Gnieźnie", 50.0, 10) == 40
    assert _capped_named_hop_minutes("Katowice", "Kopalnia Guido", 20.0, 7) == 25
    assert _capped_named_hop_minutes("Warszawa", "Puszcza Kampinoska", 30.0, 9) == 40
    assert _capped_named_hop_minutes("Rynek", "Sukiennice", 0.8, 12) == 12


def test_trojmiasto_quota_matches_wroclaw():
    for city in ("Gdańsk", "Gdynia", "Sopot"):
        assert city_daytrip_quota({"requested_city": city, "num_days": 2}) == 0
        assert city_daytrip_quota({"requested_city": city, "num_days": 3}) == 0
        assert city_daytrip_quota({"requested_city": city, "num_days": 5}) == 1
        assert city_daytrip_quota({"requested_city": city, "num_days": 7}) == 2
    assert city_daytrip_quota({"requested_city": "Wrocław", "num_days": 3}) == 0
    assert city_daytrip_quota({"requested_city": "Karpacz", "num_days": 3}) == 99
    assert is_city_tourism_trip({"requested_city": "Gdynia"})
    assert is_city_tourism_trip({"requested_city": "Sopot"})
    assert not is_city_tourism_trip({"requested_city": "Karpacz"})


def test_tyskie_is_tychy_satellite():
    from app.application.services.plan_service import _timeline_satellite_kind
    from app.domain.planner.engine import poi_geo_region_key, should_block_city_daytrip_poi

    assert _timeline_satellite_kind("Tyskie Browary Książęce") == "tychy"
    assert poi_geo_region_key({"name": "Tyskie Browary Książęce", "city": "Katowice"}) == "region_tychy"
    ctx3 = {
        "requested_city": "Katowice",
        "num_days": 3,
        "current_day_num": 2,
        "trip_type": "city_tourism",
    }
    assert should_block_city_daytrip_poi(
        {"name": "Tyskie Browary Książęce", "city": "Katowice", "lat": 50.123, "lng": 18.986},
        ctx3,
    ) is True


def test_wieliczka_lunch_after_hub_return_is_dropped():
    from app.application.services.plan_service import PlanService
    from app.domain.models.plan import (
        AttractionItem,
        DayEndItem,
        DayStartItem,
        ItemType,
        LunchBreakItem,
        RestaurantSuggestion,
        TransitItem,
        TransitMode,
    )
    from app.infrastructure.repositories.poi_repository import POIRepository

    svc = PlanService(POIRepository("data/zakopane.xlsx"))
    wiel = (49.983, 20.064)
    rynek = (50.0617, 19.9373)
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION,
            poi_id="poi-wiel",
            name="Kopalnia Soli Wieliczka",
            description_short="Opis",
            why_selected=["bo warto"],
            start_time="10:00",
            end_time="12:00",
            duration_min=120,
            lat=wiel[0],
            lng=wiel[1],
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT,
            from_location="Kopalnia Soli Wieliczka",
            to_location="Kraków centrum",
            start_time="12:00",
            end_time="12:40",
            duration_min=40,
            distance_km=14.0,
            mode=TransitMode.CAR,
            routing_source="estimated_road",
        ),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="13:00",
            end_time="13:45",
            duration_min=45,
            label="Sztolnia Wieliczka",
            suggestions=[RestaurantSuggestion.model_construct(
                id="r-sztolnia", name="Sztolnia Wieliczka",
                lat=wiel[0], lng=wiel[1],
                city="Wieliczka", address="Daniłowicza",
            )],
        ),
        DayEndItem(time="20:00"),
    ]
    out = svc._strip_satellite_meals_on_city_days(items, day_num=5)
    meals = [
        it for it in out
        if str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "lunch_break"
    ]
    assert meals == [], [getattr(m, "label", None) for m in meals]


def test_other_hub_coord_far_skips_wroclaw():
    from app.domain.planner.engine import _other_hub_coord_far, should_block_city_daytrip_poi

    far_unnamed = {"name": "Pole", "lat": 50.0647, "lng": 20.45}
    assert _other_hub_coord_far(far_unnamed, {"requested_city": "Wrocław"}) is False
    assert _other_hub_coord_far(far_unnamed, {"requested_city": "Kraków"}) is True
    assert should_block_city_daytrip_poi(
        far_unnamed,
        {
            "requested_city": "Kraków",
            "num_days": 3,
            "current_day_num": 2,
            "trip_type": "city_tourism",
        },
    ) is True


def test_locked_city_helper():
    from app.application.services.plan_service import _is_locked_city_context

    assert _is_locked_city_context({"requested_city": "Wrocław"})
    assert _is_locked_city_context({"is_zakopane_trip": True, "requested_city": "Zakopane"})
    assert not _is_locked_city_context({"requested_city": "Kraków"})
    assert not _is_locked_city_context({"requested_city": "Katowice"})


def test_far_meal_hop_inserted_for_krakow_not_wroclaw():
    from app.application.services.plan_service import PlanService
    from app.domain.models.plan import (
        AttractionItem,
        DayEndItem,
        DayStartItem,
        ItemType,
        LunchBreakItem,
        RestaurantSuggestion,
    )
    from app.infrastructure.repositories.poi_repository import POIRepository

    svc = PlanService(POIRepository("data/zakopane.xlsx"))
    ojcow = (50.212, 19.829)
    milk = (50.061, 19.937)
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION,
            poi_id="poi-maczuga",
            name="Maczuga Herkulesa",
            description_short="Opis",
            why_selected=["bo warto"],
            start_time="10:00",
            end_time="11:00",
            duration_min=60,
            lat=ojcow[0],
            lng=ojcow[1],
        ),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="12:00",
            end_time="12:45",
            duration_min=45,
            label="Milkbar Tomasza",
            suggestions=[RestaurantSuggestion.model_construct(
                id="r-milk", name="Milkbar Tomasza",
                lat=milk[0], lng=milk[1],
                city="Kraków", address="Tomasza",
            )],
        ),
        DayEndItem(time="20:00"),
    ]
    krk = svc._ensure_stop_to_stop_legs(
        items, {}, {"requested_city": "Kraków", "has_car": True}, day_num=6,
    )
    hops = [
        it for it in krk
        if str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "transit"
    ]
    assert hops, "Kraków should plant the 23 km lunch hop"
    wro = svc._ensure_stop_to_stop_legs(
        items, {}, {"requested_city": "Wrocław", "has_car": True}, day_num=6,
    )
    wro_hops = [
        it for it in wro
        if str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "transit"
    ]
    assert not wro_hops, "Wrocław keeps the 12 km meal-hop skip"


def test_mixed_gliwice_zabrze_keeps_one():
    from app.application.services.plan_service import PlanService
    from app.domain.models.plan import AttractionItem, DayEndItem, DayStartItem, ItemType
    from app.infrastructure.repositories.poi_repository import POIRepository

    svc = PlanService(POIRepository("data/zakopane.xlsx"))
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="g1", name="Willa Caro",
            description_short="", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=50.294, lng=18.665,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="g2", name="Palmiarnia Miejska",
            description_short="", why_selected=["x"],
            start_time="11:15", end_time="12:00", duration_min=45,
            lat=50.297, lng=18.666,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="z1", name="Kopalnia Guido",
            description_short="", why_selected=["x"],
            start_time="13:00", end_time="15:00", duration_min=120,
            lat=50.297, lng=18.786,
        ),
        DayEndItem(time="20:00"),
    ]
    out = svc._drop_extra_satellite_kinds(items, day_num=3)
    names = [getattr(it, "name", "") for it in out if getattr(it, "name", None)]
    assert "Kopalnia Guido" not in names
    assert "Willa Caro" in names


def _svc344():
    from app.application.services.plan_service import PlanService
    from app.infrastructure.repositories.poi_repository import POIRepository
    return PlanService(POIRepository("data/zakopane.xlsx"))


def test_katowice_empty_afternoon_closes_and_badges():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, FreeTimeItem, ItemType,
    )
    from app.domain.planner.time_utils import time_to_minutes

    svc = _svc344()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="k1", name="Spodek",
            description_short="", why_selected=["x"],
            start_time="10:00", end_time="13:47", duration_min=227,
            lat=50.266, lng=19.023,
        ),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME,
            start_time="13:47", end_time="17:47", duration_min=240,
            label="Popołudniowa przerwa",
        ),
        DayEndItem(time="20:00"),
    ]
    ctx = {"requested_city": "Katowice", "day_end": "20:00", "day_start": "09:00"}
    out, exhausted = svc._close_day_when_nothing_left(items, ctx, day_num=6)
    assert exhausted is True
    last = max(
        time_to_minutes(getattr(it, "end_time", None) or getattr(it, "time", "") or "00:00")
        for it in out
        if str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        != "free_time"
    )
    assert last <= 14 * 60
    wro, wro_ex = svc._close_day_when_nothing_left(
        items, {"requested_city": "Wrocław", "day_end": "20:00"}, day_num=6,
    )
    assert wro_ex is False
    assert any(
        str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "free_time"
        for it in wro
    )


def test_chain_overlapping_hops_katowice():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )
    from app.domain.planner.time_utils import time_to_minutes

    svc = _svc344()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Nikiszowiec",
            description_short="", why_selected=["x"],
            start_time="09:15", end_time="10:50", duration_min=95,
            lat=50.244, lng=19.081,
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="10:58", end_time="11:43",
            duration_min=45, from_location="Nikiszowiec", to_location="Spodek",
            mode=TransitMode.CAR,
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:40", end_time="12:08",
            duration_min=28, from_location="Nikiszowiec", to_location="Muzeum Śląskie",
            mode=TransitMode.CAR,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Muzeum Śląskie",
            description_short="", why_selected=["x"],
            start_time="12:08", end_time="13:30", duration_min=82,
            lat=50.261, lng=19.035,
        ),
        DayEndItem(time="20:00"),
    ]
    out = svc._chain_overlapping_hops(items, day_num=7)
    hops = [
        it for it in out
        if str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "transit"
    ]
    assert len(hops) == 2
    a_en = time_to_minutes(hops[0].end_time)
    b_st = time_to_minutes(hops[1].start_time)
    assert b_st >= a_en


def test_shrink_and_trim_free_time_over_sixty():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, FreeTimeItem, ItemType,
    )
    from app.domain.planner.time_utils import time_to_minutes
    from app.domain.validators.client_invariants import LONG_FREE_TIME_MIN, audit_day

    svc = _svc344()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Zamek Królewski",
            description_short="", why_selected=["x"],
            start_time="10:00", end_time="18:51", duration_min=531,
            lat=52.248, lng=21.015,
        ),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME,
            start_time="18:51", end_time="20:00", duration_min=69,
            label="Czas wolny",
        ),
        DayEndItem(time="20:00"),
    ]
    ctx = {"requested_city": "Warszawa", "day_end": "20:00", "day_start": "09:00"}
    out = svc._trim_tail_long_free_time(items, ctx, day_num=1, min_span=61)
    assert not any(
        str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "free_time"
        for it in out
    )
    mid = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Stary Rynek",
            description_short="", why_selected=["x"],
            start_time="09:30", end_time="11:00", duration_min=90,
            lat=52.408, lng=16.935,
        ),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME,
            start_time="11:00", end_time="12:08", duration_min=68,
            label="Przerwa",
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Ostrów Tumski",
            description_short="", why_selected=["x"],
            start_time="12:08", end_time="13:30", duration_min=82,
            lat=52.411, lng=16.948,
        ),
        DayEndItem(time="20:00"),
    ]
    shrunk = svc._shrink_free_time_over_sixty(mid, ctx, day_num=4)
    fts = [
        it for it in shrunk
        if str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "free_time"
    ]
    assert fts
    span = time_to_minutes(fts[0].end_time) - time_to_minutes(fts[0].start_time)
    assert span <= LONG_FREE_TIME_MIN
    codes = {d.code for d in audit_day(shrunk, day=4, context=ctx)}
    assert "long_free_time" not in codes


def test_close_micro_gaps_after_day_start():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, FreeTimeItem, ItemType,
        TransitItem, TransitMode,
    )
    from app.domain.validators.client_invariants import audit_day

    svc = _svc344()
    items = [
        DayStartItem(time="09:00"),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="09:05", end_time="09:15",
            duration_min=10, from_location="Poznań", to_location="Stary Rynek",
            mode=TransitMode.WALK,
        ),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME,
            start_time="09:18", end_time="09:25", duration_min=7,
            label="Bufor",
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Stary Rynek",
            description_short="", why_selected=["x"],
            start_time="09:29", end_time="11:00", duration_min=91,
            lat=52.408, lng=16.935,
        ),
        DayEndItem(time="20:00"),
    ]
    out = svc._close_micro_gaps(items, day_num=2)
    out = svc._collapse_sliver_runs(out, day_num=2)
    ctx = {"requested_city": "Poznań", "day_end": "20:00", "day_start": "09:00"}
    out = svc._glue_leading_technical_blocks(out, ctx, day_num=2)
    codes = {d.code for d in audit_day(out, day=2, context=ctx)}
    assert "fragmented" not in codes


def test_guliwer_dropped_for_couples_even_without_meta():
    from app.domain.models.plan import AttractionItem, DayEndItem, DayStartItem, ItemType

    svc = _svc344()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="g", name="Centrum Rozrywki Guliwer",
            description_short="", why_selected=["x"],
            start_time="10:13", end_time="11:25", duration_min=72,
            lat=50.26, lng=19.02,
        ),
        DayEndItem(time="20:00"),
    ]
    out = svc._drop_kids_only_for_adults(
        items, {"requested_city": "Katowice", "group_type": "couples"}, day_num=3,
    )
    names = [getattr(it, "name", "") for it in out]
    assert "Centrum Rozrywki Guliwer" not in names
    family = svc._drop_kids_only_for_adults(
        items, {"requested_city": "Katowice", "group_type": "family_kids"}, day_num=3,
    )
    assert any("Guliwer" in (getattr(it, "name", "") or "") for it in family)


def test_identical_clock_hops_are_deduped():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )
    from app.domain.planner.time_utils import time_to_minutes

    svc = _svc344()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Kopalnia Soli Wieliczka",
            description_short="", why_selected=["x"],
            start_time="10:00", end_time="15:21", duration_min=321,
            lat=49.983, lng=20.064,
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="15:21", end_time="16:01",
            duration_min=40, from_location="Kopalnia Soli Wieliczka",
            to_location="Kraków centrum", mode=TransitMode.CAR,
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="15:21", end_time="16:01",
            duration_min=40, from_location="Kopalnia Soli Wieliczka",
            to_location="Milkbar Tomasza", mode=TransitMode.CAR,
        ),
        DayEndItem(time="20:00"),
    ]
    out = svc._dedupe_parallel_hops(items, day_num=5)
    hops = [
        it for it in out
        if str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "transit"
    ]
    assert len(hops) == 1
    rewritten = svc._rewrite_hop_origins(out, day_num=5)
    # last occupied before the surviving hop is Wieliczka — origin stays
    assert hops[0].start_time == "15:21"
    codes_times = [
        (time_to_minutes(h.start_time), time_to_minutes(h.end_time)) for h in hops
    ]
    assert len(set(codes_times)) == 1
    _ = rewritten


def test_dangling_keeps_hub_return():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc344()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="g", name="Kopalnia Guido",
            description_short="", why_selected=["x"],
            start_time="10:00", end_time="13:00", duration_min=180,
            lat=50.297, lng=18.786,
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="13:00", end_time="13:30",
            duration_min=30, from_location="Kopalnia Guido",
            to_location="Katowice centrum", mode=TransitMode.CAR,
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="13:30", end_time="14:13",
            duration_min=43, from_location="Katowice centrum",
            to_location="Kresowe Smaki", mode=TransitMode.CAR,
        ),
        DayEndItem(time="20:00"),
    ]
    out = svc._drop_dangling_end_hops(
        items, {"requested_city": "Katowice", "day_end": "20:00"},
        day_num=7, any_dangling=True,
    )
    dests = [
        getattr(it, "to_location", "") for it in out
        if str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "transit"
    ]
    assert "Katowice centrum" in dests
    assert "Kresowe Smaki" not in dests


def test_pad_pregierz_breaks_sliver_run():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )
    from app.domain.validators.client_invariants import audit_day

    svc = _svc344()
    items = [
        DayStartItem(time="09:00"),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="09:00", end_time="09:11",
            duration_min=11, from_location="Poznań", to_location="Pręgierz",
            mode=TransitMode.WALK,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="p", name="Pręgierz",
            description_short="", why_selected=["x"],
            start_time="09:11", end_time="09:18", duration_min=7,
            lat=52.408, lng=16.935,
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="09:18", end_time="09:29",
            duration_min=11, from_location="Pręgierz", to_location="Park Jana Pawła II",
            mode=TransitMode.WALK,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Park Jana Pawła II",
            description_short="", why_selected=["x"],
            start_time="09:29", end_time="10:04", duration_min=35,
            lat=52.41, lng=16.93,
        ),
        DayEndItem(time="20:00"),
    ]
    ctx = {"requested_city": "Poznań", "day_end": "20:00", "day_start": "09:00"}
    assert any(d.code == "fragmented" for d in audit_day(items, day=2, context=ctx))
    out = svc._pad_micro_visits(items, day_num=2)
    codes = {d.code for d in audit_day(out, day=2, context=ctx)}
    assert "fragmented" not in codes


def test_pad_skips_lookaround_when_excel_tmax_under_fifteen():
    from app.domain.models.plan import AttractionItem, DayEndItem, DayStartItem, ItemType

    svc = _svc344()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Brama Krowia",
            description_short="", why_selected=["x"],
            start_time="09:10", end_time="09:20", duration_min=10,
            lat=54.35, lng=18.65,
        ),
        DayEndItem(time="20:00"),
    ]
    ctx = {
        "requested_city": "Gdańsk",
        "poi_meta": {"brama krowia": {"time_max": 10, "time_min": 5}},
    }
    out = svc._pad_micro_visits(items, ctx, day_num=2)
    visit = next(it for it in out if getattr(it, "name", "") == "Brama Krowia")
    assert visit.end_time == "09:20"
    assert int(visit.duration_min) == 10


def test_shrink_drops_long_free_time_before_lunch():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, FreeTimeItem, ItemType,
        LunchBreakItem, TransitItem, TransitMode,
    )
    from app.domain.planner.time_utils import time_to_minutes
    from app.domain.validators.client_invariants import LONG_FREE_TIME_MIN, audit_day

    svc = _svc344()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="t", name="Tężnia",
            description_short="", why_selected=["x"],
            start_time="09:28", end_time="09:58", duration_min=30,
            lat=50.26, lng=19.02,
        ),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME,
            start_time="10:40", end_time="12:00", duration_min=80,
            label="Czas wolny",
        ),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="12:00", end_time="12:50", duration_min=50,
            suggestions=[], label="Kresowe Smaki",
        ),
        DayEndItem(time="20:00"),
    ]
    ctx = {"requested_city": "Katowice", "day_end": "20:00", "day_start": "09:00"}
    out = svc._shrink_free_time_over_sixty(items, ctx, day_num=6)
    fts = [
        it for it in out
        if str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "free_time"
    ]
    assert all(
        (time_to_minutes(it.end_time) - time_to_minutes(it.start_time))
        <= LONG_FREE_TIME_MIN
        for it in fts
    )
    codes = {d.code for d in audit_day(out, day=6, context=ctx)}
    assert "long_free_time" not in codes

    hopped = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="t", name="Tężnia",
            description_short="", why_selected=["x"],
            start_time="09:28", end_time="09:58", duration_min=30,
            lat=50.26, lng=19.02,
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="09:58", end_time="10:40",
            duration_min=42, from_location="Tężnia", to_location="Kresowe Smaki",
            mode=TransitMode.CAR,
        ),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME,
            start_time="10:40", end_time="12:00", duration_min=80,
            label="Czas wolny",
        ),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="12:00", end_time="12:50", duration_min=50,
            suggestions=[], label="Kresowe Smaki",
        ),
        DayEndItem(time="20:00"),
    ]
    absorbed = svc._shrink_free_time_over_sixty(hopped, ctx, day_num=6)
    fts2 = [
        it for it in absorbed
        if str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "free_time"
    ]
    assert not fts2
    hop = next(
        it for it in absorbed
        if str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "transit"
    )
    assert hop.end_time == "12:00"
    codes2 = {d.code for d in audit_day(absorbed, day=6, context=ctx)}
    assert "long_free_time" not in codes2


def test_guliwer_slides_past_lunch_to_opening():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, LunchBreakItem,
    )
    from app.domain.planner.time_utils import time_to_minutes
    from app.domain.validators.client_invariants import audit_day

    svc = _svc344()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="g", name="Centrum Rozrywki Guliwer",
            description_short="", why_selected=["x"],
            start_time="10:13", end_time="11:25", duration_min=72,
            lat=50.26, lng=19.02,
        ),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="12:00", end_time="12:50", duration_min=50,
            suggestions=[], label="Kresowe Smaki",
        ),
        DayEndItem(time="19:00"),
    ]
    hours = {
        "date_from": "01-01", "date_to": "12-31",
        "mon": "14:00-20:00", "tue": "14:00-20:00", "wed": "14:00-20:00",
        "thu": "14:00-20:00", "fri": "14:00-20:00",
        "sat": "11:00-20:00", "sun": "11:00-20:00",
    }
    ctx = {
        "requested_city": "Katowice",
        "date": "2026-02-20",
        "day_start": "09:00",
        "day_end": "19:00",
        "poi_pool": [{
            "id": "g",
            "name": "Centrum Rozrywki Guliwer",
            "opening_hours_seasonal": [hours],
            "time_min": 60,
            "time_max": 180,
        }],
        "poi_meta": {
            "centrum rozrywki guliwer": {
                "opening_hours_seasonal": [hours],
                "time_min": 60,
                "time_max": 180,
            }
        },
    }
    out = svc._respect_opening_hours(items, ctx, day_num=3)
    visit = next(
        it for it in out if "Guliwer" in (getattr(it, "name", "") or "")
    )
    assert time_to_minutes(visit.start_time) >= 14 * 60
    codes = {d.code for d in audit_day(out, day=3, context=ctx)}
    assert "closed_stop" not in codes
