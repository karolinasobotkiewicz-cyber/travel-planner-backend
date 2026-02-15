"""
Plan endpoints - preview, status, get plan.
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Dict, Any
from pydantic import BaseModel, Field

from app.domain.models.trip_input import TripInput
from app.domain.models.plan import PlanResponse
from app.infrastructure.repositories import (
    PlanRepository,
    POIRepository,
    PlanVersionRepository
)
from app.api.dependencies import (
    get_plan_repository,
    get_poi_repository,
    get_version_repository,
    get_plan_editor
)
from app.application.services.plan_service import PlanService
from app.application.services.plan_editor import PlanEditor


router = APIRouter()


@router.post(
    "/preview",
    response_model=PlanResponse,
    status_code=status.HTTP_200_OK
)
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
            change_summary="Initial plan generation (version 1)"
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
    Each version includes: version_number, created_at, change_type,
    change_summary.
    
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


@router.get(
    "/{plan_id}/versions/{version_number}",
    response_model=Dict[str, Any]
)
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
                detail=(
                    f"Target version {target_version} not found "
                    f"for plan {plan_id}"
                )
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
            "new_version_number": (
                latest_version["version_number"]
                if latest_version
                else None
            ),
            "rolled_back_to": target_version
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rollback failed: {str(e)}"
        )

# ============================================================================
# EDITING ENDPOINTS (ETAP 2 - Day 7)
# ============================================================================


class RemoveItemRequest(BaseModel):
    """Request model for removing an item from a day plan."""
    item_id: str
    avoid_cooldown_hours: int = 24


class ReplaceItemRequest(BaseModel):
    """Request model for replacing an item in a day plan."""
    item_id: str
    strategy: str = "SMART_REPLACE"
    preferences: Dict[str, Any] = {}


@router.post(
    "/{plan_id}/days/{day_number}/remove",
    response_model=PlanResponse
)
def remove_item_from_day(
    plan_id: str,
    day_number: int,
    request: RemoveItemRequest,
    plan_repo: PlanRepository = Depends(get_plan_repository),
    version_repo: PlanVersionRepository = Depends(get_version_repository),
    poi_repo: POIRepository = Depends(get_poi_repository),
    editor: PlanEditor = Depends(get_plan_editor)
):
    """
    Remove an item from a specific day and save as new version.
    
    Flow:
    1. Load current plan
    2. Apply remove_item() edit
    3. Recalculate times (reflow)
    4. Save as new version
    5. Return updated plan
    
    Args:
        plan_id: UUID of the plan
        day_number: Day number (1-indexed)
        request: RemoveItemRequest with item_id and avoid_cooldown_hours
        
    Returns:
        Updated PlanResponse with item removed, gap filled, times recalculated
        
    ETAP 2 Day 7: Editing API with versioning.
    """
    try:
        # Load current plan
        plan = plan_repo.get_by_id(plan_id)
        if plan is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plan {plan_id} not found"
            )
        
        # Find target day
        if day_number < 1 or day_number > len(plan.days):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid day_number {day_number}. "
                    f"Plan has {len(plan.days)} days."
                )
            )
        
        day_plan = plan.days[day_number - 1]
        
        # Get all POIs for gap filling
        all_pois = poi_repo.get_all()
        all_pois_dicts = [poi.model_dump(by_alias=True) for poi in all_pois]
        
        # Create context for editing
        context = {
            "season": "winter",  # TODO: extract from plan or use current date
            "weather": "sunny",
            "transport": "car"
        }
        
        # Create user preferences (from plan metadata or defaults)
        user = {
            "group_type": "couples",
            "budget_level": 2,
            "preferences": ["hiking"]
        }
        
        # Apply edit
        updated_day = editor.remove_item(
            day_plan=day_plan,
            item_id=request.item_id,
            all_pois=all_pois_dicts,
            context=context,
            user=user,
            avoid_cooldown_hours=request.avoid_cooldown_hours
        )
        
        # Update plan with edited day
        plan.days[day_number - 1] = updated_day
        
        # Save updated plan
        plan_repo.save(plan)
        
        # Save new version
        try:
            days_json = {
                "days": [day.dict() for day in plan.days]
            }
            version_repo.save_version(
                plan_id=plan.plan_id,
                days_json=days_json,
                change_type="remove_item",
                change_summary=(
                    f"Removed item {request.item_id} "
                    f"from day {day_number}"
                )
            )
        except Exception as e:
            print(f"Warning: Failed to save version: {e}")
        
        return plan
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove item: {str(e)}"
        )


@router.post(
    "/{plan_id}/days/{day_number}/replace",
    response_model=PlanResponse
)
def replace_item_in_day(
    plan_id: str,
    day_number: int,
    request: ReplaceItemRequest,
    plan_repo: PlanRepository = Depends(get_plan_repository),
    version_repo: PlanVersionRepository = Depends(get_version_repository),
    poi_repo: POIRepository = Depends(get_poi_repository),
    editor: PlanEditor = Depends(get_plan_editor)
):
    """
    Replace an item in a specific day with similar POI and save as new version.
    
    Flow:
    1. Load current plan
    2. Apply replace_item() with SMART_REPLACE
    3. Recalculate times (reflow)
    4. Save as new version
    5. Return updated plan
    
    Args:
        plan_id: UUID of the plan
        day_number: Day number (1-indexed)
        request: ReplaceItemRequest with item_id, strategy, preferences
        
    Returns:
        Updated PlanResponse with item replaced, times recalculated
        
    ETAP 2 Day 7: Editing API with SMART_REPLACE.
    """
    try:
        # Load current plan
        plan = plan_repo.get_by_id(plan_id)
        if plan is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plan {plan_id} not found"
            )
        
        # Find target day
        if day_number < 1 or day_number > len(plan.days):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid day_number {day_number}. "
                    f"Plan has {len(plan.days)} days."
                )
            )
        
        day_plan = plan.days[day_number - 1]
        
        # Get all POIs for replacement
        all_pois = poi_repo.get_all()
        all_pois_dicts = [poi.model_dump(by_alias=True) for poi in all_pois]
        
        # Create context for editing
        context = {
            "season": "winter",
            "weather": "sunny",
            "transport": "car"
        }
        
        # Create user preferences
        user = {
            "group_type": "couples",
            "budget_level": 2,
            "preferences": ["hiking"]
        }
        
        # Apply edit
        updated_day = editor.replace_item(
            day_plan=day_plan,
            item_id=request.item_id,
            all_pois=all_pois_dicts,
            context=context,
            user=user,
            strategy=request.strategy
        )
        
        # Update plan with edited day
        plan.days[day_number - 1] = updated_day
        
        # Save updated plan
        plan_repo.save(plan)
        
        # Save new version
        try:
            days_json = {
                "days": [day.dict() for day in plan.days]
            }
            version_repo.save_version(
                plan_id=plan.plan_id,
                days_json=days_json,
                change_type="replace_item",
                change_summary=(
                    f"Replaced item {request.item_id} in day {day_number} "
                    f"using {request.strategy}"
                )
            )
        except Exception as e:
            print(f"Warning: Failed to save version: {e}")
        
        return plan
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to replace item: {str(e)}"
        )


# ============================================
# REGENERATE TIME RANGE (ETAP 2 - DAY 8)
# ============================================

class RegenerateRangeRequest(BaseModel):
    """Request to regenerate time range with pinned items."""
    from_time: str = Field(..., description="Start time HH:MM")
    to_time: str = Field(..., description="End time HH:MM")
    pinned_items: List[str] = Field(
        default=[],
        description="POI IDs to keep (locked)"
    )


@router.post(
    "/{plan_id}/days/{day_number}/regenerate",
    response_model=PlanResponse
)
def regenerate_time_range_in_day(
    plan_id: str,
    day_number: int,
    request: RegenerateRangeRequest,
    plan_repo: PlanRepository = Depends(get_plan_repository),
    version_repo: PlanVersionRepository = Depends(get_version_repository),
    poi_repo: POIRepository = Depends(get_poi_repository),
    editor: PlanEditor = Depends(get_plan_editor)
):
    """
    Regenerate time range in day plan with pinned items.
    
    ETAP 2 - DAY 8 (19.02.2026)
    
    Regenerates POIs in specified time range while keeping pinned items locked.
    
    **Flow:**
    1. Load current plan
    2. Extract items in time range (from_time to to_time)
    3. Keep pinned items locked
    4. Remove unpinned attractions
    5. Re-run mini planning for available slots
    6. Merge before + regenerated + after
    7. Recalculate all times (full reflow)
    8. Save as new version
    9. Return updated plan
    
    **Example:**
    ```json
    {
        "from_time": "14:00",
        "to_time": "17:00",
        "pinned_items": ["poi_10"]
    }
    ```
    
    **Result:**
    - All attractions in 14:00-17:00 replaced
    - Except poi_10 (pinned, stays in place)
    - New POIs selected based on scoring
    - Times recalculated for entire day
    - New version created (change_type="regenerate_range")
    """
    try:
        # Load plan
        plan = plan_repo.get_by_id(plan_id)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plan {plan_id} not found"
            )
        
        # Validate day number
        if day_number < 1 or day_number > len(plan.days):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid day_number {day_number}. "
                    f"Plan has {len(plan.days)} days"
                )
            )
        
        # Validate time range
        if request.from_time >= request.to_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="from_time must be before to_time"
            )
        
        # Get target day (0-indexed)
        day_plan = plan.days[day_number - 1]
        
        # TODO: Extract context and user from plan metadata
        # For now, use defaults (same as remove/replace)
        context = {
            "season": "summer",
            "date": "2026-07-15",
            "weather": {
                "condition": "sunny",
                "precip": False,
                "temp_c": 22
            },
            "transport": "car",
            "has_car": True,
            "daylight_start": "05:30",
            "daylight_end": "21:00"
        }
        
        user = {
            "target_group": "couples",
            "preferences": {
                "preferred_activities": ["hiking", "nature", "culture"],
                "avoid_crowds": False,
                "pace": "moderate"
            },
            "budget_level": 2,
            "daily_limit": None,
            "group_size": 2
        }
        
        # Get all POIs
        all_pois = poi_repo.get_all()
        all_pois_dicts = [poi.model_dump(by_alias=True) for poi in all_pois]
        
        # Apply regenerate
        updated_day = editor.regenerate_time_range(
            day_plan=day_plan,
            from_time=request.from_time,
            to_time=request.to_time,
            pinned_items=request.pinned_items,
            all_pois=all_pois_dicts,
            context=context,
            user=user
        )
        
        # Update day in plan
        plan.days[day_number - 1] = updated_day
        
        # Save updated plan
        plan_repo.save(plan)
        
        # Save version
        try:
            days_json = {
                "days": [day.model_dump() for day in plan.days]
            }
            pinned_str = ", ".join(request.pinned_items) if request.pinned_items else "none"
            version_repo.save_version(
                plan_id=plan.plan_id,
                days_json=days_json,
                change_type="regenerate_range",
                change_summary=(
                    f"Regenerated day {day_number} "
                    f"from {request.from_time} to {request.to_time}, "
                    f"pinned: {pinned_str}"
                )
            )
        except Exception as e:
            print(f"Warning: Failed to save version: {e}")
        
        return plan
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate range: {str(e)}"
        )
