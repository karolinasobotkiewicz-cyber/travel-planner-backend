"""FIX #297 — Poznań leftover: Monday Palmiarnia, transits, thin far, hours."""
from __future__ import annotations

from datetime import date

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    ItemType,
    LunchBreakItem,
    TicketInfo,
    TransitItem,
    TransitMode,
)
from app.domain.planner.engine import poi_geo_region_key, should_block_city_daytrip_poi
from app.domain.scoring.profile_poi_rules import should_deny_poi_for_profile


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur=60, *, lat=52.406, lng=16.925, city="Poznań"):
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


def test_palmiarnia_stripped_on_monday():
    items = [
        _attr("Palmiarnia Poznańska", "15:55", "16:55", 60),
        _attr("Park Wilsona", "17:10", "18:00", 50),
    ]
    out = _svc()._strip_closed_on_weekday(items, date(2026, 2, 16), day_num=1)
    names = [getattr(it, "name", "") for it in out]
    assert not any("almiarnia" in n for n in names)
    assert any("Wilsona" in n for n in names)


def test_wilsona_self_transit_stripped():
    items = [
        _attr("Park Wilsona", "10:00", "11:00", 60),
        _tr(
            "Park Wilsona", "Park Wilsona",
            "11:00", "11:13", km=0.0, dur=13,
        ),
        _attr("Stary Rynek", "11:20", "12:20", 60),
    ]
    out = _svc()._strip_self_transits(items, day_num=1)
    transits = [it for it in out if it.type == ItemType.TRANSIT]
    assert transits == []


def test_micro_car_hops_become_walk():
    hops = [
        _tr("Palmiarnia", "Park Wilsona", "16:55", "17:10", km=0.282, dur=15),
        _tr("Makiety", "Rynek 95", "13:00", "13:08", km=0.238, dur=8),
        _tr("A", "B", "14:00", "14:10", km=0.791, dur=10),
    ]
    out = _svc()._force_short_city_hops_walk(hops, day_num=1)
    for it in out:
        mode = str(getattr(it.mode, "value", it.mode)).lower()
        assert "walk" in mode


def test_5km_in_5_min_car_rebuilt():
    hop = _tr(
        "Termy Maltańskie", "Antrejka",
        "14:00", "14:05", km=5.045, dur=5,
    )
    out = _svc()._sanitize_walk_leg_durations(
        [hop], {}, day_num=3, context={"has_car": True},
    )
    assert int(out[0].duration_min) >= 10


def test_long_walk_5min_becomes_car():
    hop = _tr(
        "Park Sołacki", "Just Friends",
        "13:00", "13:05", km=3.823, dur=5,
        mode=TransitMode.WALK, src="estimated_road",
    )
    out = _svc()._sanitize_walk_leg_durations(
        [hop], {}, day_num=1, context={"has_car": True},
    )
    mode = str(getattr(out[0].mode, "value", out[0].mode)).lower()
    assert "car" in mode
    assert int(out[0].duration_min) >= 8


def test_1530m_walk_10min_duration_rebuilt():
    hop = _tr(
        "Park Cytadela", "Muzeum Iluzji",
        "15:00", "15:10", km=1.53, dur=10,
        mode=TransitMode.WALK, src="estimated_walk",
    )
    out = _svc()._sanitize_walk_leg_durations(
        [hop], {}, day_num=1, context={"has_car": True},
    )
    mode = str(getattr(out[0].mode, "value", out[0].mode)).lower()
    assert "walk" in mode
    assert int(out[0].duration_min) >= 18


def test_walk_estimated_road_normalized():
    hop = _tr(
        "A", "B", "12:00", "12:18", km=1.989, dur=18,
        mode=TransitMode.WALK, src="estimated_road",
    )
    out = _svc()._normalize_transit_mode_source([hop], day_num=3)
    src = str(getattr(out[0], "routing_source", "") or "").lower()
    assert src == "estimated_walk"


def test_strzeszyn_thin_far_dropped():
    items = [
        _attr("Termy Maltańskie", "10:00", "12:00", 120),
        _tr(
            "Termy Maltańskie", "Jezioro Strzeszyńskie",
            "12:00", "12:38", km=8.2, dur=38,
        ),
        _attr(
            "Jezioro Strzeszyńskie", "12:38", "13:17", 39,
            lat=52.458, lng=16.850,
        ),
    ]
    out = _svc()._drop_thin_lonely_far_stops(items, day_num=3)
    names = [getattr(it, "name", "") for it in out]
    assert not any("trzeszyn" in n.lower() for n in names)


def test_pobiedziska_is_lednica_region():
    assert poi_geo_region_key(
        {"name": "Rezerwat w Pobiedziskach", "city": "Pobiedziska"}
    ) == "region_lednica"


def test_3day_poznan_blocks_pobiedziska():
    ctx = {
        "requested_city": "Poznań",
        "num_days": 3,
        "current_day_num": 3,
        "preferences": ["museum_heritage", "relaxation"],
    }
    assert should_block_city_daytrip_poi(
        {"name": "Skansen w Pobiedziskach", "city": "Pobiedziska"},
        ctx,
    ) is True


def test_dziekanowice_50km_dropped():
    items = [
        _attr("Stary Rynek", "10:00", "11:00", 60),
        _tr(
            "Stary Rynek", "Wyspa Ostrów Lednicki",
            "11:00", "11:50", km=50.0, dur=50,
        ),
        _attr(
            "Wyspa Ostrów Lednicki w Dziekanowicach",
            "11:50", "13:00", 70,
            lat=52.526, lng=17.375, city="Dziekanowice",
        ),
    ]
    out = _svc()._drop_thin_lonely_far_stops(items, day_num=7)
    names = [getattr(it, "name", "") for it in out]
    assert not any("dziekanowic" in n.lower() or "lednick" in n.lower() for n in names)


def test_gniezno_after_return_to_poznan_dropped():
    items = [
        _attr("Katedra w Gnieźnie", "10:00", "11:30", 90, city="Gniezno"),
        _tr(
            "Katedra w Gnieźnie", "Poznań",
            "11:30", "12:20", km=47.5, dur=50,
        ),
        _attr("Muzeum Początków Państwa Polskiego", "13:00", "14:00", 60, city="Gniezno"),
    ]
    out = _svc()._drop_satellite_revisit_after_hub_return(items, day_num=5)
    names = [getattr(it, "name", "") for it in out]
    assert any("atedra" in n for n in names)
    assert not any("oczątk" in n or "oczatk" in n for n in names)


def test_termy_floor_at_least_90():
    items = [_attr("Termy Maltańskie", "14:00", "15:09", 69)]
    out = _svc()._cap_stretched_attraction_durations(
        items,
        day_num=2,
        user={"preferences": ["water_attractions", "relaxation"]},
    )
    assert int(out[0].duration_min) >= 90


def test_termy_crushed_below_90_dropped():
    items = [_attr("Termy Maltańskie", "16:30", "17:20", 50)]
    out = _svc()._drop_crushed_named_visits(items, day_num=2)
    assert out == []


def test_muzeum_powstania_after_1800_stripped():
    items = [
        _attr("Muzeum Powstania Wielkopolskiego", "18:25", "19:55", 90),
        _attr("Park Cytadela", "16:00", "17:00", 60),
    ]
    out = _svc()._strip_after_hours_museums(items, day_num=1)
    names = [getattr(it, "name", "") for it in out]
    assert not any("owstania" in n for n in names)


def test_zamek_krolewski_shifted_to_10():
    items = [_attr("Zamek Królewski", "09:00", "10:00", 60)]
    out = _svc()._strip_after_hours_museums(items, day_num=1)
    assert out
    assert out[0].start_time >= "10:00"


def test_instrumentow_denied_for_family_kids():
    assert should_deny_poi_for_profile(
        {"name": "Muzeum Instrumentów Muzycznych"},
        {
            "target_group": "family_kids",
            "preferences": ["kids_attractions", "relaxation"],
            "children_age": 5,
        },
    ) is True


def test_adventure_day_capped_at_five():
    items = [
        _attr(f"POI {i}", f"{10+i}:00", f"{10+i}:40", 40)
        for i in range(7)
    ]
    out = _svc()._cap_packed_city_day(
        items, {"travel_style": "adventure"}, day_num=1,
    )
    n = sum(1 for it in out if it.type == ItemType.ATTRACTION)
    assert n == 5


def test_12min_gap_is_named():
    items = [
        _attr("A", "15:00", "15:52", 52),
        _attr("B", "16:04", "17:00", 56),
    ]
    out = _svc()._fill_anonymous_midday_gaps(items, {}, day_num=1)
    fts = [it for it in out if it.type == ItemType.FREE_TIME]
    assert fts
    assert int(fts[0].duration_min) >= 8


def test_zamek_poznan_ticket_forced_to_20():
    it = AttractionItem.model_construct(
        type=ItemType.ATTRACTION,
        poi_id="zamek",
        name="Zamek Królewski",
        description_short="Zamek na Placu Zamkowym w Warszawie.",
        start_time="10:00",
        end_time="11:00",
        duration_min=60,
        lat=52.4094,
        lng=16.9315,
        address="Plac Zamkowy 4, 00-277 Warszawa",
        city="Warszawa",
        cost_estimate=120,
        ticket_info=TicketInfo(ticket_normal=60, ticket_reduced=30),
    )
    out = _svc()._force_known_good_poi_coords([it], day_num=1)
    ti = getattr(out[0], "ticket_info", None)
    assert ti is not None
    assert int(ti.ticket_normal) == 20
    assert "Poznań" in (out[0].address or "") or "przemys" in (out[0].address or "").lower()


def test_strzeszyn_lunch_not_centrum():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="13:00",
        end_time="14:00",
        duration_min=60,
        suggestions=[],
        location_context="centrum",
    )
    items = [
        _attr(
            "Jezioro Strzeszyńskie", "11:00", "12:50", 110,
            lat=52.458, lng=16.850,
        ),
        lunch,
    ]
    out = _svc()._snap_meals_to_nearby_restaurants(
        items,
        {"requested_city": "Poznań", "restaurants_available": []},
        {"target_group": "seniors"},
        day_num=3,
    )
    meals = [it for it in out if it.type == ItemType.LUNCH_BREAK]
    assert meals
    ctx = str(getattr(meals[0], "location_context", "") or "").lower()
    assert "centrum" not in ctx
    assert "strzeszy" in ctx
