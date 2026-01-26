"""
Pydantic models dla trip input request.
Reprezentuje dane wejściowe od klienta dla generowania planu podróży.
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Any
from datetime import date


class LocationInput(BaseModel):
    """Lokalizacja podróży."""

    city: str = Field(..., min_length=1, description="Miasto docelowe")
    country: str = Field(default="Poland", description="Kraj")
    region_type: Optional[str] = Field(
        default=None, description="Typ regionu: mountain, sea, city"
    )

    @field_validator("city")
    @classmethod
    def validate_city(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("City cannot be empty")
        return v.strip()


class GroupInput(BaseModel):
    """Informacje o grupie podróżującej."""

    type: str = Field(
        ...,
        description="Typ grupy: solo, couples, friends, family_kids, seniors",
    )
    size: int = Field(default=1, ge=1, le=20, description="Liczba osób")
    children_age: Optional[int] = Field(
        default=None, ge=0, le=18, description="Wiek dziecka jeśli family_kids"
    )
    crowd_tolerance: int = Field(
        default=1, ge=0, le=3, description="Tolerancja na tłumy: 0=low, 3=high"
    )

    @field_validator("type")
    @classmethod
    def validate_group_type(cls, v: str) -> str:
        allowed = ["solo", "couples", "friends", "family_kids", "seniors"]
        if v not in allowed:
            raise ValueError(f"Group type must be one of {allowed}, got: {v}")
        return v


class TripLengthInput(BaseModel):
    """Długość podróży."""

    days: int = Field(..., ge=1, le=14, description="Liczba dni")
    start_date: date = Field(..., description="Data rozpoczęcia YYYY-MM-DD")

    @field_validator("start_date")
    @classmethod
    def validate_start_date(cls, v: date) -> date:
        # TODO sprawdzić czy data nie jest w przeszłości
        # ale zostawiam na później bo to może być testing data
        return v


class DailyTimeWindow(BaseModel):
    """Okno czasowe dla każdego dnia podróży."""

    start: str = Field(
        default="09:00",
        pattern=r"^([01]\d|2[0-3]):([0-5]\d)$",
        description="Godzina startu dnia HH:MM",
    )
    end: str = Field(
        default="19:00",
        pattern=r"^([01]\d|2[0-3]):([0-5]\d)$",
        description="Godzina końca dnia HH:MM",
    )

    @field_validator("end")
    @classmethod
    def validate_end_after_start(cls, v: str, info: Any) -> str:
        if "start" not in info.data:
            return v

        start = info.data["start"]

        # konwersja HH:MM na minuty
        sh, sm = map(int, start.split(":"))
        eh, em = map(int, v.split(":"))

        start_min = sh * 60 + sm
        end_min = eh * 60 + em

        if end_min <= start_min:
            raise ValueError("End time must be after start time")

        return v


class BudgetInput(BaseModel):
    """Budżet użytkownika."""

    level: int = Field(
        default=2,
        ge=1,
        le=3,
        description="Poziom budżetu: 1=cheap, 2=medium, 3=expensive",
    )
    daily_limit: Optional[int] = Field(
        default=None, ge=0, description="Opcjonalny dzienny limit w PLN"
    )


class TripInput(BaseModel):
    """
    Główny model wejściowy dla generowania planu podróży.
    Mapuje się na parametry engine.py poprzez adapter.
    """

    location: LocationInput
    group: GroupInput
    trip_length: TripLengthInput
    daily_time_window: DailyTimeWindow
    budget: BudgetInput

    transport_modes: List[str] = Field(
        default=["car"],
        description="Środki transportu: walk, car, public_transport",
    )
    preferences: List[str] = Field(
        default_factory=list,
        description="Preferencje użytkownika (tags, typy atrakcji)",
    )

    @field_validator("transport_modes")
    @classmethod
    def validate_transport(cls, v: List[str]) -> List[str]:
        allowed = ["walk", "car", "public_transport"]
        for mode in v:
            if mode not in allowed:
                raise ValueError(
                    f"Transport mode must be in {allowed}, got: {mode}"
                )
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "location": {
                    "city": "Zakopane",
                    "country": "Poland",
                    "region_type": "mountain",
                },
                "group": {
                    "type": "family_kids",
                    "size": 4,
                    "children_age": 8,
                    "crowd_tolerance": 1,
                },
                "trip_length": {"days": 3, "start_date": "2026-02-15"},
                "daily_time_window": {"start": "09:00", "end": "19:00"},
                "budget": {"level": 2, "daily_limit": 500},
                "transport_modes": ["car"],
                "preferences": ["outdoor", "family"],
            }
        }
