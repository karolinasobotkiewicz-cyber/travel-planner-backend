"""
Trail Repository - PostgreSQL access for mountain trails (ETAP 3).
Queries TrailDB table loaded in Phase 1.
"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.infrastructure.database import TrailDB
from app.infrastructure.database.connection import SessionLocal


class TrailRepository:
    """
    Repository for TrailDB - hiking trail data from PostgreSQL.
    
    Usage:
        repo = TrailRepository()
        trails = repo.get_by_region("Tatry")
        family_trails = repo.get_family_friendly("Tatry")
    """
    
    def __init__(self, session: Optional[Session] = None):
        """
        Initialize repository.
        
        Args:
            session: Optional SQLAlchemy session. If None, creates new session.
        """
        self.session = session or SessionLocal()
        self._owns_session = session is None
    
    def __del__(self):
        """Close session if we created it."""
        if self._owns_session and self.session:
            self.session.close()
    
    def get_all(self) -> List[TrailDB]:
        """Get all trails (37 total)."""
        return self.session.query(TrailDB).all()
    
    def get_by_id(self, trail_id: str) -> Optional[TrailDB]:
        """Get trail by ID."""
        return self.session.query(TrailDB).filter(TrailDB.id == trail_id).first()
    
    def get_by_region(self, region: str) -> List[TrailDB]:
        """
        Get trails by region.
        
        Args:
            region: 'Tatry', 'Kotlina Kłodzka', 'Karkonosze'
        
        Returns:
            List of trails in region
        """
        return self.session.query(TrailDB).filter(TrailDB.region == region).all()
    
    def get_by_difficulty(self, difficulty: str, region: Optional[str] = None) -> List[TrailDB]:
        """
        Get trails by difficulty level.
        
        Args:
            difficulty: 'easy', 'moderate', 'hard', 'extreme'
            region: Optional region filter
        
        Returns:
            List of trails matching difficulty
        """
        query = self.session.query(TrailDB).filter(TrailDB.difficulty_level == difficulty)
        
        if region:
            query = query.filter(TrailDB.region == region)
        
        return query.all()
    
    def get_family_friendly(self, region: Optional[str] = None) -> List[TrailDB]:
        """
        Get family-friendly trails (family_friendly=True).
        
        CRITICAL: Use this for family_kids groups to filter out dangerous trails.
        
        Args:
            region: Optional region filter
        
        Returns:
            List of family-friendly trails
        """
        query = self.session.query(TrailDB).filter(TrailDB.family_friendly == True)
        
        if region:
            query = query.filter(TrailDB.region == region)
        
        return query.all()
    
    def get_by_max_duration(self, max_minutes: int, region: Optional[str] = None) -> List[TrailDB]:
        """
        Get trails that fit within time budget.
        
        Args:
            max_minutes: Maximum trail duration (uses time_max field)
            region: Optional region filter
        
        Returns:
            List of trails with time_max <= max_minutes
        """
        query = self.session.query(TrailDB).filter(TrailDB.time_max <= max_minutes)
        
        if region:
            query = query.filter(TrailDB.region == region)
        
        return query.all()
    
    def search(
        self,
        region: Optional[str] = None,
        difficulty: Optional[str] = None,
        family_friendly: Optional[bool] = None,
        max_duration: Optional[int] = None,
        exposure_level: Optional[str] = None
    ) -> List[TrailDB]:
        """
        Advanced search with multiple filters.
        
        Args:
            region: Filter by region
            difficulty: Filter by difficulty level
            family_friendly: Filter by family_friendly flag
            max_duration: Filter by max duration (time_max)
            exposure_level: Filter by exposure level
        
        Returns:
            List of trails matching ALL filters
        
        Example:
            # Get easy family trails in Tatry under 3 hours
            trails = repo.search(
                region="Tatry",
                difficulty="easy",
                family_friendly=True,
                max_duration=180
            )
        """
        query = self.session.query(TrailDB)
        
        if region:
            query = query.filter(TrailDB.region == region)
        
        if difficulty:
            query = query.filter(TrailDB.difficulty_level == difficulty)
        
        if family_friendly is not None:
            query = query.filter(TrailDB.family_friendly == family_friendly)
        
        if max_duration:
            query = query.filter(TrailDB.time_max <= max_duration)
        
        if exposure_level:
            query = query.filter(TrailDB.exposure_level == exposure_level)
        
        return query.all()
    
    def to_dict(self, trail: TrailDB) -> dict:
        """
        Convert TrailDB model to dict format compatible with engine.py.
        
        Engine expects POI-like dict structure with specific field names.
        This method maps TrailDB fields to engine-compatible format.
        
        Args:
            trail: TrailDB SQLAlchemy model
        
        Returns:
            Dict with engine-compatible structure
        """
        return {
            "id": trail.id,
            "type": "trail",  # NEW: distinguish from POI
            "name": trail.trail_name,
            "peak_name": trail.peak_name,
            "region": trail.region,
            
            # Trail characteristics
            "difficulty_level": trail.difficulty_level,
            "length_km": float(trail.length_km) if trail.length_km else 0.0,
            "elevation_gain_m": trail.elevation_gain_m,
            "trail_color": trail.trail_color,
            
            # Timing (engine uses duration_min/max)
            "duration_min": trail.time_min,
            "duration_max": trail.time_max,
            "best_season": trail.best_season,
            
            # Safety & filtering
            "family_friendly": trail.family_friendly,
            "exposure_level": trail.exposure_level,
            "weather_dependency": trail.weather_dependency,
            "technical_difficulty": trail.technical_difficulty,
            
            # Location (engine uses lat/lng for routing)
            "lat": float(trail.start_lat) if trail.start_lat else 0.0,
            "lng": float(trail.start_lng) if trail.start_lng else 0.0,
            "start_point_name": trail.start_point_name,
            "start_elevation_m": trail.start_elevation_m,
            "end_lat": float(trail.end_lat) if trail.end_lat else None,
            "end_lng": float(trail.end_lng) if trail.end_lng else None,
            
            # Target group (JSON array)
            "target_groups": trail.target_group or [],
            "children_min_age": trail.children_min_age,
            
            # Parking (engine uses parking_* fields)
            "parking_name": trail.parking_name,
            "parking_lat": float(trail.parking_lat) if trail.parking_lat else None,
            "parking_lng": float(trail.parking_lng) if trail.parking_lng else None,
            "parking_walk_time_min": trail.parking_walk_time_min,
            "parking_type": trail.parking_type,
            "parking_cost": trail.parking_cost,
            
            # Descriptions
            "description_short": trail.description_short,
            "description_long": trail.description_long,
            "highlights": trail.highlights,
            "pro_tip": trail.pro_tip,
            
            # Scoring (engine uses popularity_score for ranking)
            "popularity_score": float(trail.popularity_score) if trail.popularity_score else 0.0,
            "scenic_score": float(trail.scenic_score) if trail.scenic_score else 0.0,
            "must_do": trail.must_do,
            
            # Metadata
            "image_key": trail.image_key,
            "link_map": trail.link_map,
            "link_description": trail.link_description,
        }
    
    def get_all_as_dicts(self) -> List[dict]:
        """
        Get all trails as engine-compatible dicts.
        
        Convenience method for engine integration.
        
        Returns:
            List of trail dicts ready for engine.py
        """
        trails = self.get_all()
        return [self.to_dict(trail) for trail in trails]
