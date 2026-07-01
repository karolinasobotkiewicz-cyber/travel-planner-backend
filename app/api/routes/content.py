"""
Content endpoints - destinations, home content.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List

from app.infrastructure.repositories import DestinationsRepository
from app.api.dependencies import get_destinations_repository
from app.infrastructure.storage import (
    build_destination_image_url,
    normalize_image_key,
)

router = APIRouter()


def _infer_region_type(region: str) -> str:
    """Infer region_type from region name (ETAP 1 helper)."""
    region_lower = region.lower()
    if (
        "tatry" in region_lower
        or "góry" in region_lower
        or "karkonosze" in region_lower
        or "kłodzka" in region_lower
    ):
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
    region_type: str  # mountain, sea, city, spa_region
    # api_city: dokładna wartość, którą front wysyła w location.city do /plan/preview
    # (01.07.2026 - front feedback: front potrzebuje jasnej wartości do API)
    api_city: str
    is_cluster: bool = False
    image_key: str | None  # klucz obrazka bez rozszerzenia (np. "destination_zakopane")
    image_url: str | None  # pelny URL do obrazka w Supabase Storage (11.03.2026)
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
        raw_key = dest.get("image_key", "")
        # region_type: użyj jawnego z JSON, w innym wypadku wywnioskuj z regionu
        region_type = dest.get("region_type") or _infer_region_type(
            dest.get("region", "")
        )
        # api_city: dokładna wartość do wysłania w location.city (fallback: name)
        api_city = dest.get("api_city") or dest.get("name")
        destinations.append({
            "destination_id": dest.get("id"),  # JSON ma "id", API zwraca "destination_id"
            "name": dest.get("name"),
            "country": "Poland",  # ETAP 1: hardcoded
            "region_type": region_type,
            "api_city": api_city,
            "is_cluster": bool(dest.get("is_cluster", False)),
            "image_key": normalize_image_key(raw_key),
            "image_url": build_destination_image_url(raw_key),  # 11.03.2026: Supabase Storage
            "description_short": dest.get("description_short", "")
        })
    
    # Fallback if JSON empty (graceful handling)
    if not destinations:
        print("WARNING: destinations.json empty, using fallback")
        # FALLBACK: hardcoded destinations (do czasu utworzenia JSON)
        fallback_destinations = [
            {
                "destination_id": "zakopane",
                "name": "Zakopane",
                "country": "Poland",
                "region_type": "mountain",
                "image_key": "destination_zakopane",
                "description_short": "Stolica polskich Tatr - idealna na rodzinne wypady"
            },
            {
                "destination_id": "krakow",
                "name": "Kraków",
                "country": "Poland",
                "region_type": "city",
                "image_key": "destination_krakow",
                "description_short": "Historyczne miasto z bogata kultura"
            },
            {
                "destination_id": "gdansk",
                "name": "Gdańsk",
                "country": "Poland",
                "region_type": "sea",
                "image_key": "destination_gdansk",
                "description_short": "Morskie miasto z piekna starówka"
            },
            {
                "destination_id": "wroclaw",
                "name": "Wrocław",
                "country": "Poland",
                "region_type": "city",
                "image_key": "destination_wroclaw",
                "description_short": "Miasto 100 mostów i krasnali"
            },
            {
                "destination_id": "kolobrzeg",
                "name": "Kołobrzeg",
                "country": "Poland",
                "region_type": "sea",
                "image_key": "destination_kolobrzeg",
                "description_short": "Nadmorski kurort z plazami"
            },
            {
                "destination_id": "poznan",
                "name": "Poznań",
                "country": "Poland",
                "region_type": "city",
                "image_key": "destination_poznan",
                "description_short": "Miasto z kultowa Starym Rynkiem"
            },
            {
                "destination_id": "bieszczady",
                "name": "Bieszczady",
                "country": "Poland",
                "region_type": "mountain",
                "image_key": "destination_bieszczady",
                "description_short": "Dzika przyroda i polskie gory"
            },
            {
                "destination_id": "torun",
                "name": "Toruń",
                "country": "Poland",
                "region_type": "city",
                "image_key": "destination_torun",
                "description_short": "Miasto piernika i gotyckie zabytki"
            },
        ]
        
        # Add image_url + api_city to fallback destinations
        destinations = []
        for dest in fallback_destinations:
            dest_with_url = dest.copy()
            dest_with_url["api_city"] = dest.get("name")
            dest_with_url["is_cluster"] = False
            dest_with_url["image_url"] = build_destination_image_url(dest["image_key"])
            dest_with_url["image_key"] = normalize_image_key(dest["image_key"])
            destinations.append(dest_with_url)
    
    return HomeContentResponse(
        destinations=[DestinationItem(**d) for d in destinations],
        featured_count=len(destinations)
    )
