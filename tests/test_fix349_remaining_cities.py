"""FIX #349 — car token: walk/meal does not teleport the car."""
from __future__ import annotations


def _svc():
    from app.application.services.plan_service import PlanService
    from app.infrastructure.repositories.poi_repository import POIRepository
    return PlanService(POIRepository("data/zakopane.xlsx"))


def _transits(items):
    out = []
    for it in items:
        tv = str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        if tv == "transit":
            out.append(it)
    return out


def _mode(it) -> str:
    return str(getattr(getattr(it, "mode", None), "value", getattr(it, "mode", "")) or "").lower()


def test_walk_to_museum_then_car_inserts_return_to_hub():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="09:00", end_time="09:20",
            duration_min=20, from_location="Kraków",
            to_location="Muzeum Obwarzanka", mode=TransitMode.WALK,
            distance_km=1.4,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="o", name="Muzeum Obwarzanka",
            description_short="", why_selected=["x"],
            start_time="09:20", end_time="10:20", duration_min=60,
            lat=50.0616, lng=19.9373, city="Kraków",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="10:20", end_time="10:45",
            duration_min=25, from_location="Muzeum Obwarzanka",
            to_location="Fabryka Schindlera", mode=TransitMode.CAR,
            distance_km=3.2,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="s", name="Fabryka Schindlera",
            description_short="", why_selected=["x"],
            start_time="10:45", end_time="12:00", duration_min=75,
            lat=50.0474, lng=19.9617, city="Kraków",
        ),
        DayEndItem(time="18:00"),
    ]
    ctx = {"requested_city": "Kraków", "has_car": True, "day_start": "09:00", "day_end": "18:00"}
    cm = {
        "Kraków": {"lat": 50.0647, "lng": 19.9450},
        "Muzeum Obwarzanka": {"lat": 50.0616, "lng": 19.9373},
        "Fabryka Schindlera": {"lat": 50.0474, "lng": 19.9617},
    }
    out = svc._seal_remaining_car_token(items, cm, ctx, day_num=3)
    hops = _transits(out)
    cars = [h for h in hops if "car" in _mode(h)]
    assert cars
    assert "obwarzan" not in (getattr(cars[0], "from_location", "") or "").lower()
    returns = [
        h for h in hops
        if "return_to_car" in str(getattr(h, "routing_source", "") or "").lower()
    ]
    assert returns
    wro = svc._seal_remaining_car_token(items, cm, {**ctx, "requested_city": "Wrocław"}, day_num=3)
    wro_cars = [h for h in _transits(wro) if "car" in _mode(h)]
    assert "obwarzan" in (getattr(wro_cars[0], "from_location", "") or "").lower()


def test_lunch_then_car_from_previous_attraction_gets_return_walk():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, LunchBreakItem,
        TransitItem, TransitMode,
    )

    svc = _svc()
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK, start_time="12:30", end_time="13:20",
        duration_min=50, label="Olio",
        suggestions=[{"name": "Olio", "lat": 50.0490, "lng": 19.9440}],
    )
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Bulwary Wiślane",
            description_short="", why_selected=["x"],
            start_time="11:00", end_time="12:20", duration_min=80,
            lat=50.0520, lng=19.9566, city="Kraków",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="12:20", end_time="12:30",
            duration_min=10, from_location="Bulwary Wiślane",
            to_location="Olio", mode=TransitMode.WALK, distance_km=0.7,
        ),
        lunch,
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="13:20", end_time="13:45",
            duration_min=25, from_location="Bulwary Wiślane",
            to_location="Wawel", mode=TransitMode.CAR, distance_km=2.1,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="w", name="Wawel",
            description_short="", why_selected=["x"],
            start_time="13:45", end_time="15:00", duration_min=75,
            lat=50.0540, lng=19.9350, city="Kraków",
        ),
        DayEndItem(time="18:00"),
    ]
    ctx = {"requested_city": "Kraków", "has_car": True}
    cm = {
        "Bulwary Wiślane": {"lat": 50.0520, "lng": 19.9566},
        "Olio": {"lat": 50.0490, "lng": 19.9440},
        "Wawel": {"lat": 50.0540, "lng": 19.9350},
        "Kraków": {"lat": 50.0647, "lng": 19.9450},
    }
    # Drive to Bulwary first so the token is the river, not the hub.
    items.insert(1, TransitItem.model_construct(
        type=ItemType.TRANSIT, start_time="10:40", end_time="11:00",
        duration_min=20, from_location="Kraków",
        to_location="Bulwary Wiślane", mode=TransitMode.CAR, distance_km=2.0,
    ))
    out = svc._seal_remaining_car_token(items, cm, ctx, day_num=1)
    hops = _transits(out)
    assert any(
        "olio" in (getattr(h, "from_location", "") or "").lower()
        and "bulwar" in (getattr(h, "to_location", "") or "").lower()
        for h in hops
        if "walk" in _mode(h)
    )
    after_lunch_cars = [
        h for h in hops
        if "car" in _mode(h)
        and "wawel" in (getattr(h, "to_location", "") or "").lower()
    ]
    assert after_lunch_cars
    assert "bulwar" in (getattr(after_lunch_cars[0], "from_location", "") or "").lower()


def test_rewrite_hop_origins_does_not_restamp_car_in_krakow():
    from app.domain.models.plan import ItemType, TransitItem, TransitMode

    svc = _svc()
    items = [
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="13:20", end_time="13:45",
            duration_min=25, from_location="Bulwary Wiślane",
            to_location="Wawel", mode=TransitMode.CAR, distance_km=2.1,
        ),
    ]
    from app.domain.models.plan import AttractionItem
    items = [
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="o", name="Olio",
            description_short="", why_selected=["x"],
            start_time="12:30", end_time="13:20", duration_min=50,
            lat=50.049, lng=19.944, city="Kraków",
        ),
        items[0],
    ]
    out = svc._rewrite_hop_origins(
        items, day_num=1, context={"requested_city": "Kraków"},
    )
    car = _transits(out)[0]
    assert "bulwar" in (getattr(car, "from_location", "") or "").lower()
    wro = svc._rewrite_hop_origins(
        items, day_num=1, context={"requested_city": "Wrocław"},
    )
    wro_car = _transits(wro)[0]
    assert "olio" in (getattr(wro_car, "from_location", "") or "").lower()


def test_auditor_flags_car_teleport():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )
    from app.domain.validators.client_invariants import audit_day

    items = [
        DayStartItem(time="09:00"),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="09:00", end_time="09:20",
            duration_min=20, from_location="Kraków",
            to_location="Park Bednarskiego", mode=TransitMode.CAR,
            distance_km=3.2,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="p", name="Park Bednarskiego",
            description_short="", why_selected=["x"],
            start_time="09:20", end_time="11:00", duration_min=100,
            lat=50.0378, lng=19.9585, city="Kraków",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:15",
            duration_min=15, from_location="Park Bednarskiego",
            to_location="Sioux", mode=TransitMode.WALK, distance_km=0.6,
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="12:00", end_time="12:20",
            duration_min=20, from_location="Sioux",
            to_location="Wawel", mode=TransitMode.CAR, distance_km=4.0,
        ),
        DayEndItem(time="18:00"),
    ]
    ctx = {"requested_city": "Kraków"}
    codes = {d.code for d in audit_day(items, day=1, context=ctx)}
    assert "car_teleport" in codes
    wro = {d.code for d in audit_day(items, day=1, context={**ctx, "requested_city": "Wrocław"})}
    assert "car_teleport" not in wro


def test_return_walk_stays_glued_when_next_stop_shares_car_start():
    """J2/J6: sorting by the old clock slid Podziemia between return and car."""
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="16:00"),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="16:00", end_time="16:10",
            duration_min=10, from_location="Kraków",
            to_location="Plac Bohaterów Getta", mode=TransitMode.CAR,
            distance_km=3.0,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="g", name="Plac Bohaterów Getta",
            description_short="", why_selected=["x"],
            start_time="16:10", end_time="16:40", duration_min=30,
            lat=50.0456, lng=19.9550, city="Kraków",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="16:40", end_time="17:00",
            duration_min=20, from_location="Plac Bohaterów Getta",
            to_location="Podziemia Rynku w Krakowie", mode=TransitMode.WALK,
            distance_km=2.1,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="p", name="Podziemia Rynku w Krakowie",
            description_short="", why_selected=["x"],
            start_time="17:50", end_time="18:25", duration_min=35,
            lat=50.0617, lng=19.9373, city="Kraków",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="17:50", end_time="18:06",
            duration_min=16, from_location="Plac Bohaterów Getta",
            to_location="Podziemia Rynku w Krakowie", mode=TransitMode.CAR,
            distance_km=2.1,
        ),
        DayEndItem(time="20:00"),
    ]
    ctx = {"requested_city": "Kraków", "has_car": True}
    cm = {
        "Kraków": {"lat": 50.0647, "lng": 19.9450},
        "Plac Bohaterów Getta": {"lat": 50.0456, "lng": 19.9550},
        "Podziemia Rynku w Krakowie": {"lat": 50.0617, "lng": 19.9373},
    }
    out = svc._seal_remaining_car_token(items, cm, ctx, day_num=3)
    hops = _transits(out)
    cars = [
        h for h in hops
        if "car" in _mode(h)
        and "podziem" in (getattr(h, "to_location", "") or "").lower()
    ]
    assert cars
    car = cars[-1]
    names = [
        (getattr(it, "name", None) or getattr(it, "to_location", None) or "")
        for it in out
        if str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        in ("transit", "attraction")
    ]
    car_idx = next(
        i for i, it in enumerate(out)
        if it is car or (
            str(getattr(getattr(it, "type", None), "value", "")) == "transit"
            and "car" in _mode(it)
            and "podziem" in (getattr(it, "to_location", "") or "").lower()
        )
    )
    attr_idx = next(
        i for i, it in enumerate(out)
        if "podziem" in (getattr(it, "name", "") or "").lower()
    )
    assert car_idx < attr_idx
    prev = out[car_idx - 1]
    assert "walk" in _mode(prev) or "foot" in _mode(prev)
    assert "getta" in (getattr(prev, "to_location", "") or "").lower()


def test_short_lunch_walk_still_inserts_return_to_car():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, LunchBreakItem,
        TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="10:00"),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:25", end_time="11:45",
            duration_min=20, from_location="Kraków",
            to_location="Planty Krakowskie", mode=TransitMode.CAR,
            distance_km=2.0,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="p", name="Planty Krakowskie",
            description_short="", why_selected=["x"],
            start_time="11:45", end_time="12:48", duration_min=63,
            lat=50.0614, lng=19.9373, city="Kraków",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="13:03", end_time="13:08",
            duration_min=5, from_location="Planty Krakowskie",
            to_location="Sorrento Trattoria", mode=TransitMode.WALK,
            distance_km=0.18,
        ),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK, start_time="13:08", end_time="13:48",
            duration_min=40, label="Sorrento Trattoria",
            suggestions=[{"name": "Sorrento Trattoria", "lat": 50.0610, "lng": 19.9360}],
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="13:53", end_time="14:03",
            duration_min=10, from_location="Planty Krakowskie",
            to_location="Bulwary Wiślane", mode=TransitMode.CAR,
            distance_km=1.4,
        ),
        DayEndItem(time="18:00"),
    ]
    ctx = {"requested_city": "Kraków", "has_car": True}
    cm = {
        "Kraków": {"lat": 50.0647, "lng": 19.9450},
        "Planty Krakowskie": {"lat": 50.0614, "lng": 19.9373},
        "Sorrento Trattoria": {"lat": 50.0610, "lng": 19.9360},
        "Bulwary Wiślane": {"lat": 50.0520, "lng": 19.9566},
    }
    out = svc._seal_remaining_car_token(items, cm, ctx, day_num=1)
    hops = _transits(out)
    assert any(
        "sorrento" in (getattr(h, "from_location", "") or "").lower()
        and "planty" in (getattr(h, "to_location", "") or "").lower()
        for h in hops
        if "walk" in _mode(h)
    )


def test_self_hop_car_is_dropped():
    from app.domain.models.plan import (
        DayEndItem, DayStartItem, ItemType, LunchBreakItem, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="18:00"),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="18:54", end_time="19:12",
            duration_min=18, from_location="Las Wolski",
            to_location="MIŁA bar mleczny 7", mode=TransitMode.CAR,
            distance_km=6.0,
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="19:12", end_time="19:47",
            duration_min=35, from_location="MIŁA bar mleczny 7",
            to_location="MIŁA bar mleczny 7", mode=TransitMode.CAR,
            distance_km=5.54,
        ),
        LunchBreakItem.model_construct(
            type=ItemType.DINNER_BREAK, start_time="19:47", end_time="20:32",
            duration_min=45, label="MIŁA bar mleczny 7",
            suggestions=[{"name": "MIŁA bar mleczny 7", "lat": 50.061, "lng": 19.937}],
        ),
        DayEndItem(time="21:00"),
    ]
    ctx = {"requested_city": "Kraków", "has_car": True}
    cm = {
        "Las Wolski": {"lat": 50.060, "lng": 19.866},
        "MIŁA bar mleczny 7": {"lat": 50.061, "lng": 19.937},
        "Kraków": {"lat": 50.0647, "lng": 19.9450},
    }
    out = svc._seal_remaining_car_token(items, cm, ctx, day_num=1)
    cars = [h for h in _transits(out) if "car" in _mode(h)]
    assert cars
    assert not any(
        "miła" in (getattr(h, "from_location", "") or "").lower()
        and "miła" in (getattr(h, "to_location", "") or "").lower()
        for h in cars
    )
