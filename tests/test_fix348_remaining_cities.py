"""FIX #348 — arrive-before-visit, phantom 0.5 km lead, A→A, missing hops."""
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


def test_arrive_before_visit_shifts_obwarzanek():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="10:31", end_time="10:41",
            duration_min=10, from_location="Kraków",
            to_location="Muzeum Obwarzanka", mode=TransitMode.WALK,
            distance_km=0.8,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="o", name="Muzeum Obwarzanka",
            description_short="", why_selected=["x"],
            start_time="10:31", end_time="11:10", duration_min=39,
            lat=50.064, lng=19.941, city="Kraków",
        ),
        DayEndItem(time="18:00"),
    ]
    out = svc._arrive_before_visit(
        items, {"requested_city": "Kraków"}, day_num=1,
    )
    visit = next(it for it in out if getattr(it, "name", "") == "Muzeum Obwarzanka")
    assert getattr(visit, "start_time") >= "10:41"
    wro = svc._arrive_before_visit(
        items, {"requested_city": "Wrocław"}, day_num=1,
    )
    wro_v = next(it for it in wro if getattr(it, "name", "") == "Muzeum Obwarzanka")
    assert getattr(wro_v, "start_time") == "10:31"


def test_phantom_leading_walk_to_zoo_is_rewritten():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="09:00", end_time="09:09",
            duration_min=9, from_location="Kraków",
            to_location="Ogród Zoologiczny w Krakowie",
            mode=TransitMode.WALK, distance_km=0.5,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="z",
            name="Ogród Zoologiczny w Krakowie",
            description_short="", why_selected=["x"],
            start_time="09:09", end_time="11:00", duration_min=111,
            lat=50.0647, lng=19.9450, city="Kraków",
        ),
        DayEndItem(time="18:00"),
    ]
    ctx = {
        "requested_city": "Kraków", "has_car": True,
        "day_start": "09:00", "day_end": "18:00",
    }
    out = svc._rewrite_phantom_leading_hop(items, {}, ctx, day_num=2)
    hops = _transits(out)
    assert hops
    km = float(getattr(hops[0], "distance_km", 0) or 0)
    assert km > 2.5
    mode = str(getattr(getattr(hops[0], "mode", None), "value", hops[0].mode)).lower()
    assert "car" in mode


def test_self_hop_is_dropped_and_missing_leg_inserted():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:30"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="p",
            name="Park Lotników Polskich",
            description_short="", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=50.0778, lng=19.9917, city="Kraków",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:10",
            duration_min=10, from_location="Park Lotników Polskich",
            to_location="Park Lotników Polskich",
            mode=TransitMode.CAR, distance_km=7.2,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Błonia",
            description_short="", why_selected=["x"],
            start_time="11:10", end_time="12:00", duration_min=50,
            lat=50.0600, lng=19.9160, city="Kraków",
        ),
        DayEndItem(time="18:00"),
    ]
    ctx = {
        "requested_city": "Kraków", "has_car": True,
        "day_start": "09:30", "day_end": "18:00",
    }
    cm = {
        "Park Lotników Polskich": {"lat": 50.0778, "lng": 19.9917},
        "Błonia": {"lat": 50.0600, "lng": 19.9160},
    }
    out = svc._seal_remaining_city_transport(items, ctx, day_num=3, coord_map=cm)
    hops = _transits(out)
    assert hops
    assert not any(
        "lotników" in (getattr(h, "from_location", "") or "").lower()
        and "lotników" in (getattr(h, "to_location", "") or "").lower()
        for h in hops
    )
    assert any(
        "błonia" in (getattr(h, "to_location", "") or "").lower()
        or "blonia" in (getattr(h, "to_location", "") or "").lower()
        for h in hops
    )


def test_auditor_flags_phantom_lead_and_self_hop():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )
    from app.domain.validators.client_invariants import audit_day

    hop = TransitItem.model_construct(
        type=ItemType.TRANSIT, start_time="09:00", end_time="09:09",
        duration_min=9, from_location="Kraków",
        to_location="Ogród Zoologiczny w Krakowie",
        mode=TransitMode.WALK, distance_km=0.5,
    )
    zoo = AttractionItem.model_construct(
        type=ItemType.ATTRACTION, poi_id="z",
        name="Ogród Zoologiczny w Krakowie",
        description_short="", why_selected=["x"],
        start_time="09:09", end_time="11:00", duration_min=111,
        lat=50.0547, lng=19.8486, city="Kraków",
    )
    self_h = TransitItem.model_construct(
        type=ItemType.TRANSIT, start_time="11:00", end_time="11:10",
        duration_min=10, from_location="Ogród Zoologiczny w Krakowie",
        to_location="Ogród Zoologiczny w Krakowie",
        mode=TransitMode.CAR, distance_km=3.28,
    )
    items = [
        DayStartItem(time="09:00"), hop, zoo, self_h, DayEndItem(time="18:00"),
    ]
    ctx = {"requested_city": "Kraków", "day_start": "09:00", "day_end": "18:00"}
    codes = {d.code for d in audit_day(items, day=1, context=ctx)}
    assert "phantom_lead" in codes
    assert "self_hop" in codes
    wro_codes = {
        d.code for d in audit_day(
            items, day=1,
            context={**ctx, "requested_city": "Wrocław"},
        )
    }
    assert "phantom_lead" not in wro_codes
    assert "self_hop" not in wro_codes


def test_kopiec_with_real_gps_drops_half_km_lead():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="09:00", end_time="09:09",
            duration_min=9, from_location="Kraków",
            to_location="Kopiec Józefa Piłsudskiego",
            mode=TransitMode.WALK, distance_km=0.5,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="k",
            name="Kopiec Józefa Piłsudskiego",
            description_short="", why_selected=["x"],
            start_time="09:09", end_time="10:30", duration_min=81,
            lat=50.0606, lng=19.8372, city="Kraków",
        ),
        DayEndItem(time="18:00"),
    ]
    ctx = {
        "requested_city": "Kraków", "has_car": True,
        "day_start": "09:00", "day_end": "18:00",
    }
    out = svc._rewrite_phantom_leading_hop(items, {}, ctx, day_num=1)
    hops = _transits(out)
    assert hops
    km = float(getattr(hops[0], "distance_km", 0) or 0)
    assert km > 2.5


def test_overlapping_hops_are_sequenced():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Planty",
            description_short="", why_selected=["x"],
            start_time="16:00", end_time="17:00", duration_min=60,
            lat=50.061, lng=19.937, city="Kraków",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="17:20", end_time="17:44",
            duration_min=24, from_location="Planty",
            to_location="Wawel", mode=TransitMode.WALK, distance_km=1.6,
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="17:28", end_time="17:44",
            duration_min=16, from_location="Wawel",
            to_location="Kazimierz", mode=TransitMode.WALK, distance_km=1.1,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Kazimierz",
            description_short="", why_selected=["x"],
            start_time="17:44", end_time="18:20", duration_min=36,
            lat=50.049, lng=19.945, city="Kraków",
        ),
        DayEndItem(time="20:00"),
    ]
    out = svc._sequence_remaining_clock(
        items, {"requested_city": "Kraków"}, day_num=1,
    )
    hops = _transits(out)
    assert hops[0].end_time <= hops[1].start_time
    wro = svc._sequence_remaining_clock(
        items, {"requested_city": "Wrocław"}, day_num=1,
    )
    wro_hops = _transits(wro)
    assert wro_hops[1].start_time == "17:28"
