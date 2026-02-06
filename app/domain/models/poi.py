"""
Pydantic model dla POI (Point of Interest).
Struktura z zakopane.xlsx + rozróżnienie internal/response fields.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Union


class POI(BaseModel):
    """
    Point of Interest - atrakcja turystyczna.

    Pola oznaczone jako internal NIE wracają w PlanResponse.
    Frontend dostaje tylko niezbędne dane w AttractionItem.
    """

    # =========================
    # PODSTAWOWE
    # =========================

    id: str = Field(..., alias="ID", description="Unikalny ID POI")
    name: str = Field(..., alias="Name", description="Nazwa atrakcji")

    description_short: str = Field(
        default="",
        alias="Description_short",
        description="Krótki opis (RESPONSE)",
    )
    description_long: str = Field(
        default="",
        alias="Description_long",
        description="Długi opis (internal)",
    )
    why_visit: str = Field(
        default="", alias="Why visit", description="Dlaczego warto odwiedzić"
    )

    # =========================
    # LOKALIZACJA (RESPONSE)
    # =========================

    address: str = Field(default="", alias="Address")
    region: str = Field(default="", alias="Region")
    lat: float = Field(..., alias="Lat", description="Szerokość")
    lng: float = Field(..., alias="Lng", description="Długość")
    city: str = Field(default="Zakopane", alias="City")
    
    # =========================
    # MEDIA (4.14 - RESPONSE)
    # =========================
    
    image_key: str = Field(
        default="",
        alias="image_key",
        description="Klucz do obrazka: poi_muzeum_tatrzanskie.jpg"
    )

    # =========================
    # OPENING HOURS (INTERNAL)
    # =========================

    opening_hours: Optional[Dict[str, str]] = Field(
        default=None,
        alias="Opening hours",
        description="Godziny otwarcia - JSON dict {'mon': '08:00-16:00', ...}",
    )
    opening_hours_seasonal: Optional[Union[List[Dict[str, str]], Dict[str, str]]] = Field(
        default=None,
        alias="opening_hours_seasonal",
        description="Godziny sezonowe - NEW (06.02.2026): List[Dict] multi-season lub Dict (old format)",
    )
    link_hours: str = Field(
        default="",
        alias="Link do godzin",
        description="Link do strony z godzinami",
    )

    # =========================
    # CZAS WIZYTY (INTERNAL)
    # =========================

    time_min: int = Field(default=30, alias="time_min", ge=0)
    time_max: int = Field(default=60, alias="time_max", ge=0)
    recommended_time_of_day: str = Field(
        default="", alias="recommended_time_of_day"
    )

    # =========================
    # CENY (RESPONSE via TicketInfo)
    # =========================

    price: Optional[float] = Field(default=None, alias="Price")
    ticket_normal: int = Field(default=0, alias="ticket_normal", ge=0)
    ticket_reduced: int = Field(default=0, alias="ticket_reduced", ge=0)
    link_pricing: str = Field(default="", alias="Link do cennika")

    @property
    def free_entry(self) -> bool:
        """Czy wstęp darmowy."""
        return self.ticket_normal == 0 and self.ticket_reduced == 0

    # =========================
    # CHARAKTERYSTYKA (INTERNAL)
    # =========================

    space: str = Field(
        default="", alias="Space", description="outdoor/indoor - INTERNAL"
    )
    intensity: str = Field(
        default="", alias="Intensity", description="low/medium/high - INTERNAL"
    )
    weather_dependent: str = Field(
        default="",
        alias="weather_dependency",
        description="Zależność od pogody - INTERNAL",
    )

    # =========================
    # SCORING (INTERNAL)
    # =========================

    must_see_score: float = Field(
        default=0.0,
        alias="Must see score",
        description="Priorytet atrakcji - INTERNAL",
    )
    popularity_score: float = Field(
        default=0.0,
        alias="popularity_score",
        description="Popularność - INTERNAL",
    )
    crowd_level: str = Field(
        default="", alias="crowd_level", description="Poziom tłumu - INTERNAL"
    )
    peak_hours: str = Field(
        default="",
        alias="Peak hours",
        description="Godziny szczytu - INTERNAL",
    )

    # =========================
    # TARGET GROUP (INTERNAL)
    # =========================

    target_group: List[str] = Field(
        default_factory=list,
        alias="Target group",
        description="Grupa docelowa - INTERNAL",
    )
    children_age: str = Field(
        default="",
        alias="Children's age",
        description="Wiek dzieci - INTERNAL",
    )
    kids_only: str = Field(
        default="",
        alias="kids_only",
        description="Tylko dla dzieci? - INTERNAL",
    )

    # =========================
    # KATEGORIE
    # =========================

    type_of_attraction: str = Field(default="", alias="Type of attraction")
    activity_style: str = Field(default="", alias="Activity_style")
    budget_type: str = Field(default="", alias="Budget type")
    seasonality: str = Field(default="", alias="Seasonality of attractions")

    # =========================
    # PARKING (RESPONSE via ParkingInfo)
    # =========================

    parking_name: str = Field(default="", alias="parking_name")
    parking_address: str = Field(default="", alias="parking_address")
    parking_lat: Optional[float] = Field(default=None, alias="parking_lat")
    parking_lng: Optional[float] = Field(default=None, alias="parking_lng")
    parking_type: str = Field(default="", alias="parking_type")
    parking_walk_time_min: int = Field(
        default=0, alias="parking_walk_time_min", ge=0
    )

    # =========================
    # POZOSTAŁE
    # =========================

    pro_tip: str = Field(default="", alias="Pro_tip")
    priority_level: str = Field(default="", alias="priority_level")
    tags: List[str] = Field(default_factory=list, alias="Tags")
    
    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, v):
        """Convert comma-separated string to list"""
        if isinstance(v, str):
            if not v or v.lower() == 'nan':
                return []
            return [x.strip().lower() for x in v.split(",") if x.strip()]
        return v if v else []
    
    @field_validator("target_group", mode="before")
    @classmethod
    def parse_target_group(cls, v):
        """Convert comma-separated string to list"""
        if isinstance(v, str):
            if not v or v.lower() == 'nan':
                return []
            return [x.strip().lower() for x in v.split(",") if x.strip()]
        return v if v else []

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "ID": "poi_zakopane_001",
                "Name": "Muzeum Oscypka",
                "Description_short": "Interaktywne muzeum o tradycji oscypka",
                "Lat": 49.50582015,
                "Lng": 20.08808064,
                "Address": "Partyzantów 47, Zakopane",
                "ticket_normal": 75,
                "ticket_reduced": 60,
                "time_min": 60,
                "time_max": 90,
                "parking_name": "Parking przy Termach",
                "parking_walk_time_min": 2,
            }
        }

    # =========================
    # VALIDATORS (Excel type coercion)
    # =========================

    @field_validator('opening_hours', 'opening_hours_seasonal', mode='before')
    @classmethod
    def validate_opening_hours(cls, v):
        """Ensure opening_hours is dict or None."""
        if v is None or v == "":
            return None
        if isinstance(v, dict):
            return v
        # If string, try to parse as JSON (for backward compatibility)
        if isinstance(v, str):
            try:
                import json
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return None
        return None

    @field_validator('crowd_level', mode='before')
    @classmethod
    def validate_crowd_level(cls, v):
        """Convert int to string for crowd_level."""
        if isinstance(v, int):
            return str(v)
        return str(v) if v is not None else ""

    @field_validator('kids_only', mode='before')
    @classmethod
    def validate_kids_only(cls, v):
        """Convert bool to string for kids_only."""
        if isinstance(v, bool):
            return "true" if v else "false"
        return str(v) if v is not None else ""

    @field_validator('tags', mode='before')
    @classmethod
    def validate_tags(cls, v):
        """Convert list to comma-separated string for tags."""
        if isinstance(v, list):
            return ", ".join(str(item) for item in v)
        return str(v) if v is not None else ""

    # =========================
    # METODY POMOCNICZE
    # =========================

    def get_target_groups(self) -> List[str]:
        """Parsuje target_group na listę."""
        if not self.target_group:
            return []
        return [g.strip().lower() for g in self.target_group.split(",")]

    def get_tags(self) -> List[str]:
        """Parsuje Tags na listę."""
        if not self.tags:
            return []
        return [t.strip().lower() for t in self.tags.split(",")]

    def to_response_dict(self) -> Dict[str, Any]:
        """
        Konwertuje POI na dict dla response (bez internal fields).
        Używane przy tworzeniu AttractionItem.
        """
        return {
            "poi_id": self.id,
            "name": self.name,
            "description_short": self.description_short,
            "lat": self.lat,
            "lng": self.lng,
            "address": self.address,
            "ticket_info": {
                "ticket_normal": self.ticket_normal,
                "ticket_reduced": self.ticket_reduced,
            },
            "parking": {
                "name": self.parking_name,
                "walk_time_min": self.parking_walk_time_min,
            },
        }
