"""FIX #301 — Poznań/Katowice hops after collapse, name match, Stare Zoo 60."""
from __future__ import annotations

from app.application.services.plan_service import (
    PlanService,
    _place_names_match,
)
from app.domain.models.plan import (
    AttractionItem,
    ItemType,
    LunchBreakItem,
    RestaurantSuggestion,
    TransitItem,
    TransitMode,
)
from app.domain.planner.engine import visit_duration_hard_cap
from app.domain.scoring.preference_coverage import poi_covers_preference_report
from app.domain.scoring.profile_poi_rules import (
    poi_trip_repeat_key,
    should_deny_poi_for_profile,
)


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur=60, *, lat=52.41, lng=16.93, city="Poznań"):
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


def test_place_names_match_restaurant_inflection():
    assert _place_names_match("GAMARDŻOBA", "GAMARDŻOBY")
    assert _place_names_match("GAMARDŻOBY", "GAMARDŻOBA")
    assert not _place_names_match("GAMARDŻOBA", "Ogród Botaniczny")


def test_lunch_hop_cannot_start_before_inflected_restaurant_ends():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="13:04",
        end_time="13:34",
        duration_min=30,
        suggestions=[
            RestaurantSuggestion.model_construct(
                id="g",
                name="GAMARDŻOBA",
                lat=52.41,
                lng=16.93,
                city="Poznań",
            )
        ],
    )
    items = [
        lunch,
        _tr("GAMARDŻOBY", "Ogród Botaniczny", "13:25", "13:40", km=1.2, dur=15),
        _attr("Ogród Botaniczny", "13:40", "15:00", 80, lat=52.42, lng=16.88),
    ]
    out = _svc()._snap_transits_to_previous_stop_end(items, day_num=1)
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert hops[0].start_time >= "13:34"


def test_abutting_attractions_get_a_hop():
    items = [
        _attr("Park Cytadela", "15:02", "16:32", 90, lat=52.4215, lng=16.9360),
        _attr("Stary Rynek", "16:32", "17:30", 58, lat=52.4082, lng=16.9346),
    ]
    out = _svc()._ensure_stop_to_stop_legs(
        items, {}, {"has_car": True, "requested_city": "Poznań"}, day_num=1,
    )
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert hops
    assert "cytadel" in (hops[0].from_location or "").lower()
    assert "rynek" in (hops[0].to_location or "").lower()


def test_hop_to_already_visited_is_dropped():
    items = [
        _attr("Ogród Botaniczny", "10:00", "11:00", 60, lat=52.42, lng=16.88),
        _attr("Stary Rynek", "16:00", "16:32", 32),
        _tr("Stary Rynek", "Ogród Botaniczny", "16:32", "16:47", km=5.6, dur=15),
        _tr("Stary Rynek", "Drevny Kocur", "16:47", "17:00", km=0.4, dur=13),
        _attr("Drevny Kocur", "17:00", "18:00", 60),
    ]
    out = _svc()._drop_hops_to_already_visited(items, day_num=1)
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert all("botanic" not in (h.to_location or "").lower() for h in hops)
    assert any("drevny" in (h.to_location or "").lower() for h in hops)


def test_self_leg_palmiarnia_is_stripped_then_next_kept():
    items = [
        _attr("Palmiarnia Poznańska", "11:00", "12:00", 60, lat=52.42, lng=16.90),
        _tr("Palmiarnia Poznańska", "Palmiarnia Poznańska", "12:00", "12:11", km=0, dur=11),
        _attr("Muzeum Armii Poznań", "12:20", "13:20", 60, lat=52.41, lng=16.93),
    ]
    dropped = _svc()._drop_hops_to_already_visited(items, day_num=2)
    hops = [it for it in dropped if it.type == ItemType.TRANSIT]
    assert hops == []
    filled = _svc()._ensure_stop_to_stop_legs(
        dropped, {}, {"has_car": True, "requested_city": "Poznań"}, day_num=2,
    )
    hops2 = [it for it in filled if it.type == ItemType.TRANSIT]
    assert hops2
    assert "armii" in (hops2[0].to_location or "").lower()


def test_stare_zoo_hard_cap_is_60():
    assert visit_duration_hard_cap({"name": "Stare Zoo"}, for_scheduling=True) == 60
    items = [
        _attr("Stare Zoo", "10:00", "12:30", 150, lat=52.41, lng=16.90),
    ]
    out = _svc()._cap_stretched_attraction_durations(
        items, day_num=1, user={"target_group": "family_kids", "travel_style": "balanced"},
    )
    assert int(out[0].duration_min) <= 60


def test_ostrow_tumski_poznan_drops_wroclaw_address():
    poi = AttractionItem.model_construct(
        type=ItemType.ATTRACTION,
        poi_id="ostrow",
        name="Ostrów Tumski",
        description_short="",
        start_time="10:00",
        end_time="11:00",
        duration_min=60,
        lat=51.1145,
        lng=17.0465,
        address="Ostrów Tumski, Wrocław, Wrocław, Poland",
        city="Poznań",
        cost_estimate=0,
    )
    out = _svc()._force_known_good_poi_coords([poi], day_num=2)
    assert "wrocław" not in (out[0].address or "").lower()
    assert "wroclaw" not in (out[0].address or "").lower()
    assert "poznań" in (out[0].address or "").lower() or "poznan" in (out[0].address or "").lower()
    assert abs(float(out[0].lat) - 52.4116) < 0.01


def test_second_church_same_day_is_stripped():
    items = [
        _attr("Kościół św. Anny", "10:00", "10:40", 40, lat=50.26, lng=19.02, city="Katowice"),
        _attr("Kościół Mariacki", "11:00", "11:40", 40, lat=50.26, lng=19.03, city="Katowice"),
        _attr("Muzeum Śląskie", "12:00", "13:30", 90, lat=50.26, lng=19.03, city="Katowice"),
    ]
    out = _svc()._strip_second_church_same_day(items, day_num=1)
    churches = [
        it for it in out
        if "kościół" in (getattr(it, "name", "") or "").lower()
        or "kosciol" in (getattr(it, "name", "") or "").lower()
    ]
    assert len(churches) == 1
    assert "anny" in churches[0].name.lower()


def test_stale_meal_context_is_reset_to_last_stop():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="13:00",
        end_time="14:00",
        duration_min=60,
        location_context="Wodny Park Tychy",
        suggestions=[],
    )
    items = [
        _attr("AnimalWorld", "11:00", "12:30", 90, lat=50.32, lng=18.78, city="Zabrze"),
        lunch,
    ]
    out = _svc()._reset_stale_meal_location_context(items, day_num=2)
    meals = [it for it in out if it.type == ItemType.LUNCH_BREAK]
    assert "animalworld" in (meals[0].location_context or "").lower()


def test_soho_does_not_keep_animalworld_context():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="19:00",
        end_time="20:00",
        duration_min=60,
        location_context="AnimalWorld",
        suggestions=[],
    )
    items = [
        _attr("SOHO", "18:00", "19:00", 60, lat=50.26, lng=19.02, city="Katowice"),
        lunch,
    ]
    out = _svc()._reset_stale_meal_location_context(items, day_num=2)
    meals = [it for it in out if it.type == ItemType.LUNCH_BREAK]
    assert "soho" in (meals[0].location_context or "").lower()


def test_stacked_olio_hops_keep_wilsona():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="13:00",
        end_time="14:00",
        duration_min=60,
        suggestions=[
            RestaurantSuggestion.model_construct(
                id="olio", name="Olio", lat=52.41, lng=16.93, city="Poznań",
            )
        ],
    )
    items = [
        lunch,
        _tr("Olio", "Rogalowe Muzeum", "14:00", "14:10", km=1.0, dur=10),
        _tr("Olio", "Park Wilsona", "14:10", "14:20", km=3.4, dur=10),
        _attr("Park Wilsona", "14:20", "15:20", 60, lat=52.40, lng=16.91),
    ]
    out = _svc()._collapse_stacked_transits(items, day_num=2)
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert len(hops) == 1
    assert "wilsona" in (hops[0].to_location or "").lower()


def test_dolina_trzech_stawow_covers_water():
    poi = {"name": "Dolina Trzech Stawów", "tags": ["city_park"]}
    assert poi_covers_preference_report(poi, "water_attractions")


def test_animalworld_denied_for_seniors_museum_nature():
    denied = should_deny_poi_for_profile(
        {"name": "AnimalWorld"},
        {
            "target_group": "seniors",
            "travel_style": "relax",
            "preferences": ["museum_heritage", "nature_landscape", "relaxation"],
        },
    )
    assert denied is True


def test_uniqueness_keys_for_poz_kat_icons():
    assert poi_trip_repeat_key("Stary Rynek") == "poz_stary_rynek"
    assert poi_trip_repeat_key("Park Wilsona") == "poz_park_wilsona"
    assert poi_trip_repeat_key("Giszowiec") == "kat_giszowiec"
    assert poi_trip_repeat_key("Jezioro Paprocany") == "kat_paprocany"
