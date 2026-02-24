"""
Dependency injection for FastAPI.
Provides repository instances with proper lifecycle management.
"""
import os
from functools import lru_cache
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.infrastructure.repositories import (
    POIRepository,
    PlanRepository,
    DestinationsRepository,
    PlanVersionRepository,
)
from app.infrastructure.database import get_session
from app.infrastructure.database.models import User
from app.infrastructure.auth import decode_jwt, get_user_from_token
from app.application.services.plan_editor import PlanEditor


# Security scheme for Swagger UI (shows lock icon)
security = HTTPBearer()


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


def get_version_repository(db: Session = Depends(get_session)) -> PlanVersionRepository:
    """
    Returns PlanVersion repository with database session.
    
    ETAP 2: Version history management (snapshot, rollback, list).
    
    Note: Not cached - creates new instance per request with session.
    """
    return PlanVersionRepository(db)


def get_plan_editor(poi_repo: POIRepository = Depends(get_poi_repository)) -> PlanEditor:
    """
    Returns PlanEditor service instance.
    
    ETAP 2 Day 7: Editing service for remove/replace operations.
    
    Note: Creates new instance per request with POI repository.
    """
    return PlanEditor(poi_repo)


# ==========================================
# ETAP 2: AUTH DEPENDENCIES
# ==========================================


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_session)
) -> User:
    """
    Validate JWT token and return current authenticated user.
    
    **Flow:**
    1. Extract token from Authorization header (Bearer <token>)
    2. Decode and validate JWT signature + expiration
    3. Extract user info (supabase_id, email)
    4. Get or auto-create user in local database
    5. Return User model instance
    
    **Usage:**
        @app.get("/protected")
        async def protected(user: User = Depends(get_current_user)):
            return {"user_id": user.id, "email": user.email}
    
    **Auto-create behavior:**
    - If user doesn't exist in local DB but has valid Supabase JWT
    - Creates new User record with supabase_id + email
    - This happens on first API request after Supabase signup
    
    Args:
        credentials: HTTP Bearer token from Authorization header
        db: Database session
    
    Returns:
        User model instance
        
    Raises:
        HTTPException 401: If token invalid, expired, or malformed
        
    Example Authorization header:
        Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
    """
    # Extract token from credentials
    token = credentials.credentials
    
    # Decode and validate JWT
    payload = decode_jwt(token)
    user_data = get_user_from_token(payload)
    
    # Get or create user in local database
    user = db.query(User).filter(User.supabase_id == user_data["supabase_id"]).first()
    
    if not user:
        # Auto-create user on first request (after Supabase signup)
        user = User(
            supabase_id=user_data["supabase_id"],
            email=user_data["email"],
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
        except Exception:
            # Handle duplicate key error (race condition or test data)
            db.rollback()
            # Try to fetch again
            user = db.query(User).filter(User.supabase_id == user_data["supabase_id"]).first()
            if not user:
                # Still doesn't exist - unexpected error
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user"
                )
    
    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_session)
) -> Optional[User]:
    """
    Optional authentication - returns User if token provided, None otherwise.
    
    **Use cases:**
    - Public endpoints that can be accessed by guests or authenticated users
    - Different behavior for logged-in vs anonymous users
    - Soft authentication checks
    
    **Usage:**
        @app.get("/public-or-private")
        async def endpoint(user: Optional[User] = Depends(get_optional_user)):
            if user:
                return {"message": f"Hello {user.email}"}
            return {"message": "Hello guest"}
    
    **Behavior:**
    - No Authorization header → Returns None (no error)
    - Invalid token → Returns None (graceful failure)
    - Valid token → Returns User instance
    
    Args:
        credentials: Optional HTTP Bearer token
        db: Database session
    
    Returns:
        User instance if valid token provided, None otherwise
        
    Example:
        # No auth header - returns None
        GET /endpoint
        
        # Valid auth - returns User
        GET /endpoint
        Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
    """
    if not credentials:
        return None
    
    # Token provided - MUST be valid or raise 401
    # Don't catch exceptions - let them propagate as 401 errors
    return await get_current_user(credentials, db)
