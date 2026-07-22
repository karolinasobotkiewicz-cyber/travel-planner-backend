"""FIX #237 — planner logic regression (timeline, transit, meals)."""
from __future__ import annotations

from app.application.services.plan_day_integrity import (
    drop_negative_duration_items,
    ensure_meal_suggestions,
    fix_transit_meal_overlaps,
)
from app.domain.models.plan import (
    AttractionItem,
    ItemType,
    LunchBreakItem,
    ParkingInfo,
    ParkingType,
    TicketInfo,
    TransitItem,
    TransitMode,
)
from app.domain.planner.time_utils import time_to_minutes


def _attr(name: str, start: str, end: str) -> AttractionItem:
    return AttractionItem(
        type=ItemType.ATTRACTION,
        poi_id=f"p_{name}",
        name=name,
        start_time=start,
        end_time=end,
        duration_min=time_to_minutes(end) - time_to_minutes(start),
        description_short="t",
        lat=51.11,
        lng=17.04,
        address="a",
        city="Wrocław",
        cost_estimate=0,
        ticket_info=TicketInfo(ticket_normal=0, ticket_reduced=0),
        parking=ParkingInfo(name="P", walk_time_min=5, parking_type=ParkingType.FREE),
    )


def test_drop_negative_duration():
    class _Bad:
        start_time = "13:00"
        end_time = "12:00"

    out = drop_negative_duration_items([_Bad()], 1)
    assert out == []


def test_fix_transit_meal_overlap_shifts_transit():
    items = [
        _attr("A", "10:00", "11:00"),
        TransitItem(
            type=ItemType.TRANSIT,
            from_location="A",
            to_location="B",
            start_time="11:00",
            end_time="12:30",
            duration_min=90,
            mode=TransitMode.CAR,
        ),
        LunchBreakItem(
            type=ItemType.LUNCH_BREAK,
            start_time="12:00",
            end_time="13:00",
            duration_min=60,
            suggestions=[],
        ),
        _attr("B", "13:00", "14:00"),
    ]
    fixed = fix_transit_meal_overlaps(items, 1)
    tr = next(it for it in fixed if it.type == ItemType.TRANSIT)
    lunch = next(it for it in fixed if it.type == ItemType.LUNCH_BREAK)
    assert time_to_minutes(tr.end_time) <= time_to_minutes(lunch.start_time)


def test_ensure_meal_suggestions_fills_from_nearby():
    items = [
        _attr("Rynek", "10:00", "11:00"),
        LunchBreakItem(
            type=ItemType.LUNCH_BREAK,
            start_time="12:00",
            end_time="13:00",
            duration_min=60,
            suggestions=[],
        ),
    ]
    coords = {"Rynek": {"name": "Rynek", "lat": 51.11, "lng": 17.04}}
    restaurants = [
        {
            "id": "r1",
            "name": "Restauracja Test",
            "lat": 51.1105,
            "lng": 17.0405,
            "city": "Wrocław",
            "meal_type": "lunch",
        }
    ]
    ctx = {"restaurants_available": restaurants}

    def _parse(r, meal):
        from app.application.services.plan_service import _restaurant_dict_to_suggestion

        return _restaurant_dict_to_suggestion(r, meal)

    from app.application.services.plan_service import _filter_meal_suggestions

    out = ensure_meal_suggestions(
        items, coords, ctx, parse_suggestion_fn=_parse, filter_fn=_filter_meal_suggestions
    )
    lunch = out[1]
    assert len(lunch.suggestions) >= 1
    assert lunch.suggestions[0].name == "Restauracja Test"
