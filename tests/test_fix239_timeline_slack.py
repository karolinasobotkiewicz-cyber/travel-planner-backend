"""FIX #239 — timeline slack collapse."""
from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    DinnerBreakItem,
    ItemType,
    ParkingInfo,
    ParkingType,
    TicketInfo,
)
from app.domain.planner.time_utils import time_to_minutes


def _attr(name, start, end):
    return AttractionItem(
        type=ItemType.ATTRACTION,
        poi_id="a",
        name=name,
        start_time=start,
        end_time=end,
        duration_min=time_to_minutes(end) - time_to_minutes(start),
        description_short="t",
        lat=51.1,
        lng=17.0,
        address="a",
        city="Wrocław",
        cost_estimate=0,
        ticket_info=TicketInfo(ticket_normal=0, ticket_reduced=0),
        parking=ParkingInfo(name="P", walk_time_min=5, parking_type=ParkingType.FREE),
    )


def test_collapse_timeline_slack_before_dinner():
    svc = PlanService(poi_repository=None)
    items = [
        _attr("A", "14:00", "15:00"),
        DinnerBreakItem(
            type=ItemType.DINNER_BREAK,
            start_time="17:30",
            end_time="18:30",
            duration_min=60,
            suggestions=[],
        ),
    ]
    out = svc._collapse_excessive_timeline_slack(items, max_slack_min=25)
    dinner = out[1]
    # FIX #240: kolacja nie jest przesuwana wcześniej
    assert time_to_minutes(dinner.start_time) == time_to_minutes("17:30")
