"""
Dependency injection for FastAPI.
Singleton instances of repositories.
"""
import os
from functools import lru_cache

from app.infrastructure.repositories import (
    POIRepository,
    PlanRepository,
    DestinationsRepository,
)


# Singleton instances
_poi_repo = None
_plan_repo = None
_destinations_repo = None


@lru_cache()
def get_poi_repository() -> POIRepository:
    """
    Returns singleton POI repository.
    
    ETAP 1: Excel-based in-memory cache.
    ETAP 2: PostgreSQL + Redis cache.
    """
    global _poi_repo
    
    if _poi_repo is None:
        # TODO: move path to settings
        excel_path = os.path.join("data", "zakopane.xlsx")
        _poi_repo = POIRepository(excel_path)
    
    return _poi_repo


@lru_cache()
def get_plan_repository() -> PlanRepository:
    """
    Returns singleton Plan repository.
    
    ETAP 1: In-memory dict storage.
    ETAP 2: PostgreSQL persistence.
    """
    global _plan_repo
    
    if _plan_repo is None:
        _plan_repo = PlanRepository()
    
    return _plan_repo


@lru_cache()
def get_destinations_repository() -> DestinationsRepository:
    """
    Returns singleton Destinations repository.
    
    ETAP 1: JSON file.
    ETAP 2: PostgreSQL destinations table.
    """
    global _destinations_repo
    
    if _destinations_repo is None:
        # TODO: move path to settings
        json_path = os.path.join("data", "destinations.json")
        _destinations_repo = DestinationsRepository(json_path)
    
    return _destinations_repo
