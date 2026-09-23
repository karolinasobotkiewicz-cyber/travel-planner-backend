"""FIX #355 — last open-mail pass: honest legs, car ledger, no fillers."""
from __future__ import annotations


def _svc():
    from app.application.services.plan_service import PlanService
    from app.infrastructure.repositories.poi_repository import POIRepository
    return PlanService(POIRepository("data/zakopane.xlsx"))


def test_slow_short_drive_is_restamped_from_pins():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )
    from app.domain.planner.time_utils import time_to_minutes

    svc = _svc()
    svc._open_mail_seen = set()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Rynek",
            description_short="rynek", why_selected=["x"],
            start_time="09:00", end_time="10:00", duration_min=60,
            lat=50.259, lng=19.021, city="Katowice",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="10:00", end_time="11:30",
            duration_min=90, mode=TransitMode.CAR,
            from_location="Rynek", to_location="Spodek",
            distance_km=2.35,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="s", name="Spodek",
            description_short="hala", why_selected=["x"],
            start_time="11:30", end_time="12:30", duration_min=60,
            lat=50.266, lng=19.023, city="Katowice",
        ),
        DayEndItem(time="18:00"),
    ]
    ctx = {
        "requested_city": "Katowice", "has_car": True,
        "day_start": "09:00", "day_end": "18:00",
    }
    out = svc._seal_open_mail_day(items, ctx, day_num=2)
    hop = next(
        it for it in out
        if str(getattr(getattr(it, "type", None), "value", "")) == "transit"
        and "spodek" in (getattr(it, "to_location", "") or "").lower()
    )
    pace = int(getattr(hop, "duration_min", 0) or 0)
    assert pace < 20


def test_walk_does_not_keep_a_road_source():
    from app.domain.models.plan import (
        DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    svc._open_mail_seen = set()
    items = [
        DayStartItem(time="09:00"),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="15:00", end_time="15:12",
            duration_min=12, mode=TransitMode.WALK,
            from_location="MIŁA", to_location="Smok Wawelski",
            distance_km=0.8, routing_source="estimated_road",
        ),
        DayEndItem(time="18:00"),
    ]
    ctx = {"requested_city": "Kraków", "has_car": True, "day_end": "18:00"}
    out = svc._seal_open_mail_day(items, ctx, day_num=2)
    hop = next(
        it for it in out
        if str(getattr(getattr(it, "type", None), "value", "")) == "transit"
    )
    assert "road" not in str(getattr(hop, "routing_source", "") or "").lower()


def test_technical_filler_and_repeat_icon_stay_off_the_day():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType,
    )

    svc = _svc()
    svc._open_mail_seen = {"park kosciuszki"}
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="katowice_ft_fill",
            name="Park Kościuszki", description_short="",
            why_selected=["long_ft_fill"],
            start_time="11:00", end_time="11:40", duration_min=40,
            lat=50.25, lng=19.02, city="Katowice",
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="zoo",
            name="Śląskie ZOO", description_short="zoo",
            why_selected=["x"],
            start_time="12:00", end_time="13:00", duration_min=60,
            lat=50.28, lng=18.99, city="Katowice",
        ),
        DayEndItem(time="18:00"),
    ]
    ctx = {"requested_city": "Katowice", "has_car": True, "day_end": "18:00"}
    out = svc._seal_open_mail_day(items, ctx, day_num=2)
    names = [getattr(it, "name", "") or "" for it in out]
    assert not any("Kościuszki" in n for n in names)
    zoo = next(it for it in out if "ZOO" in (getattr(it, "name", "") or ""))
    assert getattr(zoo, "city", "") == "Chorzów"


def test_early_dinner_moves_to_the_evening_floor():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, DinnerBreakItem, ItemType,
        LunchBreakItem,
    )
    from app.domain.planner.time_utils import time_to_minutes

    svc = _svc()
    svc._open_mail_seen = set()
    items = [
        DayStartItem(time="09:00"),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK, start_time="13:00", end_time="13:26",
            duration_min=26, suggestions=[],
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="p", name="Planty",
            description_short="park", why_selected=["x"],
            start_time="14:00", end_time="14:40", duration_min=40,
            lat=50.06, lng=19.94, city="Kraków",
        ),
        DinnerBreakItem.model_construct(
            type=ItemType.DINNER_BREAK, start_time="16:01", end_time="16:45",
            duration_min=44, suggestions=[], label="Kolacja",
        ),
        DayEndItem(time="20:00"),
    ]
    ctx = {
        "requested_city": "Kraków", "has_car": True,
        "day_start": "09:00", "day_end": "20:00",
    }
    out = svc._seal_open_mail_day(items, ctx, day_num=1)
    dinner = next(
        it for it in out
        if str(getattr(getattr(it, "type", None), "value", "")) == "dinner_break"
    )
    lunch = next(
        it for it in out
        if str(getattr(getattr(it, "type", None), "value", "")) == "lunch_break"
    )
    assert time_to_minutes(dinner.start_time) >= 17 * 60 + 30
    assert time_to_minutes(lunch.end_time) - time_to_minutes(lunch.start_time) >= 35
