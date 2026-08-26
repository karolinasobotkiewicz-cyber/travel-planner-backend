"""FIX #292 — leftover WRO/KRK/WAWA/KAT/POZ dump."""
from __future__ import annotations

from datetime import date

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
from app.domain.planner.engine import visit_duration_hard_cap
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


def _ft(start, end, dur, *, label="Czas wolny", suggestions=None):
    return FreeTimeItem.model_construct(
        type=ItemType.FREE_TIME,
        start_time=start,
        end_time=end,
        duration_min=dur,
        label=label,
        suggestions=suggestions or [],
    )


def test_botaniczny_and_jordana_repeat_keys():
    assert poi_trip_repeat_key("Ogród Botaniczny") is not None
    assert poi_trip_repeat_key("Park Jordana") == "krk_park_jordana"
    assert poi_trip_repeat_key("Park Decjusza") == "krk_park_decjusza"
    assert poi_trip_repeat_key("Cytadela") == "waw_cytadela"
    assert poi_trip_repeat_key("Park Sensoryczny") == "kat_sensoryczny"
    assert poi_trip_repeat_key("Pomnik Bamberki") == "poz_stary_rynek"


def test_wioski_swiata_closed_in_february():
    kept = {
        p["name"]
        for p in filter_by_season(
            [
                {"name": "Wioski Świata", "id": "w1", "season_fit": {"winter": 1}},
                {"name": "Wawel", "id": "w2", "season_fit": {"winter": 1}},
            ],
            "2026-02-22",
        )
    }
    assert "Wioski Świata" not in kept
    assert "Wawel" in kept


def test_polin_after_last_entry_dropped():
    items = [_attr("POLIN Muzeum Historii Żydów Polskich", "17:40", "19:40", 120,
                   city="Warszawa")]
    out = _svc()._strip_after_hours_museums(items, day_num=3)
    assert out == []


def test_mhk_sunday_after_15_dropped():
    items = [_attr("Muzeum Historii Katowic", "16:54", "18:00", 66, city="Katowice")]
    out = _svc()._strip_after_hours_museums(
        items, day_num=3, trip_date=date(2026, 2, 22),
    )
    assert out == []


def test_bamberki_and_prezydencki_caps():
    assert visit_duration_hard_cap({"name": "Pomnik Bamberki"}) == 15
    assert visit_duration_hard_cap({"name": "Pałac Prezydencki"}) == 20
    assert visit_duration_hard_cap({"name": "Jezioro Rusałka"}) == 90


def test_pixel_and_papugarnia_floors():
    pixel = _attr("Pixel XL", "14:00", "14:25", 25)
    papu = _attr("Papugarnia Katowice", "12:00", "12:25", 25)
    assert int(_svc()._cap_stretched_attraction_durations([pixel], day_num=1)[0].duration_min) >= 60
    assert int(_svc()._cap_stretched_attraction_durations([papu], day_num=1)[0].duration_min) >= 60


def test_termy_floor_and_rusalka_cap():
    termy = _attr("Termy Maltańskie", "16:00", "17:00", 60, city="Poznań")
    rusa = _attr("Jezioro Rusałka", "11:00", "13:30", 150, city="Poznań")
    assert int(_svc()._cap_stretched_attraction_durations([termy], day_num=1)[0].duration_min) >= 120
    assert int(_svc()._cap_stretched_attraction_durations([rusa], day_num=1)[0].duration_min) <= 90


def test_guliwer_denied_for_solo():
    assert should_deny_poi_for_profile(
        {"name": "Centrum Rozrywki Guliwer"},
        {"target_group": "solo", "preferences": ["active_sport"],
         "travel_style": "adventure"},
    )


def test_muzeum_slaskie_denied_water_food_relax():
    assert should_deny_poi_for_profile(
        {"name": "Muzeum Śląskie"},
        {"target_group": "couples",
         "preferences": ["water_attractions", "local_food_experience", "relaxation"],
         "travel_style": "relax"},
    )


def test_kat_parks_denied_for_underground_history():
    assert should_deny_poi_for_profile(
        {"name": "Park Chrobrego"},
        {"target_group": "friends",
         "preferences": ["underground", "history_mystery", "museum_heritage"],
         "travel_style": "cultural"},
    )


def test_84m_car_becomes_walk():
    hop = _tr(
        "Aula Leopoldina", "Chinkalnia", "14:00", "14:11",
        km=0.084, dur=11, mode=TransitMode.CAR, src="estimated_road",
    )
    out = _svc()._sanitize_walk_leg_durations([hop], {}, day_num=2)
    assert "walk" in str(getattr(out[0].mode, "value", out[0].mode)).lower()
    assert int(out[0].duration_min) <= 6


def test_5km_walk_in_5_min_becomes_car():
    hop = _tr(
        "GOjump", "The Cork", "18:00", "18:05",
        km=5.166, dur=5, mode=TransitMode.WALK,
    )
    out = _svc()._sanitize_walk_leg_durations(
        [hop], {}, day_num=3, context={"has_car": True},
    )
    mode = str(getattr(out[0].mode, "value", out[0].mode)).lower()
    assert "car" in mode
    assert int(out[0].duration_min) >= 10


def test_43km_in_10_min_car_rebuilt():
    hop = _tr(
        "Katowice", "Restauracja Poziom+", "17:00", "17:10",
        km=43.201, dur=10, mode=TransitMode.CAR, src="estimated_road",
    )
    out = _svc()._sanitize_walk_leg_durations([hop], {}, day_num=7)
    assert int(out[0].duration_min) >= 45


def test_clock_sync_small_mismatch():
    hop = _tr(
        "Aula Leopoldina", "Chinkalnia", "14:14", "14:19",
        km=0.4, dur=8, mode=TransitMode.WALK,
    )
    out = _svc()._sync_transit_duration_to_clock([hop], day_num=6)
    assert int(out[0].duration_min) == 5


def test_cultural_long_free_time_capped():
    items = [
        _attr("Hydropolis", "10:00", "12:00", 120),
        _ft("14:00", "15:50", 110),
        DayEndItem(time="19:00"),
    ]
    out = _svc()._trim_excess_free_time(
        items, {"travel_style": "cultural"}, {"day_start": "09:00"}, day_num=2,
    )
    fts = [it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME]
    assert fts
    assert all(int(it.duration_min) <= 35 for it in fts)


def test_morning_break_after_first_poi_dropped():
    items = [
        _attr("LEGO", "09:00", "10:30", 90, city="Poznań"),
        _ft("10:30", "11:27", 57, label="Poranna przerwa"),
        _attr("Maltanka", "11:30", "12:30", 60, city="Poznań"),
    ]
    out = _svc()._trim_excess_free_time(
        items, {"target_group": "family_kids"}, {"day_start": "09:00"}, day_num=2,
    )
    fts = [it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME]
    assert not fts


def test_anonymous_gap_is_named():
    items = [
        _attr("Sky Tower", "12:30", "13:57", 87),
        _attr("Wystawa Pająków", "14:25", "15:10", 45),
    ]
    out = _svc()._fill_anonymous_midday_gaps(
        items, {"day_start": "09:00", "day_end": "19:00"}, day_num=5,
    )
    fts = [it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME]
    assert fts
    assert int(fts[0].duration_min) >= 20


def test_density_warning_counts_string_type_attractions():
    day = type("D", (), {
        "day": 3,
        "items": [
            _attr("Hydropolis", "10:00", "12:00", 120),
            _attr("Ostrów Tumski", "13:00", "14:30", 90),
        ],
    })()
    warns = _svc()._day_density_warnings([day], "09:00", "19:00")
    assert not any(w.get("attractions") == 0 for w in warns)


def test_family_drink_copy_rewritten():
    items = [_ft(
        "18:00", "18:40", 40,
        suggestions=["Drink lub deser w lokalnym lokalu"],
    )]
    out = _svc()._family_safe_free_time_copy(
        items, {"target_group": "family_kids"}, day_num=1,
    )
    blob = " ".join(str(s).lower() for s in (out[0].suggestions or []))
    assert "drink" not in blob


def test_relax_lunch_floored():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="13:00",
        end_time="13:29",
        duration_min=29,
        suggestions=[],
    )
    out = _svc()._enforce_lunch_min_duration(
        [lunch], {"travel_style": "relax"}, {"day_end": "18:00"}, day_num=1,
    )
    assert int(out[0].duration_min) >= 40


def test_hala_pergola_clustered():
    items = [
        _attr("Pergola przy Hali Stulecia", "11:00", "11:40", 40),
        _attr("Świat Iluzji", "12:00", "13:00", 60),
        _attr("Hala Stulecia", "14:00", "15:00", 60),
    ]
    out = _svc()._cluster_adjacent_icons(items, day_num=2)
    names = [it.name for it in out if _is_attr(it)]
    pi, hi = names.index("Pergola przy Hali Stulecia"), names.index("Hala Stulecia")
    assert abs(hi - pi) == 1


def test_third_park_dropped():
    items = [
        _attr("Park Bednarskiego", "10:00", "11:00", 60, city="Kraków"),
        _attr("Planty", "11:30", "12:30", 60, city="Kraków"),
        _attr("Park Jordana", "13:00", "14:00", 60, city="Kraków"),
    ]
    out = _svc()._cap_same_day_green_stops(
        items, {"preferences": ["museum_heritage"]}, day_num=2,
    )
    parks = [it.name for it in out]
    assert "Park Jordana" not in parks
    assert len(parks) == 2


def test_most_swietokrzyski_copy_not_monument():
    item = _attr(
        "Most Świętokrzyski", "16:00", "16:20", 20,
        city="Warszawa", desc="Zabytek z bogatą historią",
    )
    out = _svc()._force_known_good_poi_coords([item], day_num=10)
    desc = (getattr(out[0], "description_short", "") or "").lower()
    assert "zabytek" not in desc


def _is_attr(it) -> bool:
    return getattr(it, "type", None) == ItemType.ATTRACTION
