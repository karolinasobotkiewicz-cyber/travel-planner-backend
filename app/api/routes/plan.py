"""
Plan endpoints - preview, status, get plan.
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Dict, Any
from pydantic import BaseModel
import uuid

from app.domain.models.trip_input import TripInput
from app.domain.models.plan import PlanResponse
from app.infrastructure.repositories import PlanRepository, POIRepository, PlanVersionRepository
from app.api.dependencies import (
    get_plan_repository,
    get_poi_repository,
    get_version_repository
)
from app.application.services.plan_service import PlanService


router = APIRouter()


@router.post("/preview", response_model=PlanResponse, status_code=status.HTTP_200_OK)
def preview_plan(
    trip_input: TripInput,
    plan_repo: PlanRepository = Depends(get_plan_repository),
    poi_repo: POIRepository = Depends(get_poi_repository),
    version_repo: PlanVersionRepository = Depends(get_version_repository)
):
    """
    Generuje podglad planu przed platnoscia.
    
    ETAP 1: Zwraca prawdziwy plan z silnika.
    Klient widzi co dostanie przed zaplaceniem.
    
    ETAP 2: Auto-save version #1 after generation.
    
    Flow:
    1. TripInput validation (Pydantic)
    2. PlanService.generate_plan() - używa engine.py
    3. Plan zapisany w repository
    4. Version #1 auto-saved (ETAP 2)
    5. Zwrot PlanResponse
    """
    # Utworz service z POI repository
    plan_service = PlanService(poi_repo)
    
    # Generuj plan z prawdziwego silnika (4.10, 4.11, 4.12)
    plan = plan_service.generate_plan(trip_input)
    
    # Zapisz w repository
    plan_repo.save(plan)
    
    # ETAP 2: Auto-save version #1
    try:
        days_json = {
            "days": [day.dict() for day in plan.days]
        }
        version_repo.save_version(
            plan_id=plan.plan_id,
            days_json=days_json,
            change_type="generated",
            change_summary=f"Initial plan generation (version 1)"
        )
    except Exception as e:
        # Log error but don't fail request (version is secondary)
        print(f"Warning: Failed to save version #1: {e}")
    
    return plan


@router.get("/{plan_id}/status")
def get_plan_status(
    plan_id: str,
    plan_repo: PlanRepository = Depends(get_plan_repository)
):
    """
    Sprawdza status planu (polling endpoint).
    
    Statusy:
    - pending: plan w trakcie generowania
    - ready: plan gotowy
    - failed: blad generowania
    - payment_required: wymaga platnosci (ETAP 2)
    """
    metadata = plan_repo.get_metadata(plan_id)
    
    if metadata is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan {plan_id} not found"
        )
    
    return metadata


@router.get("/{plan_id}", response_model=PlanResponse)
def get_full_plan(
    plan_id: str,
    plan_repo: PlanRepository = Depends(get_plan_repository)
):
    """
    Zwraca pelny wygenerowany plan.
    
    ETAP 1: Bez walidacji platnosci.
    ETAP 2: Tylko po oplaceniu.
    """
    plan = plan_repo.get_by_id(plan_id)
    
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan {plan_id} not found"
        )
    
    # TODO: sprawdzic czy oplacony (ETAP 2)
    
    return plan


# ============================================================================
# VERSIONING ENDPOINTS (ETAP 2 - Day 4)
# ============================================================================

class RollbackRequest(BaseModel):
    """Request model for rollback endpoint."""
    target_version: int


@router.get("/{plan_id}/versions", response_model=List[Dict[str, Any]])
def list_plan_versions(
    plan_id: str,
    version_repo: PlanVersionRepository = Depends(get_version_repository)
):
    """
    Lists all versions of a plan (metadata only).
    
    Returns version history sorted by version_number DESC.
    Each version includes: version_number, created_at, change_type, change_summary.
    
    ETAP 2: Version tracking for edit history and rollback.
    """
    try:
        versions = version_repo.list_versions(plan_id)
        
        if not versions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No versions found for plan {plan_id}"
            )
        
        return versions
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list versions: {str(e)}"
        )


@router.get("/{plan_id}/versions/{version_number}", response_model=Dict[str, Any])
def get_plan_version(
    plan_id: str,
    version_number: int,
    version_repo: PlanVersionRepository = Depends(get_version_repository)
):
    """
    Gets full snapshot of a specific version (including days_json).
    
    Use this to preview what the plan looked like at a specific version.
    Useful before rollback to confirm target version.
    
    ETAP 2: Version history with full snapshot.
    """
    try:
        version = version_repo.get_version(plan_id, version_number)
        
        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version {version_number} not found for plan {plan_id}"
            )
        
        return version
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get version: {str(e)}"
        )


@router.post("/{plan_id}/rollback", response_model=Dict[str, Any])
def rollback_plan(
    plan_id: str,
    rollback_request: RollbackRequest,
    version_repo: PlanVersionRepository = Depends(get_version_repository),
    plan_repo: PlanRepository = Depends(get_plan_repository)
):
    """
    Rolls back plan to a previous version.
    
    Logic:
    1. Fetch target version snapshot
    2. Create new version with change_type='rollback'
    3. Copy days_json from target version to new version
    4. Update Plan.updated_at
    
    This creates a NEW version (doesn't delete newer versions).
    Example: If plan has versions [1, 2, 3] and you rollback to 2,
    result is [1, 2, 3, 4] where 4 is copy of 2.
    
    ETAP 2: Rollback with version lineage tracking.
    """
    try:
        target_version = rollback_request.target_version
        
        # Verify target version exists
        version = version_repo.get_version(plan_id, target_version)
        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target version {target_version} not found for plan {plan_id}"
            )
        
        # Perform rollback (creates new version)
        success = version_repo.rollback(plan_id, target_version)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Rollback failed"
            )
        
        # Get updated version list
        versions = version_repo.list_versions(plan_id)
        latest_version = versions[0] if versions else None
        
        return {
            "success": True,
            "message": f"Rolled back to version {target_version}",
            "new_version_number": latest_version["version_number"] if latest_version else None,
            "rolled_back_to": target_version
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rollback failed: {str(e)}"
        )