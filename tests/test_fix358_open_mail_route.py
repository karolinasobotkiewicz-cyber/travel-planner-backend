"""FIX #358 — a hop ends in a visit, and the car leaves from its parking spot."""
from __future__ import annotations


def _svc():
    from app.application.services.plan_service import PlanService
    from app.infrastructure.repositories.poi_repository import POIRepository
    return PlanService(POIRepository("data/zakopane.xlsx"))


def _ctx():
    return {
        "requested_city": "Katowice",
        "has_car": True,
        "day_start": "09:00",
        "day_end": "20:00",
    }


def _kind(it) -> str:
    return str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")) or "")


def test_waypoint_without_a_visit_is_spliced_out():
    from app.domain.models.plan import (
        AttractionItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    svc._open_mail_seen = set()
    items = [
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Guido",
            description_short="g", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=50.297, lng=18.791, city="Zabrze",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:20",
            duration_min=20, mode=TransitMode.CAR,
            from_location="Guido", to_location="Park Kościuszki",
            distance_km=8.0, routing_source="haversine",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:20", end_time="11:40",
            duration_min=20, mode=TransitMode.CAR,
            from_location="Park Kościuszki", to_location="Bar Gucio",
            distance_km=2.0, routing_source="haversine",
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Bar Gucio",
            description_short="b", why_selected=["x"],
            start_time="11:40", end_time="12:20", duration_min=40,
            lat=50.26, lng=19.02, city="Katowice",
        ),
    ]
    out = svc._own_open_mail_route(items, _ctx(), day_num=1, coord_map={
        "Guido": {"lat": 50.297, "lng": 18.791},
        "Park Kościuszki": {"lat": 50.25, "lng": 19.00},
        "Bar Gucio": {"lat": 50.26, "lng": 19.02},
    })
    dests = [
        (getattr(it, "to_location", "") or "")
        for it in out if _kind(it) == "transit"
    ]
    assert not any("kościuszki" in d.lower() or "kosciuszki" in d.lower() for d in dests)
    assert any("gucio" in d.lower() for d in dests)


def test_visit_sits_on_the_hop_that_arrived():
    from app.domain.models.plan import (
        AttractionItem, FreeTimeItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    svc._open_mail_seen = set()
    items = [
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="10:00", end_time="10:20",
            duration_min=20, mode=TransitMode.CAR,
            from_location="Kraków", to_location="Barbakan",
            distance_km=3.0, routing_source="haversine",
        ),
        FreeTimeItem(
            start_time="10:20", end_time="11:00", duration_min=40,
            label="Czas dla siebie",
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Barbakan",
            description_short="b", why_selected=["x"],
            start_time="12:40", end_time="13:20", duration_min=40,
            lat=50.065, lng=19.941, city="Kraków",
        ),
    ]
    ctx = dict(_ctx(), requested_city="Kraków")
    out = svc._own_open_mail_route(items, ctx, day_num=1, coord_map={
        "Barbakan": {"lat": 50.065, "lng": 19.941},
        "Kraków": {"lat": 50.06, "lng": 19.94},
    })
    names = []
    for it in out:
        if _kind(it) == "transit":
            names.append("hop:" + (getattr(it, "to_location", "") or ""))
        elif _kind(it) == "attraction":
            names.append("visit:" + (getattr(it, "name", "") or ""))
    hop_at = next(i for i, n in enumerate(names) if "barbakan" in n.lower() and n.startswith("hop:"))
    assert names[hop_at + 1].lower().startswith("visit:barbakan")


def test_car_does_not_restart_from_the_city_hub():
    from app.domain.models.plan import (
        AttractionItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    svc._open_mail_seen = set()
    items = [
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="10:00", end_time="10:15",
            duration_min=15, mode=TransitMode.CAR,
            from_location="Katowice", to_location="Spodek",
            distance_km=2.0, routing_source="haversine",
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="s", name="Spodek",
            description_short="s", why_selected=["x"],
            start_time="10:15", end_time="11:00", duration_min=45,
            lat=50.266, lng=19.023, city="Katowice",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:12",
            duration_min=12, mode=TransitMode.WALK,
            from_location="Spodek", to_location="Rynek",
            distance_km=0.6, routing_source="haversine",
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="r", name="Rynek",
            description_short="r", why_selected=["x"],
            start_time="11:12", end_time="12:00", duration_min=48,
            lat=50.259, lng=19.021, city="Katowice",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="12:10", end_time="12:30",
            duration_min=20, mode=TransitMode.CAR,
            from_location="Katowice", to_location="Guido",
            distance_km=20.0, routing_source="estimated_walk",
        ),
    ]
    out = svc._own_open_mail_route(items, _ctx(), day_num=2, coord_map={
        "Spodek": {"lat": 50.266, "lng": 19.023},
        "Rynek": {"lat": 50.259, "lng": 19.021},
        "Katowice": {"lat": 50.264, "lng": 19.023},
        "Guido": {"lat": 50.297, "lng": 18.791},
    })
    cars = [
        it for it in out
        if _kind(it) == "transit" and "car" in str(getattr(it, "mode", "")).lower()
    ]
    last = cars[-1]
    origin = (getattr(last, "from_location", "") or "").lower()
    assert "katowice" not in origin
    assert "walk" not in str(getattr(last, "routing_source", "") or "").lower()


def test_zero_km_self_hop_is_dropped():
    from app.domain.models.plan import ItemType, TransitItem, TransitMode

    svc = _svc()
    svc._open_mail_seen = set()
    items = [
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="12:00", end_time="12:05",
            duration_min=5, mode=TransitMode.CAR,
            from_location="Bar Gucio", to_location="Bar Gucio",
            distance_km=0.0, routing_source="haversine",
        ),
    ]
    out = svc._own_open_mail_route(items, _ctx(), day_num=1)
    assert not any(_kind(it) == "transit" for it in out)
