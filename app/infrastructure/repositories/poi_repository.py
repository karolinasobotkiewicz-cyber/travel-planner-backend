"""
POI Repository - in-memory cache z Excel (ETAP 1).
"""
from typing import List, Optional, Dict, Any
import os

from app.infrastructure.repositories.interfaces import IPOIRepository
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from app.domain.models.poi import POI


class POIRepository(IPOIRepository):
    """
    In-memory POI repository z lazy loading z Excel.
    
    ETAP 1: Wczytuje zakopane.xlsx raz, cachuje w pamięci.
    ETAP 2: PostgreSQL + Redis cache layer.
    """

    def __init__(self, excel_path: str):
        self.excel_path = excel_path
        self._cache: Optional[List[POI]] = None
        self._initialized = False

    def _load_if_needed(self, force_reload: bool = False):
        """Lazy loading - wczytaj Excel tylko raz (chyba że force_reload=True)."""
        if self._initialized and not force_reload:
            return

        if not os.path.exists(self.excel_path):
            # TODO: handle missing file gracefully
            print(f"WARNING: Excel not found: {self.excel_path}")
            self._cache = []
            self._initialized = True
            return

        # Load z Excel przez istniejący loader
        try:
            raw_pois = load_zakopane_poi(self.excel_path)
        except ImportError as e:
            # openpyxl not installed - graceful fallback
            print(f"WARNING: {str(e)}")
            print("POI Repository will return empty list until Excel loaded")
            self._cache = []
            self._initialized = True
            return

        # Convert do POI models
        self._cache = []
        for poi_dict in raw_pois:
            try:
                # POI model ma alias fields - musimy użyć by_alias=True
                poi = POI(**poi_dict)
                self._cache.append(poi)
            except Exception as e:
                # FIXME: lepszy error handling
                print(f"Failed to parse POI {poi_dict.get('ID')}: {e}")
                continue

        self._initialized = True
        print(f"POI Repository: loaded {len(self._cache)} POIs from Excel")

    def reload(self):
        """Force reload Excel data - useful after Excel file changes."""
        print("POI Repository: FORCE RELOAD triggered")
        self._initialized = False
        self._cache = None
        self._load_if_needed(force_reload=True)

    def get_all(self) -> List[POI]:
        """Zwraca wszystkie POI."""
        self._load_if_needed()
        return self._cache or []

    def get_by_id(self, poi_id: str) -> Optional[POI]:
        """Zwraca POI po ID lub None."""
        self._load_if_needed()
        
        for poi in (self._cache or []):
            if poi.id == poi_id:
                return poi
        
        return None

    def get_by_region(self, region: str) -> List[POI]:
        """Zwraca POI z danego regionu."""
        self._load_if_needed()
        
        result = []
        for poi in (self._cache or []):
            if poi.region.lower() == region.lower():
                result.append(poi)
        
        return result

    def search(self, **filters) -> List[POI]:
        """
        Wyszukuje POI po filtrach.
        
        ETAP 1: Prosty filtr po atrybutach.
        ETAP 2: Zaawansowane query z PostgreSQL.
        
        Przykłady:
        - target_group='family'
        - free_entry=True
        - min_rating=4.0
        """
        self._load_if_needed()
        
        result = []
        for poi in (self._cache or []):
            match = True
            
            # Filter by target_group
            if 'target_group' in filters:
                target = filters['target_group']
                target_groups = poi.get_target_groups()  # Use method instead of attribute
                if target not in target_groups:
                    match = False
            
            # Filter by free_entry
            if 'free_entry' in filters:
                if poi.free_entry != filters['free_entry']:
                    match = False
            
            # Filter by min_rating
            if 'min_rating' in filters:
                min_r = filters['min_rating']
                if (poi.rating or 0) < min_r:
                    match = False
            
            if match:
                result.append(poi)
        
        return result

    def reload(self):
        """Force reload z Excel - do testów."""
        self._cache = None
        self._initialized = False
        self._load_if_needed()
