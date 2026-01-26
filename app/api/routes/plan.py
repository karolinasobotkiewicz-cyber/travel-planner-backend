"""
Plan endpoints - preview, status, get plan.
"""
from fastapi import APIRouter, HTTPException, status, Depends
import uuid

from app.domain.models.trip_input import TripInput
from app.domain.models.plan import PlanResponse
from app.infrastructure.repositories import PlanRepository, POIRepository
from app.api.dependencies import (
    get_plan_repository,
    get_poi_repository
)
from app.application.services.plan_service import PlanService


router = APIRouter()


@router.post("/preview", response_model=PlanResponse, status_code=status.HTTP_200_OK)
def preview_plan(
    trip_input: TripInput,
    plan_repo: PlanRepository = Depends(get_plan_repository),
    poi_repo: POIRepository = Depends(get_poi_repository)
):
    """
    Generuje podglad planu przed platnoscia.
    
    ETAP 1: Zwraca prawdziwy plan z silnika.
    Klient widzi co dostanie przed zaplaceniem.
    
    Flow:
    1. TripInput validation (Pydantic)
    2. PlanService.generate_plan() - używa engine.py
    3. Plan zapisany w repository
    4. Zwrot PlanResponse
    """
    # Utworz service z POI repository
    plan_service = PlanService(poi_repo)
    
    # Generuj plan z prawdziwego silnika (4.10, 4.11, 4.12)
    plan = plan_service.generate_plan(trip_input)
    
    # Zapisz w repository
    plan_repo.save(plan)
    
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