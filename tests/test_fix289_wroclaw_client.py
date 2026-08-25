"""FIX #289 — Wrocław leftover: dupes, meals, walk/car, winter, budget, hours."""
from __future__ import annotations

from types import SimpleNamespace

from app.application.services.plan_service import PlanService
from app.domain.filters.seasonality import filter_by_season
from app.domain.models.plan import (
    AttractionItem,
    DayEndItem,
    FreeTimeItem,
    ItemType,
    LunchBreakItem,
    RestaurantSuggestion,
    TransitItem,
    TransitMode,
)
from app.domain.planner.engine import (
    poi_geo_region_key,
    should_block_city_daytrip_poi,
    visit_duration_hard_cap,
)
from app.domain.scoring.profile_poi_rules import (
    poi_trip_repeat_key,
    should_deny_poi_for_profile,
)


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur=60, *, lat=51.11, lng=17.03, city="Wrocław", cost=0):
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


def _tr(
    frm, to, start, end, *, km, dur, mode=TransitMode.WALK, src="estimated_walk",
):
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


def test_iluzja_cap_is_60():
    assert visit_duration_hard_cap({"name": "Świat Iluzji we Wrocławiu"}) == 60


def test_cross_day_strips_wyspa_pergola_japonski():
    d1 = SimpleNamespace(day=1, items=[
        _attr("Ogród Japoński", "11:00", "12:00", 60),
    ], quality_badges=None, date=None, weekday=None)
    d2 = SimpleNamespace(day=2, items=[
        _attr("Wyspa Słodowa", "11:00", "12:15", 75),
        _attr("Pergola", "13:00", "14:00", 60),
    ], quality_badges=None, date=None, weekday=None)
    d3 = SimpleNamespace(day=3, items=[
        _attr("Wyspa Słodowa", "10:00", "11:15", 75),
        _attr("Pergola", "12:00", "13:00", 60),
        _attr("Ogród Japoński", "14:00", "15:00", 60),
    ], quality_badges=None, date=None, weekday=None)
    out = _svc()._strip_cross_day_trip_repeats([d1, d2, d3])
    names = [
        getattr(it, "name", "")
        for d in out
        for it in (d.items or [])
    ]
    assert names.count("Wyspa Słodowa") == 1
    assert names.count("Pergola") == 1
    assert names.count("Ogród Japoński") == 1


def test_park_mamuta_and_przyrodnicze_repeat_keys():
    assert poi_trip_repeat_key("Park Mamuta") == "wro_park_mamuta"
    assert poi_trip_repeat_key("Muzeum Przyrodnicze") == "wro_muzeum_przyrodnicze"
    assert poi_trip_repeat_key("Ogród Japoński") == "wro_ogrod_japonski"


def test_cork_rotates_on_day2():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="13:00",
        end_time="14:00",
        duration_min=60,
        suggestions=[
            RestaurantSuggestion.model_construct(
                name="The Cork", lat=51.11, lng=17.03, cuisine_type="", meal_type="all",
            ),
        ],
    )
    ctx = {
        "trip_meal_names": {"the cork"},
        "restaurants_available": [
            {"name": "IDA kuchnia i wino", "lat": 51.11, "lng": 17.04, "city": "Wrocław"},
            {"name": "The Cork", "lat": 51.11, "lng": 17.03, "city": "Wrocław"},
        ],
        "target_group": "couples",
    }
    out = _svc()._rotate_repeated_default_meals(
        [lunch], ctx, {"target_group": "couples"}, day_num=2,
    )
    primary = (out[0].suggestions or [None])[0]
    assert primary is not None
    assert "cork" not in (primary.name or "").lower()


def test_walk_2_9km_with_car_becomes_drive():
    items = [_tr(
        "Pod przykrywką", "Hydropolis", "14:00", "14:39",
        km=2.94, dur=39, mode=TransitMode.WALK, src="estimated_walk",
    )]
    out = _svc()._downgrade_short_urban_cars(
        items, {"has_car": True}, day_num=1,
    )
    mode = str(getattr(getattr(out[0], "mode", None), "value", out[0].mode) or "")
    assert "car" in mode.lower()
    assert int(out[0].duration_min) <= 20


def test_355m_car_becomes_walk():
    items = [_tr(
        "Let Me Out", "Olio", "16:00", "16:14",
        km=0.355, dur=14, mode=TransitMode.CAR, src="estimated_road",
    )]
    out = _svc()._downgrade_short_urban_cars(
        items, {"has_car": True}, day_num=1,
    )
    mode = str(getattr(getattr(out[0], "mode", None), "value", out[0].mode) or "")
    assert "walk" in mode.lower()
    assert int(out[0].duration_min) <= 8


def test_2km_walk_in_10_min_is_implausible():
    a = _attr("A", "10:00", "11:00", 60, lat=51.1100, lng=17.0300)
    b = _attr("B", "11:10", "12:00", 50, lat=51.1200, lng=17.0480)
    hop = _tr("A", "B", "11:00", "11:10", km=2.021, dur=10)
    out = _svc()._sanitize_walk_leg_durations(
        [a, hop, b], {}, day_num=2, context={"has_car": True},
    )
    tr = next(it for it in out if getattr(it, "type", None) == ItemType.TRANSIT)
    mode = str(getattr(getattr(tr, "mode", None), "value", tr.mode) or "")
    assert "car" in mode.lower() or int(tr.duration_min) >= 20


def test_38m_walk_is_not_17_min():
    hop = _tr("X", "Y", "10:00", "10:17", km=0.038, dur=17)
    out = _svc()._sanitize_walk_leg_durations([hop], {}, day_num=7)
    assert int(out[0].duration_min) <= 5
    mode = str(getattr(getattr(out[0], "mode", None), "value", out[0].mode) or "")
    assert "walk" in mode.lower()


def test_87km_in_20_min_is_stretched():
    hop = _tr(
        "Wrocław", "Niemcza", "15:00", "15:20",
        km=87, dur=20, mode=TransitMode.CAR, src="estimated_road",
    )
    out = _svc()._fix_implausible_transit_duration(hop, {}, {"has_car": True})
    assert int(out.duration_min) >= 50


def test_66km_walk_becomes_car():
    hop = _tr(
        "Centrum", "Wojsławice", "14:00", "14:05",
        km=66, dur=5, mode=TransitMode.WALK, src="estimated_walk",
    )
    out = _svc()._fix_implausible_transit_duration(hop, {}, {"has_car": True})
    mode = str(getattr(getattr(out, "mode", None), "value", out.mode) or "")
    assert "car" in mode.lower()
    assert int(out.duration_min) >= 40


def test_gokarty_denied_for_cultural():
    assert should_deny_poi_for_profile(
        {"name": "Gokarty Wrocław"},
        {"target_group": "couples", "travel_style": "cultural",
         "preferences": ["museum_heritage", "relaxation"]},
    ) is True


def test_let_me_out_denied_for_seniors():
    assert should_deny_poi_for_profile(
        {"name": "Let Me Out Escape Room"},
        {"target_group": "seniors", "travel_style": "relax",
         "preferences": ["museum_heritage", "nature_landscape", "relaxation"]},
    ) is True


def test_winter_rejs_filtered():
    kept = filter_by_season(
        [{"name": "Rejs statkiem po Odrze", "id": "r1", "season_fit": {"winter": 1}}],
        "2026-02-24",
    )
    assert kept == []
    kept2 = filter_by_season(
        [{"name": "Spływ pontonowy Złotniki", "id": "p1", "season_fit": {"winter": 1}}],
        "2026-02-24",
    )
    assert kept2 == []


def test_grabowy_is_wojslawice_and_blocked_on_3day():
    poi = {"name": "Grabowy Labirynt", "city": "Niemcza", "lat": 50.725, "lng": 16.852}
    assert poi_geo_region_key(poi) == "region_wojslawice"
    assert should_block_city_daytrip_poi(poi, {
        "requested_city": "Wrocław",
        "num_days": 3,
        "current_day_num": 3,
        "trip_type": "city_tourism",
    }) is True


def test_botaniczny_not_hala_coords():
    item = _attr(
        "Ogród Botaniczny", "11:00", "12:00", 60,
        lat=51.1069, lng=17.0773, city="Wrocław",
    )
    out = _svc()._force_known_good_poi_coords([item], day_num=1)
    assert abs(float(out[0].lat) - 51.1163) < 0.01
    assert abs(float(out[0].lng) - 17.0478) < 0.02


def test_walk_plus_road_source_aligned():
    hop = _tr(
        "Hydropolis", "Česká", "18:00", "18:08",
        km=0.5, dur=8, mode=TransitMode.WALK, src="estimated_road",
    )
    out = _svc()._fix_unrealistic_transit_modes(
        [hop], {}, {"has_car": True, "transport_modes": ["car"]}, day_num=2,
    )
    assert "walk" in str(getattr(out[0], "routing_source", "")).lower()


def test_attraction_starting_at_day_end_dropped():
    items = [
        _attr("Muzeum Pana Tadeusza", "18:00", "18:27", 27),
        DayEndItem(time="18:00"),
    ]
    out = _svc()._clamp_timeline_to_day_end(
        items, {"day_end": "18:00"}, day_num=4,
    )
    names = [getattr(it, "name", "") for it in out]
    assert "Muzeum Pana Tadeusza" not in names


def test_budget_drops_paid_stack():
    items = [
        _attr("GoJump", "10:00", "11:30", 90, cost=400),
        _attr("Let Me Out Escape Room", "12:00", "13:20", 80, cost=350),
        _attr("Rynek we Wrocławiu", "14:00", "15:00", 60, cost=0),
    ]
    out = _svc()._drop_over_budget_paid_attractions(
        items, {"daily_limit": 600, "preferences": ["active_sport"]}, day_num=1,
    )
    names = [getattr(it, "name", "") for it in out]
    costs = sum(float(getattr(it, "cost_estimate", 0) or 0) for it in out)
    assert costs <= 600
    assert "Rynek we Wrocławiu" in names


def test_trailing_adventure_free_time_capped():
    items = [
        _attr("Centrum Historii Zajezdnia", "12:00", "13:30", 90),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME,
            start_time="13:30",
            end_time="16:03",
            duration_min=153,
            label="Czas dla siebie",
            suggestions=[],
        ),
        DayEndItem(time="19:00"),
    ]
    out = _svc()._cap_trailing_adventure_free_time(
        items, {"travel_style": "adventure"}, day_num=2,
    )
    ft = [it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME]
    assert not ft or int(ft[0].duration_min) <= 50
