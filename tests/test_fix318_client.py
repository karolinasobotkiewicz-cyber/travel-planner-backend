"""FIX #318 — Wrocław follow-up: geography, visit floors, morning holes.

Does not call generate_plan. Live JSON 1–10 stays in test_fix317_wroclaw_json.py.
"""
from __future__ import annotations

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    DayEndItem,
    DayPlan,
    DayStartItem,
    ItemType,
)


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur=60, *, lat=51.11, lng=17.03):
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
        address="Wrocław",
        city="Wrocław",
        cost_estimate=0,
    )


def _ctx(**extra):
    base = {
        "requested_city": "Wrocław",
        "has_car": True,
        "day_start": "09:00",
        "day_end": "19:00",
    }
    base.update(extra)
    return base


def _names(items):
    return [
        (getattr(it, "name", "") or "")
        for it in items
        if getattr(it, "type", None) == ItemType.ATTRACTION
    ]


def test_zabkowice_day_drops_topacz_and_city():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Zamek w Ząbkowicach Śląskich", "10:30", "12:30", 120,
              lat=50.589, lng=16.810),
        _attr("Muzeum Motoryzacji i Techniki Zamek Topacz", "14:00", "15:00", 60,
              lat=51.02, lng=16.95),
        _attr("Hydropolis", "16:00", "17:00", 60, lat=51.104, lng=17.056),
        DayEndItem(time="17:00"),
    ]
    out = _svc()._keep_one_satellite_region(items, day_num=3)
    names = " ".join(_names(out)).lower()
    assert "ząbkow" in names or "zabkow" in names
    assert "topacz" not in names
    assert "hydropolis" not in names


def test_city_morning_drops_glued_zabkowice():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Hala Stulecia", "09:20", "10:20", 60, lat=51.107, lng=17.077),
        _attr("Panorama Racławicka", "10:40", "11:40", 60, lat=51.110, lng=17.044),
        _attr("Zamek w Ząbkowicach Śląskich", "13:00", "15:00", 120,
              lat=50.589, lng=16.810),
        DayEndItem(time="15:00"),
    ]
    out = _svc()._keep_one_satellite_region(items, day_num=4)
    names = " ".join(_names(out)).lower()
    assert "hala" in names
    assert "panorama" in names
    assert "ząbkow" not in names and "zabkow" not in names


def test_guardian_retitles_after_dropping_topacz():
    days = [
        DayPlan(
            day=3,
            title="Zamek w Ząbkowicach Śląskich i Muzeum Motoryzacji i Techniki Zamek Topacz",
            items=[
                DayStartItem(type=ItemType.DAY_START, time="09:00"),
                _attr("Zamek w Ząbkowicach Śląskich", "10:30", "14:00", 210,
                      lat=50.589, lng=16.810),
                _attr(
                    "Muzeum Motoryzacji i Techniki Zamek Topacz",
                    "15:00", "16:00", 60, lat=51.02, lng=16.95,
                ),
                DayEndItem(time="16:00"),
            ],
        ),
    ]
    out = _svc()._guard_trip_invariants(days, _ctx(), coord_map={}, user={})
    title = (out[0].title or "").lower()
    names = " ".join(_names(out[0].items or [])).lower()
    assert "topacz" not in names
    assert "topacz" not in title
    assert "ząbkow" in title or "zabkow" in title


def test_inject_on_zabkowice_day_rejects_city_and_brzeg():
    from app.domain.models.plan import FreeTimeItem

    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Zamek w Ząbkowicach Śląskich", "10:30", "12:00", 90,
              lat=50.589, lng=16.810),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME,
            start_time="12:00", end_time="16:00", duration_min=240,
            label="Czas dla siebie", suggestions=[],
        ),
        DayEndItem(time="16:00"),
    ]
    pool = [
        {
            "id": "hydro",
            "name": "Hydropolis",
            "lat": 51.104, "lng": 17.056,
            "city": "Wrocław", "duration_min": 90,
            "tags": ["museum_heritage"],
        },
        {
            "id": "brzeg-1",
            "name": "Zamek Piastów Śląskich w Brzegu",
            "lat": 50.861, "lng": 17.467,
            "city": "Wrocław", "duration_min": 90,
            "tags": ["museum_heritage"],
        },
    ]
    ctx = _ctx(locked_satellite_kind="zabkowice", complete_daytrip=True)
    out = _svc()._inject_attraction_into_free_time(
        items, pool, ctx, {"target_group": "solo"}, day_num=3,
    )
    names = " ".join(_names(out)).lower()
    assert "brzeg" not in names
    assert "hydropolis" not in names


def test_hydropolis_crushed_to_33_is_restored_to_90():
    from app.domain.models.plan import LunchBreakItem, RestaurantSuggestion
    from app.domain.planner.time_utils import time_to_minutes

    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="10:33", end_time="11:18", duration_min=45,
        suggestions=[RestaurantSuggestion.model_construct(
            id="t", name="Taste", lat=51.11, lng=17.03,
            city="Wrocław", address="",
        )],
        label="Taste", location_context="",
    )
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Hydropolis", "10:00", "10:33", 33, lat=51.104, lng=17.056),
        lunch,
        DayEndItem(time="11:18"),
    ]
    out = _svc()._cap_stretched_attraction_durations(items, day_num=2)
    hydro = next(
        it for it in out
        if "hydropolis" in (getattr(it, "name", None) or "").lower()
    )
    assert int(hydro.duration_min) >= 90
    lunch_out = next(
        it for it in out
        if getattr(it, "type", None) == ItemType.LUNCH_BREAK
    )
    assert time_to_minutes(lunch_out.start_time) >= time_to_minutes(hydro.end_time) - 1


def test_movie_gate_floor_60():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Movie Gate", "14:00", "14:21", 21, lat=51.11, lng=17.02),
        DayEndItem(time="14:21"),
    ]
    out = _svc()._cap_stretched_attraction_durations(items, day_num=2)
    gate = next(
        it for it in out
        if "movie" in (getattr(it, "name", None) or "").lower()
    )
    assert int(gate.duration_min) >= 60


def test_zajezdnia_floor_90():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Zajezdnia Historii", "11:00", "11:45", 45, lat=51.12, lng=17.02),
        DayEndItem(time="11:45"),
    ]
    out = _svc()._cap_stretched_attraction_durations(items, day_num=3)
    z = next(
        it for it in out
        if "zajezdnia" in (getattr(it, "name", None) or "").lower()
    )
    assert int(z.duration_min) >= 90


def test_35min_before_lunch_is_eaten():
    from app.domain.models.plan import (
        FreeTimeItem, LunchBreakItem, RestaurantSuggestion, TransitItem, TransitMode,
    )
    from app.domain.planner.time_utils import time_to_minutes

    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Hala Stulecia", "10:00", "11:30", 90, lat=51.107, lng=17.077),
        TransitItem.model_construct(
            type=ItemType.TRANSIT,
            from_location="Hala Stulecia", to_location="Taste",
            start_time="11:30", end_time="11:45", duration_min=15,
            distance_km=1.2, mode=TransitMode.WALK, routing_source="estimated_walk",
        ),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME,
            start_time="11:45", end_time="12:20", duration_min=35,
            label="Czas dla siebie", suggestions=[],
        ),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="12:20", end_time="13:05", duration_min=45,
            suggestions=[RestaurantSuggestion.model_construct(
                id="t", name="Taste", lat=51.11, lng=17.03,
                city="Wrocław", address="",
            )],
            label="Taste", location_context="",
        ),
        DayEndItem(time="13:05"),
    ]
    out = _svc()._eat_long_free_time_before_attraction(
        items, day_num=4, min_ft=35, keep=15, pull_lunch=True,
    )
    fts = [
        it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME
    ]
    assert fts
    assert int(fts[0].duration_min) <= 20
    lunch = next(
        it for it in out
        if getattr(it, "type", None) == ItemType.LUNCH_BREAK
    )
    assert time_to_minutes(lunch.start_time) < time_to_minutes("12:20")


def test_pajaki_denied_for_couples_cultural():
    from app.domain.scoring.profile_poi_rules import should_deny_poi_for_profile
    poi = {"name": "Wystawa Pająków"}
    couples = {
        "target_group": "couples",
        "travel_style": "cultural",
        "preferences": ["museum_heritage", "relaxation", "local_food_experience"],
    }
    family = {
        "target_group": "family_kids",
        "travel_style": "balanced",
        "preferences": ["kids_attractions"],
        "children_age": 8,
    }
    assert should_deny_poi_for_profile(poi, couples) is True
    assert should_deny_poi_for_profile(poi, family) is False


def test_krasnale_denied_for_seniors_relax():
    from app.domain.scoring.profile_poi_rules import should_deny_poi_for_profile
    poi = {"name": "Dom Krasnali"}
    seniors = {
        "target_group": "seniors",
        "travel_style": "relax",
        "preferences": ["museum_heritage", "nature_landscape", "relaxation"],
    }
    family = {
        "target_group": "family_kids",
        "travel_style": "balanced",
        "preferences": ["kids_attractions"],
        "children_age": 8,
    }
    assert should_deny_poi_for_profile(poi, seniors) is True
    assert should_deny_poi_for_profile(poi, family) is False


def test_morning_free_time_is_not_popoludniowa():
    from app.domain.models.plan import FreeTimeItem

    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME,
            start_time="09:00", end_time="09:30", duration_min=30,
            label="Popołudniowa przerwa", suggestions=[],
        ),
        _attr("Hydropolis", "09:30", "11:00", 90, lat=51.104, lng=17.056),
        DayEndItem(time="11:00"),
    ]
    out = _svc()._name_remaining_holes(items, _ctx(), day_num=3)
    out = _svc()._relabel_free_time_by_slot(out, _ctx(), day_num=3)
    fts = [
        it for it in out
        if getattr(it, "type", None) == ItemType.FREE_TIME
    ]
    assert fts
    blob = " ".join((it.label or "").lower() for it in fts)
    assert "popołudniow" not in blob
    assert any(
        k in blob for k in ("porann", "poranek", "kawa")
    )


def test_morning_gap_before_hala_is_named():
    from app.domain.models.plan import FreeTimeItem
    from app.domain.validators.client_invariants import audit_day

    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Hala Stulecia", "10:10", "11:00", 50, lat=51.107, lng=17.077),
        DayEndItem(time="11:00"),
    ]
    out = _svc()._seal_client_hops_and_physics(items, _ctx(), day_num=2)
    codes = {d.code for d in audit_day(out, day=2, context=_ctx())}
    assert "anonymous_gap" not in codes
    assert "missing_hop" not in codes


def test_quality_first_names_hole_before_evening_ft():
    """JSON8 D6: 14:46 castle, unnamed 14:46–16:00, named FT 16:00."""
    from app.domain.models.plan import FreeTimeItem
    from app.domain.validators.client_invariants import audit_day

    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Rynek w Oławie", "13:00", "14:46", 106,
              lat=50.945, lng=17.293),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME,
            start_time="16:00", end_time="16:45", duration_min=45,
            label="Czas dla siebie", suggestions=[],
        ),
        DayEndItem(time="16:45"),
    ]
    ctx = _ctx(num_days=7, day_end="20:00")
    out = _svc()._seal_client_hops_and_physics(items, ctx, day_num=6)
    codes = {d.code for d in audit_day(out, day=6, context=ctx)}
    assert "anonymous_gap" not in codes


def test_strip_pajaki_for_couples_even_without_pool():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Bastion Sakwowy", "10:00", "11:00", 60),
        _attr("Wystawa Pająków", "11:30", "12:15", 45),
        DayEndItem(time="12:15"),
    ]
    user = {
        "target_group": "couples",
        "travel_style": "balanced",
        "preferences": ["nature_landscape", "local_food_experience", "museum_heritage"],
    }
    out = _svc()._strip_profile_denied_attractions(items, user, None, 7)
    names = " ".join(_names(out)).lower()
    assert "pająk" not in names and "pajak" not in names
    assert "bastion" in names


def test_far_city_lunch_on_satellite_day_is_not_a_teleport():
    from app.domain.models.plan import LunchBreakItem, RestaurantSuggestion
    from app.domain.validators.client_invariants import audit_day

    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Dolina Tatarska", "10:00", "10:55", 55,
              lat=51.11, lng=16.40),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK,
            start_time="12:00", end_time="13:00", duration_min=60,
            suggestions=[RestaurantSuggestion.model_construct(
                id="f", name="Restauracja Forum Kulinarne",
                lat=51.11, lng=17.03, city="Wrocław", address="",
            )],
            label="Restauracja Forum Kulinarne", location_context="",
        ),
        DayEndItem(time="13:00"),
    ]
    out = _svc()._seal_client_hops_and_physics(items, _ctx(), day_num=5)
    codes = {d.code for d in audit_day(out, day=5, context=_ctx())}
    assert "missing_hop" not in codes
    assert "anonymous_gap" not in codes

