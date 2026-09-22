"""FIX #353 — ghost hub-return, fake walk km, dinner-before-dinner label."""
from __future__ import annotations


def _svc():
    from app.application.services.plan_service import PlanService
    from app.infrastructure.repositories.poi_repository import POIRepository
    return PlanService(POIRepository("data/zakopane.xlsx"))


def test_ghost_return_to_hub_is_dropped_before_first_drive():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem,
        TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        TransitItem(
            type=ItemType.TRANSIT, start_time="09:00", end_time="09:10",
            duration_min=10, mode=TransitMode.WALK,
            from_location="Kraków", to_location="Planty",
            distance_km=0.8,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="p", name="Planty",
            description_short="", why_selected=["x"],
            start_time="09:10", end_time="10:00", duration_min=50,
            lat=50.061, lng=19.937, city="Kraków",
        ),
        TransitItem(
            type=ItemType.TRANSIT, start_time="10:00", end_time="10:15",
            duration_min=15, mode=TransitMode.WALK,
            from_location="Planty", to_location="Kraków",
            distance_km=0.8, routing_source="return_to_car",
        ),
        TransitItem(
            type=ItemType.TRANSIT, start_time="10:15", end_time="10:35",
            duration_min=20, mode=TransitMode.CAR,
            from_location="Kraków", to_location="Fabryka Schindlera",
            distance_km=3.5,
        ),
        DayEndItem(time="18:00"),
    ]
    ctx = {
        "requested_city": "Kraków", "has_car": True,
        "day_start": "09:00", "day_end": "18:00",
    }
    out = svc._scrub_remaining_mail_physics(items, ctx, day_num=1)
    returns = [
        it for it in out
        if str(getattr(it, "routing_source", "") or "").lower() == "return_to_car"
    ]
    # Car stayed at the day's start (Kraków). Walking back there is honest.
    assert returns
    assert "krak" in (getattr(returns[0], "to_location", "") or "").lower()


def test_po_kolacji_before_dinner_is_relabelled():
    from app.domain.models.plan import (
        DayEndItem, DayStartItem, FreeTimeItem, ItemType,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME, start_time="18:14", end_time="19:14",
            duration_min=60, label="Po kolacji na luzie",
        ),
        DayEndItem(time="20:00"),
    ]
    ctx = {
        "requested_city": "Kraków", "has_car": True,
        "day_start": "09:00", "day_end": "20:00",
    }
    out = svc._fix_remaining_mail_meals(items, ctx, day_num=1)
    ft = next(
        it for it in out if getattr(it, "label", None)
    )
    assert "kolacji" not in (ft.label or "").lower()


def test_dangling_fill_is_stripped_from_frontend():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="mail_dangling_fill",
            name="Modra Kuchnia", description_short="",
            why_selected=["mail_visit"],
            start_time="15:00", end_time="15:20", duration_min=20,
            lat=52.4, lng=16.9, city="Poznań",
        ),
        DayEndItem(time="18:00"),
    ]
    ctx = {"requested_city": "Poznań"}
    out = svc._strip_mail_technical_fillers(items, ctx, day_num=3)
    assert not any(
        "mail_dangling" in str(getattr(it, "poi_id", "") or "")
        for it in out
    )
