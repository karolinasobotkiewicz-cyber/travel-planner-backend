"""FIX #350 — Kraków remaining-city mornings, winter dusk, park runs."""
from __future__ import annotations


def _svc():
    from app.application.services.plan_service import PlanService
    from app.infrastructure.repositories.poi_repository import POIRepository
    return PlanService(POIRepository("data/zakopane.xlsx"))


def test_prompt_start_moves_later_park_to_morning():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="10:19", end_time="10:29",
            duration_min=10, from_location="Kraków",
            to_location="plac Jana Matejki", mode=TransitMode.WALK,
            distance_km=1.0,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="m", name="plac Jana Matejki",
            description_short="", why_selected=["x"],
            start_time="10:29", end_time="11:00", duration_min=31,
            lat=50.067, lng=19.943, city="Kraków",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="15:00", end_time="15:20",
            duration_min=20, from_location="plac Jana Matejki",
            to_location="Park Decjusza", mode=TransitMode.CAR,
            distance_km=4.0,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="p", name="Park Decjusza",
            description_short="", why_selected=["x"],
            start_time="15:20", end_time="16:20", duration_min=60,
            lat=50.065, lng=19.888, city="Kraków",
        ),
        DayEndItem(time="21:00"),
    ]
    ctx = {"requested_city": "Kraków", "day_start": "09:00"}
    out = svc._ensure_remaining_prompt_start(items, ctx, day_num=2)
    first_real = None
    for it in out:
        tv = str(getattr(getattr(it, "type", None), "value", getattr(it, "type", "")))
        if tv in ("day_start", "day_end"):
            continue
        first_real = it
        break
    assert getattr(first_real, "start_time") == "09:00"
    names = [getattr(it, "name", "") for it in out]
    assert names.index("Park Decjusza") < names.index("plac Jana Matejki")
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="10:19", end_time="10:29",
            duration_min=10, from_location="Kraków",
            to_location="plac Jana Matejki", mode=TransitMode.CAR,
            distance_km=2.0,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="m", name="plac Jana Matejki",
            description_short="", why_selected=["x"],
            start_time="10:29", end_time="11:00", duration_min=31,
            lat=50.067, lng=19.943, city="Kraków",
        ),
        DayEndItem(time="21:00"),
    ]
    ctx = {"requested_city": "Kraków", "day_start": "09:00", "day_end": "21:00"}
    out = svc._pull_remaining_day_to_window(items, ctx, day_num=2)
    hops = [
        it for it in out
        if str(getattr(getattr(it, "type", None), "value", "")) == "transit"
    ]
    assert hops
    assert getattr(hops[0], "start_time") == "09:00"
    wro = svc._pull_remaining_day_to_window(
        items, {**ctx, "requested_city": "Wrocław"}, day_num=2,
    )
    wro_hops = [
        it for it in wro
        if str(getattr(getattr(it, "type", None), "value", "")) == "transit"
    ]
    assert getattr(wro_hops[0], "start_time") == "10:19"


def test_february_dusk_drops_skalki():
    from datetime import date
    from app.domain.models.plan import AttractionItem, DayEndItem, DayStartItem, ItemType

    svc = _svc()
    items = [
        DayStartItem(time="09:30"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="s", name="Skałki Twardowskiego",
            description_short="", why_selected=["x"],
            start_time="17:12", end_time="18:12", duration_min=60,
            lat=50.033, lng=19.914, city="Kraków",
        ),
        DayEndItem(time="18:00"),
    ]
    ctx = {
        "requested_city": "Kraków", "date": date(2026, 2, 22),
        "day_start": "09:30", "day_end": "18:00",
    }
    out = svc._drop_remaining_dusk_outdoor(items, ctx, day_num=3)
    names = [getattr(it, "name", "") for it in out]
    assert "Skałki Twardowskiego" not in names
    wro = svc._drop_remaining_dusk_outdoor(
        items, {**ctx, "requested_city": "Wrocław"}, day_num=3,
    )
    assert any("Skałki" in (getattr(it, "name", "") or "") for it in wro)


def test_february_dusk_uses_season_when_date_missing():
    from app.domain.models.plan import AttractionItem, DayEndItem, DayStartItem, ItemType

    svc = _svc()
    items = [
        DayStartItem(time="09:30"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="k", name="Kopiec Józefa Piłsudskiego",
            description_short="", why_selected=["x"],
            start_time="16:50", end_time="17:40", duration_min=50,
            lat=50.060, lng=19.850, city="Kraków",
        ),
        DayEndItem(time="18:00"),
    ]
    ctx = {
        "requested_city": "Kraków", "season": "winter",
        "day_start": "09:30", "day_end": "18:00",
    }
    out = svc._drop_remaining_dusk_outdoor(items, ctx, day_num=4)
    names = [getattr(it, "name", "") for it in out]
    assert "Kopiec Józefa Piłsudskiego" not in names


def test_three_parks_in_a_row_drop_the_third():
    from app.domain.models.plan import AttractionItem, DayEndItem, DayStartItem, ItemType

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Park im. Wojciecha Bednarskiego",
            description_short="", why_selected=["x"],
            start_time="14:00", end_time="14:40", duration_min=40,
            lat=50.0378, lng=19.9585, city="Kraków",
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Park Lotników Polskich",
            description_short="", why_selected=["x"],
            start_time="15:00", end_time="15:40", duration_min=40,
            lat=50.081, lng=19.991, city="Kraków",
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="c", name="Planty Krakowskie",
            description_short="", why_selected=["x"],
            start_time="16:00", end_time="16:40", duration_min=40,
            lat=50.061, lng=19.937, city="Kraków",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Kraków"}
    out = svc._cap_remaining_park_run(items, ctx, day_num=3)
    names = [getattr(it, "name", "") for it in out if getattr(it, "name", None)]
    assert "Planty Krakowskie" not in names
    assert "Park im. Wojciecha Bednarskiego" in names


def test_auditor_flags_late_start_and_dusk_park():
    from datetime import date
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )
    from app.domain.validators.client_invariants import audit_day

    items = [
        DayStartItem(time="09:00"),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="10:19", end_time="10:29",
            duration_min=10, from_location="Kraków",
            to_location="plac Jana Matejki", mode=TransitMode.WALK,
            distance_km=1.0,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="s", name="Skałki Twardowskiego",
            description_short="", why_selected=["x"],
            start_time="17:12", end_time="18:12", duration_min=60,
            lat=50.033, lng=19.914, city="Kraków",
        ),
        DayEndItem(time="18:00"),
    ]
    ctx = {
        "requested_city": "Kraków", "day_start": "09:00",
        "date": date(2026, 2, 22),
    }
    codes = {d.code for d in audit_day(items, day=2, context=ctx)}
    assert "late_start" in codes
    assert "after_dark_outdoor" in codes
    wro = {d.code for d in audit_day(
        items, day=2, context={**ctx, "requested_city": "Wrocław"},
    )}
    assert "late_start" not in wro
    assert "after_dark_outdoor" not in wro
