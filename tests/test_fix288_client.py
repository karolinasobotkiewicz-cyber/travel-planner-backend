"""FIX #288 — Wrocław / Warszawa / Kraków / Katowice / Poznań client notes."""
from __future__ import annotations

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    DayEndItem,
    DinnerBreakItem,
    FreeTimeItem,
    ItemType,
    TransitItem,
    TransitMode,
)
from app.domain.planner.engine import (
    _meal_restaurant_geo_ok,
    choose_duration,
    should_block_city_daytrip_poi,
    visit_duration_hard_cap,
)
from app.domain.planner.explainability import _explain_category_highlight
from app.domain.scoring.preference_coverage import poi_covers_preference_report
from app.domain.scoring.profile_poi_rules import (
    poi_trip_repeat_key,
    should_deny_poi_for_profile,
)


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur=60, *, lat=51.11, lng=17.03, city="Wrocław"):
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


def test_seven_day_blocks_day3_outing():
    ctx = {
        "requested_city": "Wrocław",
        "num_days": 7,
        "current_day_num": 3,
        "trip_type": "city_tourism",
        "preferences": ["nature_landscape", "museum_heritage"],
    }
    assert should_block_city_daytrip_poi(
        {"name": "Arboretum Wojsławice", "city": "Niemcza"}, ctx,
    ) is True
    ctx["current_day_num"] = 4
    assert should_block_city_daytrip_poi(
        {"name": "Arboretum Wojsławice", "city": "Niemcza"}, ctx,
    ) is False


def test_two_day_wroclaw_blocks_niemcza():
    ctx = {
        "requested_city": "Wrocław",
        "num_days": 2,
        "current_day_num": 2,
        "trip_type": "city_tourism",
    }
    assert should_block_city_daytrip_poi(
        {"name": "Rynek w Niemczy", "city": "Niemcza"}, ctx,
    ) is True


def test_five_day_day3_still_allowed():
    ctx = {
        "requested_city": "Kraków",
        "num_days": 5,
        "current_day_num": 3,
        "trip_type": "city_tourism",
    }
    assert should_block_city_daytrip_poi(
        {"name": "Zamek Tenczyn", "city": "Rudno"}, ctx,
    ) is False


def test_wawel_not_poznan_pin():
    item = _attr(
        "Zamek Królewski na Wawelu",
        "11:00",
        "13:00",
        120,
        lat=52.4094,
        lng=16.9315,
        city="Kraków",
    )
    out = _svc()._force_known_good_poi_coords([item], day_num=1)
    assert abs(float(out[0].lat) - 50.0540) < 0.01
    assert abs(float(out[0].lng) - 19.9352) < 0.02
    assert "Kraków" in (out[0].city or out[0].address or "")


def test_gniezno_city_stamped():
    item = _attr(
        "Katedra Gnieźnieńska",
        "11:00",
        "12:00",
        60,
        lat=52.5372,
        lng=17.5967,
        city="Poznań",
    )
    out = _svc()._force_known_good_poi_coords([item], day_num=1)
    assert (out[0].city or "").lower() == "gniezno" or "gniezno" in (
        out[0].address or ""
    ).lower()


def test_day_end_snaps_to_dinner():
    items = [
        _attr("Rynek we Wrocławiu", "17:00", "18:00", 60),
        DinnerBreakItem.model_construct(
            type=ItemType.DINNER_BREAK,
            start_time="18:18",
            end_time="19:20",
            duration_min=62,
            suggestions=[],
        ),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME,
            start_time="19:20",
            end_time="19:30",
            duration_min=10,
            label="Bufor",
            suggestions=[],
            is_technical_buffer=True,
        ),
        DayEndItem(time="19:09"),
    ]
    out = _svc()._reconcile_day_end_marker(
        items, {"day_end": "19:00"}, day_num=2,
    )
    ends = [it for it in out if _item_is_day_end(it)]
    assert ends and ends[0].time == "19:20"
    assert not any(bool(getattr(it, "is_technical_buffer", False)) for it in out)


def _item_is_day_end(it) -> bool:
    return getattr(getattr(it, "type", None), "value", getattr(it, "type", "")) in (
        ItemType.DAY_END.value, "day_end",
    )


def test_free_time_not_after_dinner_before_dinner():
    items = [
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME,
            start_time="17:25",
            end_time="18:38",
            duration_min=73,
            label="Po kolacji na luzie",
            suggestions=["x"],
        ),
        DinnerBreakItem.model_construct(
            type=ItemType.DINNER_BREAK,
            start_time="19:16",
            end_time="20:00",
            duration_min=44,
            suggestions=[],
        ),
    ]
    out = _svc()._relabel_free_time_by_slot(
        items, {"day_end": "20:00"}, day_num=1,
    )
    ft = out[0]
    assert "kolacji" not in (ft.label or "").lower()


def test_morning_free_time_not_afternoon():
    items = [
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME,
            start_time="11:05",
            end_time="11:21",
            duration_min=16,
            label="Popołudniowa przerwa",
            suggestions=["x"],
        ),
    ]
    out = _svc()._relabel_free_time_by_slot(
        items, {"day_end": "20:00"}, day_num=1,
    )
    assert "popołudniow" not in (out[0].label or "").lower()
    assert "popoludniow" not in (out[0].label or "").lower()


def test_duration_caps_and_floors():
    assert visit_duration_hard_cap({"name": "Katedra Wawelska"}) == 40
    assert visit_duration_hard_cap({"name": "Barbakan"}) == 40
    assert visit_duration_hard_cap({"name": "Pomnik Smoka Wawelskiego"}) == 15
    assert visit_duration_hard_cap({"name": "Pałac Krzysztofory"}) == 90
    assert visit_duration_hard_cap({"name": "Domy Kupieckie"}) == 15
    assert visit_duration_hard_cap({"name": "Zamek Cesarski"}) == 75
    assert visit_duration_hard_cap({"name": "Legendia"}) == 150
    dur = choose_duration(
        {"name": "Legendia", "time_min": 60, "time_max": 180, "type": "amusement"},
        10 * 60, 19 * 60, True,
    )
    assert dur >= 120
    zaj = choose_duration(
        {
            "name": "Centrum Historii Zajezdnia",
            "time_min": 30, "time_max": 120, "type": "museum",
        },
        10 * 60, 19 * 60, True,
    )
    assert 60 <= zaj <= 120


def test_profile_denies():
    cultural = {
        "target_group": "couples",
        "travel_style": "cultural",
        "preferences": ["museum_heritage", "relaxation", "local_food_experience"],
    }
    assert should_deny_poi_for_profile({"name": "Gokarty Wrocław"}, cultural)
    assert should_deny_poi_for_profile({"name": "Let Me Out"}, cultural)
    seniors = {
        "target_group": "seniors",
        "travel_style": "relax",
        "preferences": ["museum_heritage", "nature_landscape", "relaxation"],
    }
    assert should_deny_poi_for_profile({"name": "Wystawa Pająków"}, seniors)
    water = {
        "target_group": "couples",
        "travel_style": "relax",
        "preferences": ["water_attractions", "local_food_experience", "relaxation"],
    }
    assert should_deny_poi_for_profile({"name": "Panorama Racławicka"}, water)
    family = {
        "target_group": "family_kids",
        "travel_style": "balanced",
        "preferences": ["kids_attractions", "nature_landscape"],
        "children_age": 8,
    }
    assert should_deny_poi_for_profile(
        {"name": "Muzeum Powstania Warszawskiego"}, family,
    )
    winter = {
        "target_group": "couples",
        "travel_style": "relax",
        "preferences": ["nature_landscape", "relaxation"],
        "start_date": "2026-02-20",
    }
    assert should_deny_poi_for_profile({"name": "Ogród Doświadczeń"}, winter)
    assert should_deny_poi_for_profile({"name": "Jaskinia Ciemna"}, winter)


def test_pajaki_not_museum_coverage():
    poi = {
        "name": "Wystawa Pająków",
        "tags": "museum,interactive_exhibition,science_museum",
    }
    assert poi_covers_preference_report(poi, "museum_heritage") is False


def test_why_selected_not_interactive_exhibits():
    assert "Interaktywne eksponaty" not in (
        _explain_category_highlight({"name": "Movie Gate"}, {}) or ""
    )
    assert "Interaktywne eksponaty" not in (
        _explain_category_highlight({"name": "Muzeum Pana Tadeusza"}, {}) or ""
    )


def test_repeat_keys():
    assert poi_trip_repeat_key("Loopys World") == poi_trip_repeat_key("Loopys")
    assert poi_trip_repeat_key("Zakrzówek") == "krk_zakrzowek"
    assert poi_trip_repeat_key("FunHouse") == "kat_funhouse"


def test_micro_walk_not_75_min():
    hop = TransitItem.model_construct(
        type=ItemType.TRANSIT,
        from_location="Rynek",
        to_location="Katedra",
        start_time="12:00",
        end_time="13:15",
        duration_min=75,
        distance_km=0.184,
        mode=TransitMode.WALK,
        routing_source="estimated_walk",
    )
    out = _svc()._sanitize_walk_leg_durations([hop], {}, day_num=1)
    assert int(out[0].duration_min) <= 8
    assert "walk" in str(getattr(out[0].mode, "value", out[0].mode)).lower()


def test_far_return_not_10_min():
    hop = TransitItem.model_construct(
        type=ItemType.TRANSIT,
        from_location="Niemcza",
        to_location="Wrocław centrum",
        start_time="19:05",
        end_time="19:15",
        duration_min=55,
        distance_km=66.283,
        mode=TransitMode.CAR,
        routing_source="estimated_road",
    )
    out = _svc()._fix_implausible_transit_duration(hop, {}, {"has_car": True})
    span = 0
    try:
        from app.domain.planner.time_utils import time_to_minutes
        span = time_to_minutes(out.end_time) - time_to_minutes(out.start_time)
    except Exception:
        span = int(out.duration_min or 0)
    assert span >= 45
    assert int(out.duration_min or 0) >= 45


def test_meal_geo_rejects_8km_city_hop():
    last = {"name": "Ogród Botaniczny", "lat": 52.23, "lng": 21.02, "city": "Warszawa"}
    rest = {
        "name": "Restauracja U Jakuba",
        "lat": 52.29, "lng": 20.93, "city": "Warszawa",
    }
    assert _meal_restaurant_geo_ok(rest, last, {"requested_city": "Warszawa"}) is False


def test_clamp_keeps_modest_overrun():
    items = [
        _attr("Ogród Japoński", "15:31", "16:16", 45),
        DayEndItem(time="16:00"),
    ]
    clamped = _svc()._clamp_timeline_to_day_end(
        items, {"day_end": "16:00"}, day_num=1,
    )
    garden = [it for it in clamped if getattr(it, "name", "") == "Ogród Japoński"][0]
    assert garden.end_time == "16:00"
    out = _svc()._reconcile_day_end_marker(
        clamped, {"day_end": "16:00"}, day_num=1,
    )
    ends = [it for it in out if _item_is_day_end(it)]
    assert ends and ends[0].time == "16:00"
