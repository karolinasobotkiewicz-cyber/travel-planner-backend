"""
Content endpoints - destinations, home content.
"""
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import List

from app.infrastructure.repositories import DestinationsRepository
from app.api.dependencies import get_destinations_repository

router = APIRouter()


def _infer_region_type(region: str) -> str:
    """Infer region_type from region name (ETAP 1 helper)."""
    region_lower = region.lower()
    if "tatry" in region_lower or "góry" in region_lower:
        return "mountain"
    elif "pomorze" in region_lower or "bałtyk" in region_lower:
        return "sea"
    else:
        return "city"


class DestinationItem(BaseModel):
    """Pojedynczy kierunek podrozy z home screen."""
    destination_id: str
    name: str
    country: str
    region_type: str  # mountain, sea, city
    image_key: str  # relatywna sciezka do obrazka
    description_short: str


class HomeContentResponse(BaseModel):
    """Response dla home screen - 8 popularnych kierunkow."""
    destinations: List[DestinationItem]
    featured_count: int


@router.get("/home", response_model=HomeContentResponse)
def get_home_content(
    dest_repo: DestinationsRepository = Depends(get_destinations_repository)
):
    """
    Zwraca content dla home screen - 8 popularnych kierunkow.
    
    ETAP 1: Data z destinations.json (4.13).
    ETAP 2: Prawdziwe dane z bazy + realne zdjecia.
    
    Note: image_key to relatywna sciezka (np. "destination_zakopane.jpg"),
    nie pelny URL. Frontend sam sklada pelny URL.
    """
    # Try to load from repository (JSON file - część 4.13)
    destinations_raw = dest_repo.get_all()
    
    # Map JSON structure to DestinationItem
    destinations = []
    for dest in destinations_raw:
        destinations.append({
            "destination_id": dest.get("id"),  # JSON ma "id", API zwraca "destination_id"
            "name": dest.get("name"),
            "country": "Poland",  # ETAP 1: hardcoded
            "region_type": _infer_region_type(dest.get("region", "")),
            "image_key": dest.get("image_key"),
            "description_short": dest.get("description_short", "")
        })
    
    # Fallback if JSON empty (graceful handling)
    if not destinations:
        print("WARNING: destinations.json empty, using fallback")
        # FALLBACK: hardcoded destinations (do czasu utworzenia JSON)
        destinations = [
        {
            "destination_id": "zakopane",
            "name": "Zakopane",
            "country": "Poland",
            "region_type": "mountain",
            "image_key": "destinations/zakopane_placeholder.jpg",
            "description_short": "Stolica polskich Tatr - idealna na rodzinne wypady"
        },
        {
            "destination_id": "krakow",
            "name": "Kraków",
            "country": "Poland",
            "region_type": "city",
            "image_key": "destinations/krakow_placeholder.jpg",
            "description_short": "Historyczne miasto z bogata kultura"
        },
        {
            "destination_id": "gdansk",
            "name": "Gdańsk",
            "country": "Poland",
            "region_type": "sea",
            "image_key": "destinations/gdansk_placeholder.jpg",
            "description_short": "Morskie miasto z piekna starówka"
        },
        {
            "destination_id": "wroclaw",
            "name": "Wrocław",
            "country": "Poland",
            "region_type": "city",
            "image_key": "destinations/wroclaw_placeholder.jpg",
            "description_short": "Miasto 100 mostów i krasnali"
        },
        {
            "destination_id": "kolobrzeg",
            "name": "Kołobrzeg",
            "country": "Poland",
            "region_type": "sea",
            "image_key": "destinations/kolobrzeg_placeholder.jpg",
            "description_short": "Nadmorski kurort z plazami"
        },
        {
            "destination_id": "poznan",
            "name": "Poznań",
            "country": "Poland",
            "region_type": "city",
            "image_key": "destinations/poznan_placeholder.jpg",
            "description_short": "Miasto z kultowa Starym Rynkiem"
        },
        {
            "destination_id": "bieszczady",
            "name": "Bieszczady",
            "country": "Poland",
            "region_type": "mountain",
            "image_key": "destinations/bieszczady_placeholder.jpg",
            "description_short": "Dzika przyroda i polskie gory"
        },
        {
            "destination_id": "torun",
            "name": "Toruń",
            "country": "Poland",
            "region_type": "city",
            "image_key": "destinations/torun_placeholder.jpg",
            "description_short": "Miasto piernika i gotyckie zabytki"
        },
        ]
    
    return HomeContentResponse(
        destinations=[DestinationItem(**d) for d in destinations],
        featured_count=len(destinations)
    )
