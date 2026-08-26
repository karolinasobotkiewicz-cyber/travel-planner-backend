"""FIX #294 — Kraków leftover: Wieliczka-lunch, season, dupes, walk/car, caps."""
from __future__ import annotations

from datetime import date

from app.application.services.plan_service import PlanService, _ft_evening_starts_at
from app.domain.filters.seasonality import filter_by_season
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
    _meal_restaurant_geo_ok,
    visit_duration_hard_cap,
)
from app.domain.scoring.profile_poi_rules import poi_trip_repeat_key


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur=60, *, lat=50.06, lng=19.94, city="Kraków"):
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


def _ft(start, end, dur, *, label="Czas wolny"):
    return FreeTimeItem.model_construct(
        type=ItemType.FREE_TIME,
        start_time=start,
        end_time=end,
        duration_min=dur,
        label=label,
        suggestions=[],
    )


def _lunch(start, end, *, name, lat, lng, city="Wieliczka"):
    sug = RestaurantSuggestion.model_construct(
        id="r1",
        name=name,
        address=city,
        lat=lat,
        lng=lng,
        city=city,
        meal_type="lunch",
    )
    return LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time=start,
        end_time=end,
        duration_min=60,
        suggestions=[sug],
    )


def test_botaniczny_and_zakrzowek_repeat_keys():
    assert poi_trip_repeat_key("Ogród Botaniczny UJ") is not None
    assert poi_trip_repeat_key("Zakrzówek") == "krk_zakrzowek"


def test_ogrod_doswiadczen_closed_in_february():
    kept = {
        p["name"]
        for p in filter_by_season(
            [
                {
                    "name": "Ogród Doświadczeń im. Stanisława Lema",
                    "id": "od1",
                    "season_fit": {"winter": 1},
                },
                {"name": "Wawel", "id": "w2", "season_fit": {"winter": 1}},
            ],
            "2026-02-20",
        )
    }
    assert not any("Doświadczeń" in n or "Doswiadczen" in n for n in kept)
    assert "Wawel" in kept


def test_wieliczka_lunch_after_las_wolski_is_stripped():
    items = [
        _attr("Las Wolski", "10:00", "12:00", 120, lat=50.060, lng=19.855),
        _tr(
            "Las Wolski", "Karczma Wieliczka", "12:00", "12:40",
            km=25.6, dur=40, mode=TransitMode.CAR, src="estimated_road",
        ),
        _lunch(
            "12:40", "13:40",
            name="Karczma w Wieliczce",
            lat=49.987, lng=20.065, city="Wieliczka",
        ),
    ]
    out = _svc()._strip_far_meal_only_hops(items, day_num=3)
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert not hops
    meals = [it for it in out if getattr(it, "type", None) == ItemType.LUNCH_BREAK]
    assert meals and not (meals[0].suggestions or [])


def test_lotnictwa_restaurant_detour_is_stripped():
    items = [
        _attr("Muzeum Lotnictwa Polskiego", "12:00", "13:30", 90, lat=50.078, lng=19.990),
        _tr(
            "Muzeum Lotnictwa Polskiego", "Restauracja daleko", "13:30", "13:55",
            km=16.3, dur=25, mode=TransitMode.CAR, src="estimated_road",
        ),
        _lunch(
            "13:55", "14:40",
            name="Restauracja daleko",
            lat=49.987, lng=20.065, city="Wieliczka",
        ),
        _attr("Park Decjusza", "16:00", "17:00", 60, lat=50.064, lng=19.881),
    ]
    out = _svc()._strip_far_meal_only_hops(items, day_num=5)
    hops = [
        it for it in out
        if getattr(it, "type", None) == ItemType.TRANSIT
        and "daleko" in (getattr(it, "to_location", "") or "").lower()
    ]
    assert not hops


def test_geo_ok_refuses_10km_restaurant():
    last = {"name": "Las Wolski", "lat": 50.060, "lng": 19.855, "city": "Kraków"}
    rest = {
        "name": "Karczma",
        "lat": 49.987, "lng": 20.065, "city": "",
        "address": "",
    }
    assert _meal_restaurant_geo_ok(rest, last, {"requested_city": "Kraków"}) is False


def test_blonia_and_teznia_caps():
    assert visit_duration_hard_cap({"name": "Błonia Krakowskie"}) == 45
    assert visit_duration_hard_cap({"name": "Tężnia solankowa"}) == 30


def test_kazimierz_capped_for_preschooler():
    item = _attr("Kazimierz", "11:00", "12:34", 94)
    out = _svc()._cap_stretched_attraction_durations(
        [item], day_num=1,
        user={"target_group": "family_kids", "children_age": 5, "travel_style": "relax"},
    )
    assert int(out[0].duration_min) <= 50


def test_wioski_floor_when_in_season():
    item = _attr("Wioski Świata", "11:00", "11:22", 22)
    out = _svc()._cap_stretched_attraction_durations([item], day_num=4)
    assert int(out[0].duration_min) >= 60


def test_july_dusk_is_after_20():
    assert _ft_evening_starts_at({"season": "summer"}) == 20 * 60
    items = [_ft("17:26", "19:11", 105, label="Wieczorne zwiedzanie na luzie")]
    out = _svc()._relabel_free_time_by_slot(
        items, {"season": "summer", "day_end": "21:00"}, day_num=2,
    )
    blob = (out[0].label or "").lower() + " " + " ".join(
        str(s).lower() for s in (out[0].suggestions or [])
    )
    assert "zmroku" not in blob


def test_ft_split_by_short_transit_merges():
    items = [
        _attr("Rynek", "12:00", "13:00", 60),
        _ft("13:00", "13:25", 25),
        _tr("Rynek", "Planty", "13:25", "13:40", km=0.8, dur=15),
        _ft("13:40", "14:46", 66),
        _attr("Sukiennice", "15:00", "16:00", 60),
    ]
    out = _svc()._merge_abutting_free_time_hard(items, day_num=2, max_gap=6)
    fts = [it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME]
    assert len(fts) == 1
    assert int(fts[0].duration_min) >= 80


def test_817m_car_becomes_walk():
    items = [_tr(
        "Wawel", "Smok", "16:00", "16:08",
        km=0.817, dur=8, mode=TransitMode.CAR, src="estimated_road",
    )]
    out = _svc()._force_short_city_hops_walk(items, day_num=10)
    mode = str(getattr(getattr(out[0], "mode", None), "value", out[0].mode) or "")
    assert "walk" in mode.lower()


def test_relax_18km_walk_is_not_auto_car():
    items = [_tr(
        "Botaniczny", "Zakrzówek", "14:00", "14:25",
        km=1.8, dur=25, mode=TransitMode.WALK, src="estimated_walk",
    )]
    out = _svc()._downgrade_short_urban_cars(
        items,
        {
            "has_car": True,
            "user": {"target_group": "solo", "travel_style": "relax"},
        },
        day_num=2,
    )
    mode = str(getattr(getattr(out[0], "mode", None), "value", out[0].mode) or "")
    assert "walk" in mode.lower()


def test_gojump_to_barbakan_too_short_walk_becomes_car():
    hop = _tr(
        "GOjump", "Barbakan", "14:00", "14:15",
        km=5.403, dur=15, mode=TransitMode.WALK, src="estimated_road",
    )
    go = _attr("GOjump Kraków", "12:00", "14:00", 120, lat=50.09, lng=19.89)
    barb = _attr("Barbakan", "14:30", "15:10", 40, lat=50.065, lng=19.941)
    out = _svc()._sanitize_walk_leg_durations(
        [go, hop, barb], {}, day_num=4, context={"has_car": True},
    )
    legs = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert legs
    mode = str(getattr(legs[0].mode, "value", legs[0].mode)).lower()
    assert "car" in mode


def test_ogrod_doswiadczen_stripped_from_timeline_in_february():
    items = [_attr("Ogród Doświadczeń im. Stanisława Lema", "11:00", "12:30", 90)]
    out = _svc()._strip_out_of_season_attractions(
        items, date(2026, 2, 20), {},
    )
    assert out == []
