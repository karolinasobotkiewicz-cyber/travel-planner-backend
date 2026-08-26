"""FIX #296 — Katowice leftover: dupes, far parks, meals, walk/car, kids."""
from __future__ import annotations

from types import SimpleNamespace

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    ItemType,
    LunchBreakItem,
    TransitItem,
    TransitMode,
)
from app.domain.planner.engine import poi_geo_region_key, should_block_city_daytrip_poi
from app.domain.planner.explainability import _explain_category_highlight
from app.domain.scoring.profile_poi_rules import (
    poi_trip_repeat_key,
    should_deny_poi_for_profile,
)


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur=60, *, lat=50.26, lng=19.02, city="Katowice"):
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


def test_park_slaski_and_chopina_repeat_keys():
    assert poi_trip_repeat_key("Park Śląski") == "kat_park_slaski"
    assert poi_trip_repeat_key("Park Chopina") == "kat_park_chopina"
    assert poi_trip_repeat_key("Park Chrobrego") == "kat_park_chrobrego"
    assert poi_trip_repeat_key("Park im. Rotmistrza Pileckiego") == "kat_park_pilecki"


def test_park_slaski_stripped_on_later_day():
    def _ns(name):
        return SimpleNamespace(
            type=ItemType.ATTRACTION,
            name=name,
            start_time="11:00",
            end_time="12:00",
            duration_min=60,
            poi_id=None,
            lat=50.29,
            lng=18.98,
        )

    days = [
        SimpleNamespace(
            day=1, quality_badges=None, date=None, weekday=None,
            items=[_ns("Park Śląski")],
        ),
        SimpleNamespace(
            day=3, quality_badges=None, date=None, weekday=None,
            items=[_ns("Park Śląski"), _ns("Nikiszowiec")],
        ),
    ]
    out = _svc()._strip_cross_day_trip_repeats(days)
    d3 = [getattr(it, "name", "") for it in (out[1].items or [])]
    assert not any("ląski" in n.lower() or "slaski" in n.lower() for n in d3)
    assert any("Nikiszowiec" in n for n in d3)


def test_gliwice_parks_are_gliwice_region():
    assert poi_geo_region_key({"name": "Park Chopina", "city": "Katowice"}) == "region_gliwice"
    assert poi_geo_region_key({"name": "Park Chrobrego", "city": "Gliwice"}) == "region_gliwice"
    assert poi_geo_region_key(
        {"name": "Park im. Rotmistrza Pileckiego", "city": "Katowice"}
    ) == "region_gliwice"


def test_3day_katowice_blocks_gliwice_park_on_day1():
    ctx = {
        "requested_city": "Katowice",
        "num_days": 3,
        "current_day_num": 1,
        "preferences": ["museum_heritage", "relaxation"],
    }
    assert should_block_city_daytrip_poi(
        {"name": "Park Chopina", "city": "Katowice", "lat": 50.30, "lng": 18.67},
        ctx,
    ) is True


def test_lonely_park_chopina_37km_dropped():
    items = [
        _attr("Muzeum Śląskie", "10:00", "12:00", 120),
        _tr(
            "Muzeum Śląskie", "Park Chopina",
            "12:00", "12:50", km=37.9, dur=50,
        ),
        _attr(
            "Park Chopina", "12:50", "13:30", 40,
            lat=50.297, lng=18.665, city="Gliwice",
        ),
    ]
    out = _svc()._drop_thin_lonely_far_stops(items, day_num=1)
    names = [getattr(it, "name", "") for it in out]
    assert not any("Chopina" in n for n in names)
    assert any("Śląskie" in n or "Slaskie" in n for n in names)


def test_chrobrego_70km_for_49min_dropped():
    items = [
        _attr("Nikiszowiec", "10:00", "11:00", 60),
        _tr(
            "Nikiszowiec", "Park Chrobrego",
            "11:00", "12:33", km=70.0, dur=93,
        ),
        _attr(
            "Park Chrobrego", "12:33", "13:22", 49,
            lat=50.29, lng=18.67, city="Gliwice",
        ),
    ]
    out = _svc()._drop_thin_lonely_far_stops(items, day_num=3)
    names = [getattr(it, "name", "") for it in out]
    assert not any("Chrobrego" in n for n in names)


def test_gliwice_then_nikiszowiec_drops_the_park():
    items = [
        _attr(
            "Park Chrobrego", "10:00", "11:00", 60,
            lat=50.29, lng=18.67, city="Gliwice",
        ),
        _tr(
            "Park Chrobrego", "Nikiszowiec",
            "11:00", "12:45", km=41.78, dur=105,
        ),
        _attr("Nikiszowiec", "12:45", "13:10", 25),
    ]
    out = _svc()._drop_post_far_excursion_lonely_city_stop(items, day_num=3)
    names = [getattr(it, "name", "") for it in out]
    assert not any("Chrobrego" in n for n in names)
    assert any("Nikiszowiec" in n for n in names)


def test_same_day_gliwice_and_zabrze_keeps_one():
    items = [
        _attr("Park Chopina", "10:00", "11:00", 60, city="Gliwice"),
        _attr("Kopalnia Guido", "13:00", "15:00", 120, city="Zabrze"),
        _attr("Willa Caro", "16:00", "17:00", 60, city="Gliwice"),
    ]
    out = _svc()._cap_same_day_satellite_kinds(items, day_num=3)
    names = [getattr(it, "name", "") for it in out]
    has_gliwice = any("Chopina" in n or "Caro" in n for n in names)
    has_zabrze = any("Guido" in n for n in names)
    assert has_gliwice and not has_zabrze


def test_park_only_gliwice_satellite_dropped():
    items = [
        _attr("Planetarium Śląskie", "10:00", "12:00", 120),
        _tr(
            "Planetarium Śląskie", "Park Chopina",
            "12:00", "12:44", km=33.0, dur=44,
        ),
        _attr("Park Chopina", "12:44", "13:30", 46, city="Gliwice"),
        _attr("Park Chrobrego", "14:00", "15:00", 60, city="Gliwice"),
    ]
    out = _svc()._drop_park_only_far_satellite(items, day_num=4)
    names = [getattr(it, "name", "") for it in out]
    assert any("Planetarium" in n for n in names)
    assert not any("Chopina" in n or "Chrobrego" in n for n in names)


def test_teznia_47km_30min_dropped():
    items = [
        _attr("TePFactor", "10:00", "12:00", 120),
        _tr("TePFactor", "Tężnia solankowa", "12:00", "13:54", km=47.0, dur=114),
        _attr("Tężnia solankowa", "13:54", "14:24", 30),
    ]
    out = _svc()._drop_thin_lonely_far_stops(items, day_num=2)
    names = [getattr(it, "name", "") for it in out]
    assert not any("ężnia" in n or "eznia" in n.lower() for n in names)


def test_short_city_car_becomes_walk():
    hop = _tr(
        "Rynek", "Olio", "13:00", "13:13",
        km=0.298, dur=13, mode=TransitMode.CAR,
    )
    out = _svc()._force_short_city_hops_walk([hop], day_num=2)
    mode = str(getattr(out[0].mode, "value", out[0].mode)).lower()
    assert "walk" in mode


def test_41km_walk_5min_becomes_car():
    hop = _tr(
        "A", "B", "14:00", "14:05",
        km=41.6, dur=5, mode=TransitMode.WALK, src="estimated_walk",
    )
    out = _svc()._sanitize_walk_leg_durations(
        [hop], {}, day_num=7, context={"has_car": True},
    )
    mode = str(getattr(out[0].mode, "value", out[0].mode)).lower()
    assert "car" in mode
    assert int(out[0].duration_min) >= 40


def test_lunch_floor_for_four_people():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="13:00",
        end_time="13:28",
        duration_min=28,
        suggestions=[],
    )
    out = _svc()._enforce_lunch_min_duration(
        [lunch],
        {"target_group": "friends", "travel_style": "adventure", "group_size": 4},
        {},
        day_num=2,
    )
    assert int(out[0].duration_min) >= 45


def test_muzeum_historii_denied_for_family():
    assert should_deny_poi_for_profile(
        {"name": "Muzeum Historii Katowic"},
        {"target_group": "family_kids", "preferences": ["kids_attractions"], "children_age": 5},
    ) is True


def test_skansen_denied_for_preschooler():
    assert should_deny_poi_for_profile(
        {"name": "Górnośląski Park Etnograficzny"},
        {"target_group": "family_kids", "preferences": ["kids_attractions"], "children_age": 5},
    ) is True


def test_adventure_denies_gliwice_lawn():
    assert should_deny_poi_for_profile(
        {"name": "Park Chopina"},
        {
            "target_group": "friends",
            "travel_style": "adventure",
            "preferences": ["active_sport", "history_mystery"],
        },
    ) is True


def test_browar_is_not_evening_copy():
    reason = _explain_category_highlight(
        {"name": "Browar Mariacki", "tags": ["nightlife", "brewery"]},
        {"target_group": "solo"},
    )
    assert reason is None or "wieczór" not in reason.lower()
    assert reason is None or "browar" in reason.lower()
