"""FIX #366 - Kraków / Katowice UAT leftovers after #361–#365."""
from __future__ import annotations


def _svc():
    from app.application.services.plan_service import PlanService
    from app.infrastructure.repositories.poi_repository import POIRepository
    return PlanService(POIRepository("data/zakopane.xlsx"))


def test_maczuga_coords_sit_next_to_pieskowa():
    from app.domain.models.plan import AttractionItem, ItemType
    from app.infrastructure.routing.haversine import haversine_km

    svc = _svc()
    items = [
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="m", name="Maczuga Herkulesa",
            description_short="", why_selected=["x"],
            start_time="15:00", end_time="15:30", duration_min=30,
            lat=50.2444, lng=19.8047, city="Sułoszowa",
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="p", name="Zamek Pieskowa Skała",
            description_short="", why_selected=["x"],
            start_time="16:00", end_time="17:30", duration_min=90,
            lat=50.2451641, lng=19.7788312, city="Sułoszowa",
        ),
    ]
    out = svc._force_known_good_poi_coords(items, day_num=4)
    mac = next(it for it in out if "maczuga" in (it.name or "").lower())
    pies = next(it for it in out if "pieskow" in (it.name or "").lower())
    dist = haversine_km(float(mac.lat), float(mac.lng), float(pies.lat), float(pies.lng))
    assert dist < 0.4, dist


def test_short_car_hop_becomes_walk():
    from app.domain.models.plan import (
        DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="14:00", end_time="14:10",
            duration_min=10, from_location="Bazylika Mariacka",
            to_location="Brama Floriańska", mode=TransitMode.CAR,
            distance_km=0.385,
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Kraków", "has_car": True}
    out = svc._seal_fix366_uat_day(items, ctx, day_num=3)
    cars = [
        it for it in out
        if str(getattr(getattr(it, "type", None), "value", "")) == "transit"
        and "car" in str(getattr(getattr(it, "mode", None), "value", "")).lower()
    ]
    assert not cars, cars
    walks = [
        it for it in out
        if str(getattr(getattr(it, "type", None), "value", "")) == "transit"
    ]
    assert walks and "walk" in str(
        getattr(getattr(walks[0], "mode", None), "value", "")
    ).lower()


def test_short_car_and_gap_cover_still_run():
    from app.domain.models.plan import (
        DayEndItem, DayStartItem, FreeTimeItem, ItemType, TransitItem, TransitMode,
        AttractionItem,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Rynek",
            description_short="x", why_selected=["x"],
            start_time="09:30", end_time="10:30", duration_min=60,
            lat=50.06, lng=19.94, city="Kraków",
        ),
        # 70 min anonymous hole before next stop
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Wawel",
            description_short="x", why_selected=["x"],
            start_time="11:40", end_time="12:40", duration_min=60,
            lat=50.05, lng=19.93, city="Kraków",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Kraków"}
    out = svc._seal_fix366_uat_day(items, ctx, day_num=1)
    fts = [
        it for it in out
        if str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "free_time"
    ]
    assert fts, "expected gap cover free_time"


def test_post_hub_sztolnia_meal_hop_is_dropped():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, DinnerBreakItem,
        ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="k", name="Kopalnia Soli Wieliczka",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="13:00", duration_min=180,
            lat=49.9835, lng=20.0552, city="Wieliczka",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="13:10", end_time="13:40",
            duration_min=30, from_location="Kopalnia Soli Wieliczka",
            to_location="Kraków centrum", mode=TransitMode.CAR, distance_km=12.0,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Zalew Bagry",
            description_short="x", why_selected=["excel_pool"],
            start_time="16:00", end_time="16:40", duration_min=40,
            lat=50.0328, lng=19.9905, city="Kraków",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="17:24", end_time="17:33",
            duration_min=9, from_location="Zalew Bagry",
            to_location="Sztolnia Wieliczka", mode=TransitMode.WALK,
            distance_km=0.558,
        ),
        DinnerBreakItem.model_construct(
            type=ItemType.DINNER_BREAK, start_time="17:33", end_time="18:18",
            duration_min=45, label="Sztolnia Wieliczka",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Kraków", "has_car": True}
    out = svc._seal_fix366_uat_day(items, ctx, day_num=5)
    hops = [
        getattr(it, "to_location", None)
        for it in out
        if str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        == "transit"
    ]
    assert not any(h and "Sztolnia" in str(h) for h in hops), hops


def test_empty_cybermagia_preference_fill_is_dropped():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="18:00", end_time="18:20",
            duration_min=20, from_location="Spodek", to_location="Cybermagia",
            mode=TransitMode.CAR, distance_km=2.0, routing_source="pref_fill",
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="katowice_pref", name="Cybermagia",
            description_short="", why_selected=["preference_fill"],
            start_time="18:20", end_time="19:00", duration_min=40,
            lat=50.2649, lng=19.0238, city="Katowice", address="",
        ),
        DayEndItem(time="20:00"),
    ]
    ctx = {"requested_city": "Katowice"}
    out = svc._seal_fix366_uat_day(items, ctx, day_num=2)
    names = [getattr(it, "name", "") for it in out]
    assert not any("cybermag" in (n or "").lower() for n in names), names
