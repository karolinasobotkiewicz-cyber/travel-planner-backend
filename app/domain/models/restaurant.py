"""
ETAP 3 - Restaurant Model

Represents a restaurant/dining place for meal optimizer.
310 restaurants across 15 cities (Planer - restauracje.xlsx).

CRITICAL: meal_type MUST be 'lunch' OR 'dinner' (single value).
Excel has comma-separated values ('lunch,dinner') - mapping required.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
import uuid


class Restaurant(BaseModel):
    """
    Restaurant/dining place model.
    
    Used by meal optimizer to select lunch/dinner locations.
    Separate from attractions (POI) to enable specialized filtering.
    """

    # =========================
    # CORE IDENTITY
    # =========================
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="UUID generated from name + city + lat"
    )
    
    name: str = Field(..., description="Restaurant name")
    city: str = Field(..., description="City (15 cities)")
    
    # =========================
    # LOCATION
    # =========================
    
    lat: float = Field(..., description="Latitude")
    lng: float = Field(..., description="Longitude")
    address: str = Field(default="", description="Street address")
    region: str = Field(default="", description="Region (Tatry, Kotlina Kłodzka, etc.)")
    
    # =========================
    # MEAL LOGIC (CRITICAL FOR OPTIMIZER)
    # =========================
    
    meal_type: Literal["lunch", "dinner"] = Field(
        ...,
        description="CRITICAL: 'lunch' OR 'dinner' (single value) - optimizer requires this"
    )
    
    cuisine_type: str = Field(
        default="",
        description="Polish, Italian, Asian, etc."
    )
    
    place_type: str = Field(
        default="",
        description="restaurant, cafe, bar, etc."
    )
    
    # =========================
    # TIMING
    # =========================
    
    visit_duration_min: int = Field(
        default=60,
        ge=0,
        description="Minimum visit duration (minutes)"
    )
    
    visit_duration_max: int = Field(
        default=90,
        ge=0,
        description="Maximum visit duration (minutes)"
    )
    
    opening_hours: Optional[dict] = Field(
        default=None,
        description="Weekly opening hours {'mon': '11:00-22:00', ...}"
    )
    
    opening_hours_seasonal: Optional[list] = Field(
        default=None,
        description="Seasonal hours (parsed from Excel)"
    )
    
    # =========================
    # PRICING
    # =========================
    
    price_level: int = Field(
        default=2,
        ge=1,
        le=4,
        description="Price level: 1 (cheap) to 4 (expensive)"
    )
    
    avg_meal_cost: int = Field(
        default=50,
        ge=0,
        description="Average meal cost per person (PLN)"
    )
    
    # =========================
    # CHARACTERISTICS (INTERNAL)
    # =========================
    
    atmosphere: str = Field(
        default="",
        description="casual, formal, family-friendly, romantic"
    )
    
    space: str = Field(
        default="",
        description="indoor/outdoor/both"
    )
    
    reservations_required: bool = Field(
        default=False,
        description="Whether reservations are recommended"
    )
    
    # =========================
    # TARGET GROUP (FILTERING)
    # =========================
    
    target_group: List[str] = Field(
        default_factory=list,
        description="family_kids, couple, solo, group_friends"
    )
    
    children_friendly: bool = Field(
        default=True,
        description="Suitable for families with children"
    )
    
    # =========================
    # QUALITY SIGNALS
    # =========================
    
    popularity_score: float = Field(
        default=0.0,
        ge=0.0,
        le=10.0,
        description="Popularity score (0-10) for weighting"
    )
    
    rating: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=5.0,
        description="Average rating (0-5 stars)"
    )
    
    must_try: bool = Field(
        default=False,
        description="Local specialty / must-try place"
    )
    
    # =========================
    # PARKING
    # =========================
    
    parking_name: str = Field(default="", description="Nearby parking name")
    parking_lat: Optional[float] = Field(default=None, description="Parking latitude")
    parking_lng: Optional[float] = Field(default=None, description="Parking longitude")
    parking_walk_time_min: int = Field(
        default=0,
        ge=0,
        description="Walk time from parking (minutes)"
    )
    
    # =========================
    # METADATA
    # =========================
    
    pro_tip: str = Field(
        default="",
        description="Insider tip (e.g., 'Try the pierogi')"
    )
    
    image_key: str = Field(
        default="",
        description="Image key for Supabase Storage"
    )
    
    link_website: str = Field(default="", description="Restaurant website")
    link_menu: str = Field(default="", description="Online menu link")

    # =========================
    # VALIDATORS
    # =========================
    
    @field_validator("target_group", mode="before")
    @classmethod
    def parse_target_group(cls, v):
        """Convert comma-separated string to list."""
        if isinstance(v, str):
            if not v or v.lower() == 'nan':
                return []
            return [x.strip().lower() for x in v.split(",") if x.strip()]
        return v if v else []
    
    @field_validator("opening_hours", mode="before")
    @classmethod
    def validate_opening_hours(cls, v):
        """Ensure opening_hours is dict or None."""
        if v is None or v == "":
            return None
        if isinstance(v, dict):
            return v
        # Try parsing as JSON
        if isinstance(v, str):
            try:
                import json
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return None
        return None
    
    @field_validator("opening_hours_seasonal", mode="before")
    @classmethod
    def validate_opening_hours_seasonal(cls, v):
        """Ensure opening_hours_seasonal is list or None."""
        if v is None or v == "":
            return None
        if isinstance(v, list):
            return v
        # Try parsing as JSON
        if isinstance(v, str):
            try:
                import json
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else None
            except (json.JSONDecodeError, ValueError):
                return None
        return None

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "rest_zakopane_001",
                "name": "Karczma Po Zbóju",
                "city": "Zakopane",
                "lat": 49.2969,
                "lng": 19.9489,
                "meal_type": "dinner",
                "cuisine_type": "Polish",
                "place_type": "restaurant",
                "visit_duration_min": 60,
                "visit_duration_max": 90,
                "price_level": 2,
                "avg_meal_cost": 60,
                "children_friendly": True,
                "popularity_score": 8.5,
            }
        }
