"""
Dependency injection for FastAPI.
Provides repository instances with proper lifecycle management.
"""
import os
from functools import lru_cache
from fastapi import Depends
from sqlalchemy.orm import Session

from app.infrastructure.repositories import (
    POIRepository,
    PlanRepository,
    DestinationsRepository,
)
from app.infrastructure.database import get_session


# Singleton instances (for stateless repositories)
_poi_repo = None
_destinations_repo = None


@lru_cache()
def get_poi_repository() -> POIRepository:
    """
    Returns singleton POI repository.
    
    ETAP 1: Excel-based in-memory cache.
    ETAP 2: PostgreSQL + Redis cache (deferred).
    """
    global _poi_repo
    
    if _poi_repo is None:
        # TODO: move path to settings
        excel_path = os.path.join("data", "zakopane.xlsx")
        _poi_repo = POIRepository(excel_path)
    
    return _poi_repo


def get_plan_repository(db: Session = Depends(get_session)) -> PlanRepository:
    """
    Returns Plan repository with database session.
    
    ETAP 1: In-memory dict storage (deprecated).
    ETAP 2: PostgreSQL persistence (current).
    
    Note: Not cached - creates new instance per request with session.
    """
    return PlanRepository(db)


@lru_cache()
def get_destinations_repository() -> DestinationsRepository:
    """
    Returns singleton Destinations repository.
    
    ETAP 1: JSON file.
    ETAP 2: PostgreSQL destinations table (deferred).
    """
    global _destinations_repo
    
    if _destinations_repo is None:
        # TODO: move path to settings
        json_path = os.path.join("data", "destinations.json")
        _destinations_repo = DestinationsRepository(json_path)
    
    return _destinations_repo
