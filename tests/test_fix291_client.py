"""FIX #291 — WRO/KRK/WAWA leftover: hours, winter, caps, FT, walk, meals."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.application.services.plan_service import PlanService
from app.domain.filters.seasonality import filter_by_season
from app.domain.models.plan import (
    AttractionItem,
    DayEndItem,
    FreeTimeItem,
    ItemType,
    LunchBreakItem,
    TransitItem,
    TransitMode,
)
from app.domain.planner.engine import (
    _meal_restaurant_geo_ok,
    visit_duration_hard_cap,
)
from app.domain.scoring.profile_poi_rules import (
    poi_trip_repeat_key,
    should_deny_poi_for_profile,
)


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur=60, *, lat=51.11, lng=17.03, city="Wrocław",
          desc="", address=""):
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
        address=address or city,
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


def _ft(start, end, dur):
    return FreeTimeItem.model_construct(
        type=ItemType.FREE_TIME,
        start_time=start,
        end_time=end,
        duration_min=dur,
        label="Czas wolny",
        suggestions=[],
    )


def test_winter_strips_fontanna_and_strefa_wakacji():
    winter = "2026-02-22"
    kept = {
        p["name"]
        for p in filter_by_season(
            [
                {"name": "Fontanna Multimedialna", "id": "f1", "season_fit": {"winter": 1}},
                {"name": "Wrocław - Strefa Wakacji", "id": "s1", "season_fit": {"winter": 1}},
                {"name": "Hydropolis", "id": "h1", "season_fit": {"winter": 1}},
            ],
            winter,
        )
    }
    assert "Fontanna Multimedialna" not in kept
    assert "Wrocław - Strefa Wakacji" not in kept
    assert "Hydropolis" in kept


def test_polish_winter_closed_uses_item_type_value():
    items = [
        _attr("Fontanna Multimedialna", "19:00", "19:30", 30),
        _attr("Hydropolis", "11:00", "12:30", 90),
    ]
    out = _svc()._strip_out_of_season_attractions(
        items, date(2026, 2, 22), {"id-Hydropolis": {"id": "id-Hydropolis"}},
    )
    names = [getattr(it, "name", "") for it in out]
    assert "Fontanna Multimedialna" not in names
    assert "Hydropolis" in names


def test_pana_tadeusza_clamped_to_17():
    items = [_attr("Muzeum Pana Tadeusza", "15:48", "17:08", 80)]
    out = _svc()._strip_after_hours_museums(items, day_num=2)
    assert out and out[0].end_time == "17:00"


def test_wilanow_after_last_entry_dropped():
    items = [_attr("Pałac w Wilanowie", "17:09", "18:39", 90, city="Warszawa")]
    out = _svc()._strip_after_hours_museums(items, day_num=1, trip_date=date(2026, 6, 15))
    assert out == []


def test_wilanow_monday_after_15_dropped():
    items = [_attr("Pałac w Wilanowie", "15:09", "16:39", 90, city="Warszawa")]
    out = _svc()._strip_after_hours_museums(items, day_num=1, trip_date=date(2026, 6, 8))
    assert out == []


def test_iluzja_shifted_to_10():
    items = [_attr("Świat Iluzji", "09:00", "10:30", 90, city="Warszawa")]
    out = _svc()._strip_after_hours_museums(items, day_num=1)
    assert out and out[0].start_time == "10:00"


def test_lotnictwa_monday_stripped():
    items = [_attr("Muzeum Lotnictwa Polskiego", "11:00", "12:30", 90, city="Kraków")]
    out = _svc()._strip_closed_on_weekday(items, date(2026, 7, 20), day_num=1)
    assert out == []


def test_lotnictwa_after_18_stripped():
    items = [_attr("Muzeum Lotnictwa Polskiego", "20:19", "21:13", 54, city="Kraków")]
    out = _svc()._strip_after_hours_museums(items, day_num=1)
    assert out == []


def test_zajezdnia_saturday_after_18_stripped():
    items = [_attr("Centrum Historii Zajezdnia", "18:12", "19:37", 85)]
    out = _svc()._strip_after_hours_museums(items, day_num=4, trip_date=date(2026, 2, 21))
    assert out == []


def test_hala_and_pergola_caps():
    assert visit_duration_hard_cap({"name": "Hala Stulecia"}) == 60
    assert visit_duration_hard_cap({"name": "Pergola przy Hali Stulecia"}) == 45
    assert visit_duration_hard_cap({"name": "Świat w Budowie"}) == 60
    assert visit_duration_hard_cap({"name": "Ogród Saski"}) == 60


def test_hala_floor_and_browar_floor():
    hala = _attr("Hala Stulecia", "11:00", "11:21", 21)
    browar = _attr("Browar Stu Mostów", "18:00", "18:20", 20)
    out_h = _svc()._cap_stretched_attraction_durations([hala], day_num=1)
    out_b = _svc()._cap_stretched_attraction_durations([browar], day_num=1)
    assert int(out_h[0].duration_min) >= 45
    assert int(out_b[0].duration_min) <= 60
    assert int(out_b[0].duration_min) >= 40


def test_kosmopark_denied_off_kids():
    assert should_deny_poi_for_profile(
        {"name": "Kosmopark"},
        {"target_group": "friends", "preferences": ["museum_heritage"],
         "travel_style": "cultural"},
    )


def test_wioski_denied_for_couples_cultural():
    assert should_deny_poi_for_profile(
        {"name": "Wioski Świata"},
        {"target_group": "couples", "preferences": ["museum_heritage"],
         "travel_style": "cultural"},
    )


def test_hala_denied_without_museum_pref():
    assert should_deny_poi_for_profile(
        {"name": "Hala Stulecia"},
        {"target_group": "friends",
         "preferences": ["water_attractions", "local_food_experience", "relaxation"],
         "travel_style": "balanced"},
    )


def test_motyl_repeat_key():
    assert poi_trip_repeat_key("Muzeum Żywego Motyla") == "krk_motyl"


def test_walk_2km_in_15_min_becomes_honest():
    hop = _tr(
        "Oliwa i Ogień", "Hydropolis", "13:00", "13:15",
        km=2.224, dur=15, mode=TransitMode.WALK,
    )
    out = _svc()._sanitize_walk_leg_durations(
        [hop], {}, day_num=1, context={"has_car": True},
    )
    mode = str(getattr(out[0].mode, "value", out[0].mode)).lower()
    assert "car" in mode or int(out[0].duration_min) >= 28


def test_321m_car_becomes_short_walk():
    hop = _tr(
        "Smart Kids", "Primitivo", "12:00", "12:35",
        km=0.321, dur=35, mode=TransitMode.CAR, src="estimated_road",
    )
    out = _svc()._sanitize_walk_leg_durations([hop], {}, day_num=1)
    assert "walk" in str(getattr(out[0].mode, "value", out[0].mode)).lower()
    assert int(out[0].duration_min) <= 10


def test_zero_km_restaurant_self_transit_stripped():
    hop = _tr(
        "Tutti Santi", "Tutti Santi", "14:27", "14:39",
        km=0.0, dur=12, mode=TransitMode.CAR, src="estimated_road",
    )
    assert _svc()._strip_self_transits([hop], day_num=1) == []


def test_leading_and_stacked_free_time_trimmed():
    items = [
        _ft("09:00", "10:00", 60),
        _attr("Hydropolis", "10:00", "12:00", 120),
        _ft("14:00", "15:11", 71),
        _ft("16:00", "16:32", 32),
        DayEndItem(time="19:00"),
    ]
    out = _svc()._trim_excess_free_time(
        items, {"travel_style": "balanced"}, {"day_start": "09:00"}, day_num=2,
    )
    fts = [it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME]
    assert all(int(it.duration_min) <= 40 for it in fts)
    assert not any(it.start_time == "09:00" for it in fts)


def test_relax_keeps_early_finish():
    items = [
        _attr("Ogród Saski", "16:00", "16:45", 45, city="Warszawa"),
        _ft("16:45", "19:00", 135),
        DayEndItem(time="19:00"),
    ]
    out = _svc()._trim_excess_free_time(
        items, {"travel_style": "relax"}, {"day_start": "09:00", "day_end": "19:00"},
        day_num=3,
    )
    fts = [it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME]
    assert not fts


def test_lunch_overlap_free_time_dropped():
    items = [
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="13:39",
            end_time="14:24",
            duration_min=45,
            suggestions=[],
        ),
        _ft("13:51", "14:21", 30),
    ]
    out = _svc()._trim_excess_free_time(items, {}, {"day_start": "09:00"}, day_num=7)
    assert not [it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME]


def test_niemcza_dinner_refused_after_sky_tower():
    last = {"name": "Sky Tower", "lat": 51.094, "lng": 17.019, "city": "Wrocław"}
    rest = {
        "name": "Pod Łabędziem",
        "lat": 50.72, "lng": 16.83,
        "city": "Niemcza",
        "address": "Niemcza",
    }
    assert _meal_restaurant_geo_ok(rest, last, {"requested_city": "Wrocław"}) is False


def test_kalwaria_lunch_refused_from_warsaw():
    last = {"name": "Łazienki", "lat": 52.215, "lng": 21.035, "city": "Warszawa"}
    rest = {
        "name": "Restauracja Góra Kalwaria",
        "lat": 51.982, "lng": 21.215,
        "city": "Góra Kalwaria",
        "address": "Góra Kalwaria",
    }
    assert _meal_restaurant_geo_ok(rest, last, {"requested_city": "Warszawa"}) is False


def test_clock_span_overrides_inflated_duration():
    hop = _tr(
        "Zamek Królewski", "Tutti Santi", "12:58", "13:03",
        km=0.4, dur=20, mode=TransitMode.WALK,
    )
    out = _svc()._sync_transit_duration_to_clock([hop], day_num=2)
    assert int(out[0].duration_min) == 5


def test_ewolucji_after_close_stripped():
    items = [_attr("Muzeum Ewolucji", "17:56", "19:31", 95, city="Warszawa")]
    out = _svc()._strip_after_hours_museums(items, day_num=8)
    assert out == []


def test_etnograficzne_after_18_stripped():
    items = [_attr(
        "Państwowe Muzeum Etnograficzne", "18:02", "19:21", 79, city="Warszawa",
    )]
    out = _svc()._strip_after_hours_museums(items, day_num=8)
    assert out == []


def test_pajak_uni_zabkowice_caps():
    assert visit_duration_hard_cap({"name": "Wystawa Pająków"}) == 60
    assert visit_duration_hard_cap({"name": "Uniwersytet Wrocławski"}) == 60
    assert visit_duration_hard_cap({"name": "Zamek w Ząbkowicach"}) == 90


def test_zabkowice_lunch_refused_from_wroclaw():
    last = {"name": "Sky Tower", "lat": 51.094, "lng": 17.019, "city": "Wrocław"}
    rest = {
        "name": "Restauracja Ząbkowice",
        "lat": 50.59, "lng": 16.81,
        "city": "Ząbkowice Śląskie",
        "address": "Ząbkowice",
    }
    assert _meal_restaurant_geo_ok(rest, last, {"requested_city": "Wrocław"}) is False


def test_cathedral_transit_overlap_healed():
    items = [
        _attr("Katedra Wrocławska", "12:00", "13:39", 99),
        _tr("Katedra Wrocławska", "Warzywniak", "13:23", "13:38",
            km=0.8, dur=15, mode=TransitMode.WALK),
    ]
    out = _svc()._remove_timeline_overlaps(items, 7)
    cat = next(it for it in out if getattr(it, "name", "") == "Katedra Wrocławska")
    hop = next(it for it in out if getattr(it, "type", None) == ItemType.TRANSIT)
    assert hop.start_time >= cat.end_time


def test_ogrod_doswiadczen_crushed_dropped():
    items = [_attr("Ogród Doświadczeń", "16:00", "16:27", 27, city="Kraków")]
    out = _svc()._drop_crushed_named_visits(items, day_num=3)
    assert out == []


def test_wedel_copy_not_museum_on_aleja():
    item = _attr(
        "Pijalnia Czekolady E. Wedel", "12:00", "12:45", 45,
        lat=52.23, lng=21.01, city="Warszawa",
        desc="muzeum przy alei Wedla 5",
        address="Aleja Wedla 5",
    )
    out = _svc()._force_known_good_poi_coords([item], day_num=1)
    desc = (getattr(out[0], "description_short", "") or "").lower()
    addr = (getattr(out[0], "address", "") or "").lower()
    assert "muzeum" not in desc
    assert "szpitalna" in addr
