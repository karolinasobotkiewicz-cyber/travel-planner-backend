"""
Plan Repository - PostgreSQL implementation (ETAP 2).

This module now imports from plan_repository_postgresql.
The in-memory implementation is backed up in plan_repository_inmemory.py.
"""

# Import PostgreSQL implementation as the default PlanRepository
from app.infrastructure.repositories.plan_repository_postgresql import (
    PlanPostgreSQLRepository as PlanRepository
)

__all__ = ["PlanRepository"]
