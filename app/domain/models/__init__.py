"""
Domain models package.
Exports all Pydantic models used in the application.
"""
from .trip_input import (
    TripInput,
    LocationInput,
    GroupInput,
    TripLengthInput,
    DailyTimeWindow,
    BudgetInput,
)
from .plan import (
    DayPlan,
    AttractionItem,
    TransitItem,
    DayStartItem,
    DayEndItem,
    ParkingItem,
    LunchBreakItem,
    TicketInfo,
    ParkingInfo,
    ItemType,
    TransitMode,
    ParkingType,
)
from .poi import POI
from .restaurant import Restaurant  # ETAP 3
from .trail import Trail  # ETAP 3

__all__ = [
    # Trip Input
    "TripInput",
    "LocationInput",
    "GroupInput",
    "TripLengthInput",
    "DailyTimeWindow",
    "BudgetInput",
    # Plan Response
    "DayPlan",
    "AttractionItem",
    "TransitItem",
    "DayStartItem",
    "DayEndItem",
    "ParkingItem",
    "LunchBreakItem",
    "TicketInfo",
    "ParkingInfo",
    # Enums
    "ItemType",
    "TransitMode",
    "ParkingType",
    # POI & ETAP 3
    "POI",
    "Restaurant",  # ETAP 3: 310 restaurants across 15 cities
    "Trail",       # ETAP 3: 37 trails across 3 regions
]
