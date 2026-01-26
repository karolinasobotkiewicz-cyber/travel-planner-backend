"""
Plan Repository - in-memory storage (ETAP 1).
"""
from typing import Dict, Optional, Any
from datetime import datetime

from app.infrastructure.repositories.interfaces import IPlanRepository
from app.domain.models.plan import PlanResponse


class PlanRepository(IPlanRepository):
    """
    In-memory plan storage.
    
    ETAP 1: Dict storage w pamięci (zgubi się po restarcie).
    ETAP 2: PostgreSQL persistence.
    
    Structure:
    {
        "plan_id": {
            "plan": PlanResponse,
            "status": "ready",
            "created_at": "2026-01-26T10:30:00",
            "updated_at": "2026-01-26T10:35:00",
            "metadata": {...}
        }
    }
    """

    def __init__(self):
        self._storage: Dict[str, Dict[str, Any]] = {}

    def save(self, plan: PlanResponse) -> str:
        """
        Zapisuje plan i zwraca plan_id.
        
        ETAP 2: INSERT INTO plans lub UPDATE if exists.
        """
        plan_id = plan.plan_id
        now = datetime.utcnow().isoformat()

        # Check if exists
        if plan_id in self._storage:
            # Update existing
            self._storage[plan_id]["plan"] = plan
            self._storage[plan_id]["updated_at"] = now
        else:
            # Create new
            self._storage[plan_id] = {
                "plan": plan,
                "status": "ready",
                "created_at": now,
                "updated_at": now,
                "metadata": {
                    "days_count": len(plan.days),
                    "version": plan.version,
                }
            }

        return plan_id

    def get_by_id(self, plan_id: str) -> Optional[PlanResponse]:
        """Zwraca plan po ID lub None."""
        if plan_id not in self._storage:
            return None
        
        return self._storage[plan_id]["plan"]

    def update_status(self, plan_id: str, status: str) -> bool:
        """
        Aktualizuje status planu.
        
        Statusy: pending, ready, failed, payment_required
        """
        if plan_id not in self._storage:
            return False
        
        self._storage[plan_id]["status"] = status
        self._storage[plan_id]["updated_at"] = (
            datetime.utcnow().isoformat()
        )
        
        return True

    def delete(self, plan_id: str) -> bool:
        """
        Usuwa plan z storage.
        
        ETAP 2: Soft delete (deleted_at timestamp).
        """
        if plan_id not in self._storage:
            return False
        
        del self._storage[plan_id]
        return True

    def get_metadata(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """
        Zwraca metadata planu bez pełnych danych.
        
        Używane do GET /plan/{id}/status.
        """
        if plan_id not in self._storage:
            return None
        
        entry = self._storage[plan_id]
        
        return {
            "plan_id": plan_id,
            "status": entry["status"],
            "created_at": entry["created_at"],
            "updated_at": entry["updated_at"],
            "metadata": entry["metadata"],
        }

    def count(self) -> int:
        """Zwraca liczbę planów w storage - do testów."""
        return len(self._storage)

    def clear(self):
        """Czyści storage - do testów."""
        self._storage.clear()
