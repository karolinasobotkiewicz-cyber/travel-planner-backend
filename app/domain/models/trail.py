"""
ETAP 3 - Trail Model

Represents a mountain trail for hiking optimizer.
37 trails across 3 regions: Tatry, Kotlina Kłodzka, Karkonosze.

Stored in separate table (not POI) because:
1. Different data structure (trail-specific fields)
2. Separate filtering logic (difficulty, exposure, weather)
3. Region-based retrieval (sheet name inference)
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
import uuid


class Trail(BaseModel):
    """
    Mountain trail model.
    
    Used by hiking optimizer for family_kids and adventure groups.
    Critical fields: difficulty_level, family_friendly, weather_dependency.
    """

    # =========================
    # CORE IDENTITY
    # =========================
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="UUID generated from trail_name + region + start_lat"
    )
    
    trail_name: str = Field(..., description="Trail name (e.g., 'Szlak do Morskiego Oka')")
    peak_name: str = Field(default="", description="Target peak/destination name")
    
    region: str = Field(
        ...,
        description="Region (inferred from sheet name: Tatry, Kotlina Kłodzka, Karkonosze)"
    )
    
    # =========================
    # TRAIL CHARACTERISTICS
    # =========================
    
    trail_color: str = Field(
        default="",
        description="Trail color marking (red, blue, green, yellow, black)"
    )
    
    difficulty_level: Literal["easy", "moderate", "hard", "extreme"] = Field(
        ...,
        description="Trail difficulty (MAPPED from 'medium' → 'moderate')"
    )
    
    length_km: float = Field(
        default=0.0,
        ge=0.0,
        description="Trail length in kilometers"
    )
    
    elevation_gain_m: int = Field(
        default=0,
        ge=0,
        description="Total elevation gain in meters"
    )
    
    # =========================
    # TIMING
    # =========================
    
    time_min: int = Field(
        default=120,
        ge=0,
        description="Minimum hiking time (minutes)"
    )
    
    time_max: int = Field(
        default=180,
        ge=0,
        description="Maximum hiking time (minutes)"
    )
    
    best_season: str = Field(
        default="",
        description="Best season for hiking (spring, summer, autumn, winter)"
    )
    
    # =========================
    # SAFETY & FILTERING (CRITICAL)
    # =========================
    
    family_friendly: bool = Field(
        ...,
        description="CRITICAL: Is this trail suitable for families with children?"
    )
    
    exposure_level: Literal["low", "medium", "high", "extreme"] = Field(
        default="low",
        description="Exposure risk (heights, cliffs) - MAPPED from Excel"
    )
    
    weather_dependency: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="Weather dependency (MAPPED: all_weather→low, good_weather_only→high)"
    )
    
    technical_difficulty: str = Field(
        default="",
        description="Technical requirements (none, basic, advanced)"
    )
    
    # =========================
    # LOCATION (START POINT)
    # =========================
    
    start_point_name: str = Field(default="", description="Trailhead name")
    start_lat: float = Field(..., description="Start point latitude")
    start_lng: float = Field(..., description="Start point longitude")
    start_elevation_m: int = Field(
        default=0,
        ge=0,
        description="Start elevation (meters above sea level)"
    )
    
    end_lat: Optional[float] = Field(default=None, description="End point latitude (if different)")
    end_lng: Optional[float] = Field(default=None, description="End point longitude (if different)")
    
    # =========================
    # TARGET GROUP
    # =========================
    
    target_group: List[str] = Field(
        default_factory=list,
        description="family_kids, adventure, nature_lovers, experienced_hikers"
    )
    
    children_min_age: int = Field(
        default=0,
        ge=0,
        description="Minimum recommended age for children"
    )
    
    # =========================
    # PARKING & ACCESS
    # =========================
    
    parking_name: str = Field(default="", description="Parking name")
    parking_lat: Optional[float] = Field(default=None, description="Parking latitude")
    parking_lng: Optional[float] = Field(default=None, description="Parking longitude")
    parking_walk_time_min: int = Field(
        default=0,
        ge=0,
        description="Walk time from parking to trailhead (minutes)"
    )
    
    parking_type: str = Field(
        default="",
        description="free/paid"
    )
    
    parking_cost: int = Field(
        default=0,
        ge=0,
        description="Parking cost (PLN) if paid"
    )
    
    # =========================
    # DESCRIPTION
    # =========================
    
    description_short: str = Field(
        default="",
        description="Short trail description"
    )
    
    description_long: str = Field(
        default="",
        description="Detailed trail description"
    )
    
    highlights: str = Field(
        default="",
        description="Trail highlights (viewpoints, attractions)"
    )
    
    pro_tip: str = Field(
        default="",
        description="Insider tip for hikers"
    )
    
    # =========================
    # SCORING (INTERNAL)
    # =========================
    
    popularity_score: float = Field(
        default=0.0,
        ge=0.0,
        le=10.0,
        description="Popularity score (0-10) for weighting"
    )
    
    scenic_score: float = Field(
        default=0.0,
        ge=0.0,
        le=10.0,
        description="Scenic beauty score (0-10)"
    )
    
    must_do: bool = Field(
        default=False,
        description="Iconic trail / must-do"
    )
    
    # =========================
    # METADATA
    # =========================
    
    image_key: str = Field(
        default="",
        description="Image key for Supabase Storage"
    )
    
    link_map: str = Field(default="", description="Link to trail map")
    link_description: str = Field(default="", description="Link to trail description")

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

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "trail_tatry_001",
                "trail_name": "Szlak do Morskiego Oka",
                "peak_name": "Morskie Oko",
                "region": "Tatry",
                "trail_color": "blue",
                "difficulty_level": "easy",
                "length_km": 9.0,
                "elevation_gain_m": 200,
                "time_min": 120,
                "time_max": 180,
                "family_friendly": True,
                "exposure_level": "low",
                "weather_dependency": "low",
                "start_point_name": "Parking Palenica Białczańska",
                "start_lat": 49.2419,
                "start_lng": 20.0712,
                "popularity_score": 9.5,
                "must_do": True,
            }
        }
