"""
Destinations Repository - JSON file (ETAP 1).
"""
import json
import os
from typing import List, Dict, Any, Optional

from app.infrastructure.repositories.interfaces import IDestinationsRepository


class DestinationsRepository(IDestinationsRepository):
    """
    JSON-based destinations repository.
    
    ETAP 1: Wczytuje z data/destinations.json (static content).
    ETAP 2: PostgreSQL destinations table z CMS.
    """

    def __init__(self, json_path: str):
        self.json_path = json_path
        self._cache: Optional[List[Dict[str, Any]]] = None
        self._initialized = False

    def _load_if_needed(self):
        """Lazy loading z JSON."""
        if self._initialized:
            return

        if not os.path.exists(self.json_path):
            # FIXME: handle missing file
            print(f"WARNING: JSON not found: {self.json_path}")
            self._cache = []
            self._initialized = True
            return

        with open(self.json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self._cache = data.get("destinations", [])

        self._initialized = True
        print(
            f"Destinations Repository: loaded {len(self._cache)} "
            f"destinations from JSON"
        )

    def get_all(self) -> List[Dict[str, Any]]:
        """Zwraca wszystkie destinations dla home screen."""
        self._load_if_needed()
        return self._cache or []

    def get_by_id(self, destination_id: str) -> Optional[Dict[str, Any]]:
        """Zwraca destination po ID."""
        self._load_if_needed()
        
        for dest in (self._cache or []):
            # JSON używa "id", API przekazuje "destination_id"
            if dest.get("id") == destination_id:
                return dest
        
        return None

    def reload(self):
        """Force reload z JSON - do testów."""
        self._cache = None
        self._initialized = False
        self._load_if_needed()
