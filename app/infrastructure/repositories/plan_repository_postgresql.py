"""
Plan Repository - PostgreSQL implementation (ETAP 2).
Stores plans and version history in Supabase PostgreSQL.
"""
import uuid
import json
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.infrastructure.repositories.interfaces import IPlanRepository
from app.infrastructure.database.models import Plan, PlanVersion
from app.domain.models.plan import PlanResponse, DayPlan


class PlanPostgreSQLRepository(IPlanRepository):
    """
    PostgreSQL-based plan repository.
    
    Features:
    - CRUD operations on plans table
    - Version tracking in plan_versions table
    - Automatic snapshot creation on save
    - CASCADE delete (plan + all versions)
    """

    def __init__(self, db: Session):
        """
        Initialize with SQLAlchemy session.
        
        Args:
            db: SQLAlchemy session (from get_session() dependency)
        """
        self.db = db

    def save(self, plan: PlanResponse) -> str:
        """
        Saves plan to database and creates version snapshot.
        
        Logic:
        1. Check if plan exists (by plan_id)
        2. If exists: UPDATE plan + CREATE new version (change_type='regenerated')
        3. If new: INSERT plan + CREATE initial version (change_type='initial')
        
        Args:
            plan: PlanResponse domain model
            
        Returns:
            plan_id (str)
            
        Raises:
            SQLAlchemyError: Database operation failed
        """
        try:
            plan_id = plan.plan_id
            
            # Check if plan exists
            existing_plan = self.db.query(Plan).filter(Plan.id == uuid.UUID(plan_id)).first()
            
            if existing_plan:
                # UPDATE existing plan
                existing_plan.updated_at = datetime.utcnow()
                existing_plan.trip_metadata = self._extract_metadata(plan)
                
                # Get next version number
                max_version = self.db.query(PlanVersion).filter(
                    PlanVersion.plan_id == uuid.UUID(plan_id)
                ).count()
                next_version = max_version + 1
                
                # Create new version snapshot
                new_version = PlanVersion(
                    id=uuid.uuid4(),
                    plan_id=uuid.UUID(plan_id),
                    version_number=next_version,
                    change_type='regenerated',
                    parent_version_id=None,  # TODO: track parent when rollback is implemented
                    days_json=self._serialize_days(plan.days),
                    change_summary=f"Regenerated plan (version {next_version})"
                )
                self.db.add(new_version)
                
            else:
                # INSERT new plan
                new_plan = Plan(
                    id=uuid.UUID(plan_id),
                    location=plan.destination,
                    group_type=plan.group_type,
                    days_count=len(plan.days),
                    budget_level=plan.budget_level,
                    trip_metadata=self._extract_metadata(plan)
                )
                self.db.add(new_plan)
                
                # Create initial version snapshot
                initial_version = PlanVersion(
                    id=uuid.uuid4(),
                    plan_id=uuid.UUID(plan_id),
                    version_number=1,
                    change_type='initial',
                    parent_version_id=None,
                    days_json=self._serialize_days(plan.days),
                    change_summary=f"Initial plan created for {plan.destination}"
                )
                self.db.add(initial_version)
            
            # Commit transaction
            self.db.commit()
            
            return plan_id
            
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Failed to save plan: {str(e)}")

    def get_by_id(self, plan_id: str) -> Optional[PlanResponse]:
        """
        Retrieves plan from database and reconstructs PlanResponse.
        
        Logic:
        1. Fetch Plan row (metadata)
        2. Fetch latest PlanVersion (days_json)
        3. Reconstruct PlanResponse domain model
        
        Args:
            plan_id: UUID string
            
        Returns:
            PlanResponse or None if not found
        """
        try:
            # Fetch plan metadata
            plan = self.db.query(Plan).filter(Plan.id == uuid.UUID(plan_id)).first()
            
            if not plan:
                return None
            
            # Fetch latest version (highest version_number)
            latest_version = self.db.query(PlanVersion).filter(
                PlanVersion.plan_id == uuid.UUID(plan_id)
            ).order_by(PlanVersion.version_number.desc()).first()
            
            if not latest_version:
                # Plan exists but no versions (corrupted state)
                return None
            
            # Reconstruct PlanResponse
            return self._reconstruct_plan_response(plan, latest_version)
            
        except SQLAlchemyError as e:
            raise Exception(f"Failed to fetch plan: {str(e)}")

    def update_status(self, plan_id: str, status: str) -> bool:
        """
        Updates plan status (stored in trip_metadata JSON).
        
        Note: In ETAP 2, status can be stored in trip_metadata.status
        or we can add a dedicated 'status' column later.
        
        Args:
            plan_id: UUID string
            status: Status name (ready, pending, failed, etc.)
            
        Returns:
            True if updated, False if plan not found
        """
        try:
            plan = self.db.query(Plan).filter(Plan.id == uuid.UUID(plan_id)).first()
            
            if not plan:
                return False
            
            # Update status in metadata JSON
            if plan.trip_metadata is None:
                plan.trip_metadata = {}
            
            plan.trip_metadata['status'] = status
            plan.updated_at = datetime.utcnow()
            
            self.db.commit()
            return True
            
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Failed to update status: {str(e)}")

    def delete(self, plan_id: str) -> bool:
        """
        Deletes plan from database (CASCADE deletes all versions).
        
        Args:
            plan_id: UUID string
            
        Returns:
            True if deleted, False if not found
        """
        try:
            plan = self.db.query(Plan).filter(Plan.id == uuid.UUID(plan_id)).first()
            
            if not plan:
                return False
            
            # Delete plan (CASCADE deletes plan_versions automatically)
            self.db.delete(plan)
            self.db.commit()
            
            return True
            
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Failed to delete plan: {str(e)}")

    def get_metadata(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """
        Returns plan metadata without full days data.
        
        Args:
            plan_id: UUID string
            
        Returns:
            Metadata dict or None if not found
        """
        try:
            plan = self.db.query(Plan).filter(Plan.id == uuid.UUID(plan_id)).first()
            
            if not plan:
                return None
            
            # Get version count
            version_count = self.db.query(PlanVersion).filter(
                PlanVersion.plan_id == uuid.UUID(plan_id)
            ).count()
            
            return {
                "plan_id": str(plan.id),
                "location": plan.location,
                "group_type": plan.group_type,
                "days_count": plan.days_count,
                "budget_level": plan.budget_level,
                "created_at": plan.created_at.isoformat(),
                "updated_at": plan.updated_at.isoformat(),
                "version_count": version_count,
                "status": plan.trip_metadata.get('status', 'ready') if plan.trip_metadata else 'ready',
                **plan.trip_metadata  # Include all custom metadata
            }
            
        except SQLAlchemyError as e:
            raise Exception(f"Failed to fetch metadata: {str(e)}")

    # --- Helper methods ---

    def _extract_metadata(self, plan: PlanResponse) -> Dict[str, Any]:
        """Extracts metadata from PlanResponse for trip_metadata JSON column."""
        return {
            "destination": plan.destination,
            "group_type": plan.group_type,
            "budget_level": plan.budget_level,
            "version": plan.version,
            "status": "ready",
            # Add any custom fields from plan
        }

    def _serialize_days(self, days: list[DayPlan]) -> Dict[str, Any]:
        """Serializes days list to JSON-compatible dict."""
        return {
            "days": [day.dict() for day in days]
        }

    def _reconstruct_plan_response(self, plan: Plan, version: PlanVersion) -> PlanResponse:
        """Reconstructs PlanResponse from Plan and PlanVersion database models."""
        # Deserialize days
        days_data = version.days_json.get("days", [])
        days = [DayPlan(**day_data) for day_data in days_data]
        
        # Build PlanResponse
        return PlanResponse(
            plan_id=str(plan.id),
            destination=plan.location,
            group_type=plan.group_type,
            budget_level=plan.budget_level,
            days=days,
            version=version.version_number,
            total_cost=self._calculate_total_cost(days),
            highlights=self._extract_highlights(days)
        )

    def _calculate_total_cost(self, days: list[DayPlan]) -> float:
        """Calculates total cost from all days."""
        total = 0.0
        for day in days:
            for activity in day.activities:
                if hasattr(activity, 'cost') and activity.cost:
                    total += activity.cost
        return round(total, 2)

    def _extract_highlights(self, days: list[DayPlan]) -> list[str]:
        """Extracts top highlights from plan days."""
        highlights = []
        for day in days:
            for activity in day.activities:
                if hasattr(activity, 'name'):
                    highlights.append(activity.name)
                    if len(highlights) >= 5:
                        return highlights
        return highlights
