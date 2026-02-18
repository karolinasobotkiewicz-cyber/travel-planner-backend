"""
Pydantic models dla plan response.
Zgodne z UWAGI_API_CONTRACT_v2.md (wyjaśnienia od klientki 25.01.2026).
"""
from pydantic import BaseModel, Field
from typing import List, Union, Literal
from enum import Enum


# =========================
# ENUMS
# =========================


class ItemType(str, Enum):
    """Typy elementów w planie dnia."""

    DAY_START = "day_start"
    PARKING = "parking"
    TRANSIT = "transit"
    ATTRACTION = "attraction"
    LUNCH_BREAK = "lunch_break"
    DINNER_BREAK = "dinner_break"
    FREE_TIME = "free_time"
    DAY_END = "day_end"


class TransitMode(str, Enum):
    """Tryby transportu."""

    WALK = "walk"
    CAR = "car"
    PUBLIC_TRANSPORT = "public_transport"


class ParkingType(str, Enum):
    """Typy parkingu."""

    PAID = "paid"
    FREE = "free"


# =========================
# NESTED OBJECTS
# =========================


class ParkingInfo(BaseModel):
    """
    Parking info zagnieżdżony w attraction.
    Każda atrakcja ma własny parking object (powtarzający się celowo).
    """

    name: str = Field(..., description="Nazwa parkingu")
    walk_time_min: int = Field(
        ..., ge=0, description="Czas spaceru do atrakcji w minutach"
    )


class TicketInfo(BaseModel):
    """Informacje o cenach biletów."""

    ticket_normal: int = Field(..., ge=0, description="Cena biletu normalnego")
    ticket_reduced: int = Field(..., ge=0, description="Cena biletu ulgowego")


# =========================
# PLAN ITEMS (7 typów)
# =========================


class DayStartItem(BaseModel):
    """
    Marker początku dnia (nie aktywność).
    Ma tylko `time`, nie start_time/end_time.
    """

    type: Literal[ItemType.DAY_START] = ItemType.DAY_START
    time: str = Field(
        ...,
        pattern=r"^([01]\d|2[0-3]):([0-5]\d)$",
        description="Godzina startu dnia HH:MM",
    )


class DayEndItem(BaseModel):
    """
    Marker końca dnia (nie aktywność).
    Ma tylko `time`, nie start_time/end_time.
    """

    type: Literal[ItemType.DAY_END] = ItemType.DAY_END
    time: str = Field(
        ...,
        pattern=r"^([01]\d|2[0-3]):([0-5]\d)$",
        description="Godzina końca dnia HH:MM",
    )


class ParkingItem(BaseModel):
    """Parking na początku dnia (jeśli transport_modes=car)."""

    type: Literal[ItemType.PARKING] = ItemType.PARKING
    start_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$")
    end_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$")
    name: str = Field(..., description="Nazwa parkingu")
    address: str = Field(..., description="Adres parkingu")
    lat: float = Field(..., description="Szerokość geograficzna")
    lng: float = Field(..., description="Długość geograficzna")
    parking_type: ParkingType = Field(..., description="Typ: paid/free")
    walk_time_min: int = Field(
        ..., ge=0, description="Czas spaceru DO pierwszej atrakcji"
    )


class TransitItem(BaseModel):
    """Przejazd/spacer między lokalizacjami."""

    type: Literal[ItemType.TRANSIT] = ItemType.TRANSIT
    start_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$")
    end_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$")
    duration_min: int = Field(..., ge=0, description="Czas przejazdu")
    mode: TransitMode = Field(..., description="walk/car/public_transport")
    from_location: str = Field(..., alias="from", description="Skąd")
    to_location: str = Field(..., alias="to", description="Dokąd")

    class Config:
        populate_by_name = True


class AttractionItem(BaseModel):
    """
    Atrakcja z pełnymi danymi POI.
    Frontend NIE fetchuje danych po poi_id - plan to kompletny snapshot.
    """

    type: Literal[ItemType.ATTRACTION] = ItemType.ATTRACTION
    poi_id: str = Field(..., description="ID z bazy POI")
    name: str = Field(..., description="Nazwa atrakcji")
    start_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$")
    end_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$")
    duration_min: int = Field(..., ge=0, description="Czas wizyty")

    # POI dane - MUSZĄ być w response (klientka 25.01)
    description_short: str = Field(..., description="Krótki opis")
    lat: float = Field(..., description="Szerokość geograficzna")
    lng: float = Field(..., description="Długość geograficzna")
    address: str = Field(..., description="Adres atrakcji")

    cost_estimate: int = Field(
        ..., ge=0, description="Oszacowany koszt dla grupy"
    )
    ticket_info: TicketInfo = Field(..., description="Info o cenach")
    parking: ParkingInfo = Field(
        ..., description="Parking (powtarza się dla każdej atrakcji)"
    )
    pro_tip: str | None = Field(
        default=None, description="Pro tip z bazy POI (jeśli dostępne)"
    )

    # ETAP 2 Day 5: Quality + Explainability
    why_selected: List[str] = Field(
        default_factory=list,
        description="Top 3 reasons why this POI was selected (natural language)",
    )
    quality_badges: List[str] = Field(
        default_factory=list,
        description="Quality badges (must_see, perfect_timing, weather_resistant, etc.)",
    )


class LunchBreakItem(BaseModel):
    """
    Przerwa na lunch - ZAWSZE 12:00-13:30.
    Backend generuje suggestions (ETAP 1: generyczne).
    """

    type: Literal[ItemType.LUNCH_BREAK] = ItemType.LUNCH_BREAK
    start_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$")
    end_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$")
    duration_min: int = Field(..., ge=0, description="Czas przerwy")
    label: str = Field(
        default="Lunch / przerwa regeneracyjna", description="Etykieta"
    )
    suggestions: List[str] = Field(
        default_factory=list,
        description="Backend generuje (ETAP 1: statyczne teksty)",
    )


class DinnerBreakItem(BaseModel):
    """
    Przerwa na kolację - 18:00-19:30 (jeśli jest czas w dniu).
    Backend generuje suggestions z naciskiem na regionalne jedzenie.
    """

    type: Literal[ItemType.DINNER_BREAK] = ItemType.DINNER_BREAK
    start_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$")
    end_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$")
    duration_min: int = Field(..., ge=0, description="Czas przerwy")
    label: str = Field(
        default="Kolacja / regionalne smaki", description="Etykieta"
    )
    suggestions: List[str] = Field(
        default_factory=list,
        description="Backend generuje (ETAP 1: statyczne teksty)",
    )


class FreeTimeItem(BaseModel):
    """
    Wolny czas między atrakcjami.
    Backend customizuje label kontekstowo.
    """

    type: Literal[ItemType.FREE_TIME] = ItemType.FREE_TIME
    start_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$")
    end_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):([0-5]\d)$")
    duration_min: int = Field(..., ge=0, description="Czas wolny")
    label: str = Field(
        ...,
        description="Backend customizuje: 'Przerwa przed kolejną atrakcją'",
    )


# =========================
# DISCRIMINATED UNION
# =========================

PlanItem = Union[
    DayStartItem,
    DayEndItem,
    ParkingItem,
    TransitItem,
    AttractionItem,
    LunchBreakItem,
    DinnerBreakItem,
    FreeTimeItem,
]


# =========================
# DAY PLAN
# =========================


class DayPlan(BaseModel):
    """Plan dla pojedynczego dnia."""

    day: int = Field(..., ge=1, description="Numer dnia (1-indexed)")
    items: List[PlanItem] = Field(
        default_factory=list, description="Lista items (7 typów)"
    )

    # ETAP 2 Day 5: Quality + Explainability
    quality_badges: List[str] = Field(
        default_factory=list,
        description="Quality badges for the day (has_must_see, good_variety, realistic_timing, balanced_intensity)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "day": 1,
                "items": [
                    {"type": "day_start", "time": "09:00"},
                    {
                        "type": "parking",
                        "start_time": "09:00",
                        "end_time": "09:15",
                        "name": "Parking przy Termach",
                        "address": "Jagiellońska 1, Zakopane",
                        "lat": 49.505,
                        "lng": 20.088,
                        "parking_type": "paid",
                        "walk_time_min": 2,
                    },
                    {
                        "type": "transit",
                        "start_time": "09:15",
                        "end_time": "09:20",
                        "duration_min": 5,
                        "mode": "walk",
                        "from": "Parking przy Termach",
                        "to": "Muzeum Oscypka",
                    },
                    {"type": "day_end", "time": "19:00"},
                ],
            }
        }


# =========================
# PLAN RESPONSE
# =========================


class PlanResponse(BaseModel):
    """
    Główny response dla planu podróży.
    Zgodny z plan_example_full_day_v1.json + wyjaśnienia klientki.
    """

    plan_id: str = Field(..., description="Unikalny ID planu")
    version: int = Field(default=1, description="Wersja planu")
    days: List[DayPlan] = Field(
        default_factory=list, description="Lista dni z items"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "plan_id": "plan_20260125_abc123",
                "version": 1,
                "days": [
                    {
                        "day": 1,
                        "items": [
                            {"type": "day_start", "time": "09:00"},
                            {"type": "day_end", "time": "19:00"},
                        ],
                    }
                ],
            }
        }
