"""FIX #232 — front plan view: preferences, description_long, pro_tip, dinner_break."""

from datetime import date

from app.application.services.plan_service import _trip_context_fields
from app.domain.models.plan import (
    AttractionItem,
    DinnerBreakItem,
    ItemType,
    ParkingInfo,
    PlanResponse,
    TicketInfo,
)
from app.domain.models.trip_input import (
    BudgetInput,
    DailyTimeWindow,
    GroupInput,
    LocationInput,
    TripInput,
    TripLengthInput,
)


def test_trip_context_includes_preferences_and_style():
    trip = TripInput(
        location=LocationInput(city="Warszawa", region_type="city"),
        group=GroupInput(type="friends", size=3),
        trip_length=TripLengthInput(days=4, start_date=date(2026, 8, 1)),
        daily_time_window=DailyTimeWindow(),
        budget=BudgetInput(level=2),
        preferences=["adventure", "active_sport"],
        travel_style="adventure",
    )
    ctx = _trip_context_fields(trip)
    assert ctx["preferences"] == ["adventure", "active_sport"]
    assert ctx["travel_style"] == "adventure"


def test_attraction_item_exposes_long_description_and_pro_tip():
    item = AttractionItem(
        poi_id="poi_1",
        name="Hydropolis",
        start_time="10:00",
        end_time="11:30",
        duration_min=90,
        description_short="Krótki opis",
        description_long="Długi opis atrakcji z bazy Excel.",
        lat=51.1,
        lng=17.0,
        address="Wrocław",
        cost_estimate=80,
        ticket_info=TicketInfo(ticket_normal=40, ticket_reduced=30),
        parking=ParkingInfo(name="Parking", walk_time_min=5),
        pro_tip="Warto zarezerwować bilety online.",
    )
    dumped = item.model_dump()
    assert dumped["description_long"] == "Długi opis atrakcji z bazy Excel."
    assert dumped["pro_tip"] == "Warto zarezerwować bilety online."


def test_plan_response_includes_dinner_break_item_type():
    dinner = DinnerBreakItem(
        start_time="18:30",
        end_time="19:30",
        duration_min=60,
        suggestions=[],
    )
    plan = PlanResponse(
        plan_id="00000000-0000-0000-0000-000000000001",
        version=1,
        preferences=["relaxation"],
        travel_style="relax",
        days=[{
            "day": 1,
            "items": [
                {"type": "day_start", "time": "09:00"},
                dinner.model_dump(),
                {"type": "day_end", "time": "19:00"},
            ],
        }],
    )
    types = [it.type.value for it in plan.days[0].items]
    assert ItemType.DINNER_BREAK.value in types
