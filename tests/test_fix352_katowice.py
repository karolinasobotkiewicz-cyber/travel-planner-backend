"""FIX #352 — Katowice Wilson city, Pijalnia GPS, brewery-for-kids, car hub."""
from __future__ import annotations


def _svc():
    from app.application.services.plan_service import PlanService
    from app.infrastructure.repositories.poi_repository import POIRepository
    return PlanService(POIRepository("data/zakopane.xlsx"))


def test_szyb_wilson_is_katowice_not_chorzow():
    from app.application.services.plan_service import (
        _satellite_city_for_stop, _timeline_satellite_kind,
    )

    assert _satellite_city_for_stop("Galeria Szyb Wilson") == "Katowice"
    assert _timeline_satellite_kind("Galeria Szyb Wilson") is None
    assert _timeline_satellite_kind("Park Śląski") == "chorzow"


def test_pijalnia_without_wedel_snaps_to_katowice():
    from app.domain.models.plan import AttractionItem, ItemType

    svc = _svc()
    items = [
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="p", name="Pijalnia Czekolady",
            description_short="", why_selected=["x"],
            start_time="16:00", end_time="16:40", duration_min=40,
            lat=52.2335, lng=21.0168, city="Katowice",
            address="Katowice",
        ),
    ]
    out = svc._force_known_good_poi_coords(items, day_num=3)
    it = out[0]
    assert abs(float(it.lat) - 50.2584) < 0.02
    assert abs(float(it.lng) - 19.0184) < 0.02


def test_browar_is_dropped_for_family_kids():
    from app.domain.models.plan import AttractionItem, DayEndItem, DayStartItem, ItemType

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Browar Mariacki",
            description_short="", why_selected=["x"],
            start_time="14:00", end_time="15:00", duration_min=60,
            lat=50.259, lng=19.021, city="Katowice",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {
        "requested_city": "Katowice", "group_type": "family_kids",
        "children_age": 8,
    }
    out = svc._drop_remaining_alcohol_for_kids(items, ctx, day_num=1)
    names = [getattr(it, "name", "") for it in out]
    assert not any("Browar" in n for n in names)


def test_first_katowice_car_hop_does_not_adopt_current_stop():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="09:00", end_time="09:12",
            duration_min=12, from_location="Katowice",
            to_location="Spodek", mode=TransitMode.WALK, distance_km=0.8,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="s", name="Spodek",
            description_short="", why_selected=["x"],
            start_time="09:12", end_time="10:00", duration_min=48,
            lat=50.266, lng=19.023, city="Katowice",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="13:40", end_time="13:55",
            duration_min=15, from_location="Spodek",
            to_location="Park Śląski", mode=TransitMode.CAR, distance_km=5.0,
        ),
        DayEndItem(time="18:00"),
    ]
    ctx = {"requested_city": "Katowice", "has_car": True}
    out = svc._seal_remaining_car_token(items, {}, ctx, day_num=1)
    cars = [
        it for it in out
        if str(getattr(getattr(it, "type", None), "value", "")) == "transit"
        and "car" in str(getattr(getattr(it, "mode", None), "value", "")).lower()
    ]
    assert cars
    assert "spodek" not in (getattr(cars[0], "from_location", "") or "").lower()


def test_generic_dinner_gets_a_restaurant_name():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, DinnerBreakItem, ItemType,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="s", name="Spodek",
            description_short="", why_selected=["x"],
            start_time="09:12", end_time="10:00", duration_min=48,
            lat=50.266, lng=19.023, city="Katowice",
        ),
        DinnerBreakItem.model_construct(
            type=ItemType.DINNER_BREAK, start_time="18:00", end_time="19:00",
            duration_min=60, suggestions=[], label="Kolacja",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Katowice", "restaurants_available": []}
    out = svc._fill_katowice_meal_restaurants(items, ctx, day_num=1)
    dinners = [
        it for it in out
        if str(getattr(getattr(it, "type", None), "value", "")) == "dinner_break"
    ]
    assert dinners
    d0 = dinners[0]
    label = (getattr(d0, "label", "") or "").strip().lower()
    sugg = getattr(d0, "suggestions", None) or []
    assert sugg or label not in ("kolacja", "dinner", "posiłek", "posilek")


def test_same_place_hop_is_dropped():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="p", name="Planetarium Śląskie",
            description_short="", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=50.291, lng=18.993, city="Chorzów",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:08",
            duration_min=8, from_location="Planetarium Śląskie",
            to_location="Planetarium Śląskie", mode=TransitMode.CAR,
            distance_km=1.6,
        ),
        DayEndItem(time="18:00"),
    ]
    ctx = {"requested_city": "Katowice"}
    out = svc._drop_remaining_self_hops(items, ctx, day_num=1)
    hops = [
        it for it in out
        if str(getattr(getattr(it, "type", None), "value", "")) == "transit"
    ]
    assert not hops


def test_glue_ignores_opening_floor_on_long_inbound_gap():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="13:40", end_time="14:07",
            duration_min=27, from_location="Katowice",
            to_location="Śląskie Centrum", mode=TransitMode.CAR, distance_km=8.0,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="c", name="Śląskie Centrum",
            description_short="", why_selected=["x"],
            start_time="15:33", end_time="16:33", duration_min=60,
            lat=50.264, lng=18.975, city="Chorzów",
        ),
        DayEndItem(time="21:00"),
    ]
    ctx = {"requested_city": "Katowice"}
    out = svc._glue_remaining_visit_to_inbound(items, ctx, day_num=1)
    vis = next(it for it in out if getattr(it, "name", "") == "Śląskie Centrum")
    assert vis.start_time == "14:07"


def test_adjacent_free_time_is_replaced_as_one_hole():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, FreeTimeItem, ItemType,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="s", name="Spodek",
            description_short="", why_selected=["x"],
            start_time="09:12", end_time="10:00", duration_min=48,
            lat=50.266, lng=19.023, city="Katowice",
        ),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME, start_time="10:00", end_time="10:50",
            duration_min=50, label="czas wolny",
        ),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME, start_time="10:50", end_time="11:45",
            duration_min=55, label="czas wolny",
        ),
        DayEndItem(time="18:00"),
    ]
    ctx = {"requested_city": "Katowice"}
    out = svc._replace_katowice_long_free_time(items, ctx, day_num=1)
    names = [getattr(it, "name", "") for it in out]
    assert any(n and n != "Spodek" for n in names if n)


def test_finish_names_sixty_minute_prefix_hole():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem,
        TransitMode,
    )
    from app.domain.validators.client_invariants import audit_day

    svc = _svc()
    items = [
        DayStartItem(time="09:30"),
        TransitItem(
            type=ItemType.TRANSIT, start_time="09:30", end_time="09:50",
            duration_min=20, mode=TransitMode.CAR,
            from_location="Katowice", to_location="Park Śląski",
            distance_km=6.0,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="p", name="Park Śląski",
            description_short="", why_selected=["x"],
            start_time="09:50", end_time="11:20", duration_min=90,
            lat=50.28, lng=18.97, city="Chorzów",
        ),
        TransitItem(
            type=ItemType.TRANSIT, start_time="12:20", end_time="12:30",
            duration_min=10, mode=TransitMode.WALK,
            from_location="Park Śląski", to_location="Park Kościuszki",
            distance_km=0.8, routing_source="long_ft_fill",
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="k", name="Park Kościuszki",
            description_short="", why_selected=["x"],
            start_time="12:30", end_time="13:10", duration_min=40,
            lat=50.2465, lng=19.0047, city="Katowice",
        ),
        DayEndItem(time="13:15"),
    ]
    ctx = {
        "requested_city": "Katowice", "has_car": True,
        "day_start": "09:30", "day_end": "13:15",
    }
    out = svc._finish_katowice_client_mail(items, ctx, day_num=5)
    codes = {d.code for d in audit_day(out, day=5, context=ctx)}
    assert "anonymous_gap" not in codes


def test_finish_drops_visit_that_starts_on_return_to_car():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, FreeTimeItem, ItemType,
        TransitItem, TransitMode,
    )
    from app.domain.validators.client_invariants import audit_day

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        TransitItem(
            type=ItemType.TRANSIT, start_time="09:00", end_time="09:11",
            duration_min=11, mode=TransitMode.CAR,
            from_location="Katowice", to_location="Muzeum Historii Katowic",
            distance_km=4.0,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="m", name="Muzeum Historii Katowic",
            description_short="", why_selected=["x"],
            start_time="09:11", end_time="10:00", duration_min=49,
            lat=50.259, lng=19.021, city="Katowice",
        ),
        TransitItem(
            type=ItemType.TRANSIT, start_time="10:00", end_time="10:09",
            duration_min=9, mode=TransitMode.WALK,
            from_location="Muzeum Historii Katowic", to_location="Park Chrobrego",
            distance_km=0.5,
        ),
        TransitItem(
            type=ItemType.TRANSIT, start_time="10:09", end_time="10:18",
            duration_min=9, mode=TransitMode.WALK,
            from_location="Park Chrobrego", to_location="Muzeum Historii Katowic",
            distance_km=0.5, routing_source="return_to_car",
        ),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME, start_time="10:18", end_time="11:00",
            duration_min=42, label="przerwa",
        ),
        TransitItem(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:20",
            duration_min=20, mode=TransitMode.CAR,
            from_location="Muzeum Historii Katowic", to_location="Park Chrobrego",
            distance_km=6.0,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="p", name="Park Chrobrego",
            description_short="", why_selected=["long_ft_fill"],
            start_time="10:09", end_time="10:40", duration_min=31,
            lat=50.26, lng=18.97, city="Katowice",
        ),
        DayEndItem(time="18:00"),
    ]
    ctx = {
        "requested_city": "Katowice", "has_car": True,
        "day_start": "09:00", "day_end": "18:00",
    }
    out = svc._finish_katowice_client_mail(items, ctx, day_num=6)
    codes = {d.code for d in audit_day(out, day=6, context=ctx)}
    assert "car_teleport" not in codes
