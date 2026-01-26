"""
POI endpoints - szczegoly punktow zainteresowania.
"""
from fastapi import APIRouter, HTTPException, status, Depends

from app.infrastructure.repositories import POIRepository
from app.api.dependencies import get_poi_repository

router = APIRouter()


@router.get("/{poi_id}")
def get_poi_details(
    poi_id: str,
    poi_repo: POIRepository = Depends(get_poi_repository)
):
    """
    Zwraca pelne szczegoly POI z image_key.
    
    Frontend dostaje poi_id z AttractionItem w planie,
    potem fetchuje pelne dane z tego endpointu.
    
    ETAP 1: Zwraca dane z Excel (przez POI repository).
    ETAP 2: Zwraca z PostgreSQL + cache.
    
    Response zawiera:
    - Wszystkie pola POI (nazwa, opis, ocena, ceny, etc)
    - image_key: relatywna sciezka do zdjecia (np. "poi/poi_123.jpg")
    - Placeholder images w ETAP 1, realne w ETAP 2
    """
    poi = poi_repo.get_by_id(poi_id)
    
    if poi is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"POI {poi_id} not found"
        )
    
    # Convert POI model to dict response
    # TODO: add image_key field in CZESC 4
    return poi.model_dump(by_alias=True)
