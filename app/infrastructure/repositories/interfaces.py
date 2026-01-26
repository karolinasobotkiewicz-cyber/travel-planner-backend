"""
Repository interfaces - abstract base classes.
Przygotowane pod PostgreSQL w ETAP 2, na razie in-memory.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from app.domain.models.poi import POI
from app.domain.models.plan import PlanResponse


class IPOIRepository(ABC):
    """
    Interface dla POI repository.
    
    ETAP 1: In-memory cache z Excel
    ETAP 2: PostgreSQL + cache layer
    """

    @abstractmethod
    def get_all(self) -> List[POI]:
        """Zwraca wszystkie POI."""
        pass

    @abstractmethod
    def get_by_id(self, poi_id: str) -> Optional[POI]:
        """Zwraca POI po ID lub None."""
        pass

    @abstractmethod
    def get_by_region(self, region: str) -> List[POI]:
        """Zwraca POI z danego regionu."""
        pass

    @abstractmethod
    def search(self, **filters) -> List[POI]:
        """
        Wyszukuje POI po filtrach.
        
        Przykłady:
        - target_group='family'
        - free_entry=True
        - rating__gte=4.0
        """
        pass


class IPlanRepository(ABC):
    """
    Interface dla Plan repository.
    
    ETAP 1: In-memory dict storage
    ETAP 2: PostgreSQL z plan_id jako PK
    """

    @abstractmethod
    def save(self, plan: PlanResponse) -> str:
        """
        Zapisuje plan i zwraca plan_id.
        
        ETAP 2: INSERT INTO plans lub UPDATE if exists
        """
        pass

    @abstractmethod
    def get_by_id(self, plan_id: str) -> Optional[PlanResponse]:
        """Zwraca plan po ID lub None."""
        pass

    @abstractmethod
    def update_status(self, plan_id: str, status: str) -> bool:
        """
        Aktualizuje status planu.
        
        Statusy: pending, ready, failed, payment_required
        """
        pass

    @abstractmethod
    def delete(self, plan_id: str) -> bool:
        """Usuwa plan (soft delete w ETAP 2)."""
        pass

    @abstractmethod
    def get_metadata(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """
        Zwraca metadata planu bez pełnych danych.
        
        Używane do GET /plan/{id}/status
        """
        pass


class IDestinationsRepository(ABC):
    """
    Interface dla Destinations repository.
    
    ETAP 1: JSON file
    ETAP 2: PostgreSQL destinations table
    """

    @abstractmethod
    def get_all(self) -> List[Dict[str, Any]]:
        """Zwraca wszystkie destinations dla home screen."""
        pass

    @abstractmethod
    def get_by_id(self, destination_id: str) -> Optional[Dict[str, Any]]:
        """Zwraca destination po ID."""
        pass
