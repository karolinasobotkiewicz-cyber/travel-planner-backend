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

    def save(self, plan: PlanResponse, user_id: Optional[uuid.UUID] = None) -> str:
        """
        Saves plan to database and creates version snapshot.
        
        Logic:
        1. Check if plan exists (by plan_id)
        2. If exists: UPDATE plan + CREATE new version (change_type='regenerated')
        3. If new: INSERT plan + CREATE initial version (change_type='initial')
        
        Args:
            plan: PlanResponse domain model
            user_id: Optional UUID of authenticated user (ETAP 2)
            
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
                # Link to user if provided and not already linked
                if user_id and not existing_plan.user_id:
                    existing_plan.user_id = user_id
                
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
                # Note: PlanResponse doesn't have location/group/budget fields
                # These would need to come from TripInput (future improvement)
                new_plan = Plan(
                    id=uuid.UUID(plan_id),
                    location="Unknown",  # TODO: pass from TripInput
                    group_type="unknown",  # TODO: pass from TripInput
                    days_count=len(plan.days),
                    budget_level=2,  # TODO: pass from TripInput
                    user_id=user_id,  # ETAP 2: Link plan to authenticated user
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
                    change_summary=f"Initial plan created (version 1)"
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

    def get_by_user(self, user_id: uuid.UUID) -> list[PlanResponse]:
        """
        Gets all plans for a specific user (ETAP 2 - /my-plans endpoint).
        
        Args:
            user_id: UUID of authenticated user
            
        Returns:
            List of PlanResponse objects (reconstructed from DB)
        """
        try:
            # Fetch all plans for this user
            plans = self.db.query(Plan).filter(
                Plan.user_id == user_id
            ).order_by(Plan.created_at.desc()).all()
            
            result = []
            for plan in plans:
                # Fetch latest version for each plan
                latest_version = self.db.query(PlanVersion).filter(
                    PlanVersion.plan_id == plan.id
                ).order_by(PlanVersion.version_number.desc()).first()
                
                if latest_version:
                    plan_response = self._reconstruct_plan_response(plan, latest_version)
                    result.append(plan_response)
            
            return result
            
        except SQLAlchemyError as e:
            raise Exception(f"Failed to fetch user plans: {str(e)}")

    def transfer_ownership(self, guest_id: str, user_id: uuid.UUID) -> int:
        """
        Transfers guest plans to authenticated user (ETAP 2 - /claim-guest-plans endpoint).
        
        Logic:
        - Guest plans have user_id = NULL (created before auth)
        - We match by session or guest identifier stored in trip_metadata
        - Transfer all matching plans to authenticated user_id
        
        Args:
            guest_id: Guest identifier (UUID string from localStorage)
            user_id: Authenticated user UUID
            
        Returns:
            Count of transferred plans
        """
        try:
            # Find all guest plans where user_id is NULL
            # In current implementation, anonymous users create plans with user_id=NULL
            # We could add guest_id tracking in trip_metadata for precise matching
            # For now: transfer all NULL user_id plans (assumes single-device guest session)
            
            # More precise: find plans where trip_metadata.guest_id matches
            # But ETAP 1 didn't store guest_id, so we'd need to update /preview endpoint first
            
            # Simpler approach for now: transfer ALL NULL plans created recently
            # This assumes guest creates plans, then immediately logs in and claims them
            
            # Query plans with NULL user_id
            guest_plans = self.db.query(Plan).filter(
                Plan.user_id == None
            ).all()
            
            # Filter by guest_id in trip_metadata (if stored)
            # If not stored, transfer all NULL plans (fallback for backward compatibility)
            matching_plans = []
            for plan in guest_plans:
                # Check if guest_id stored in metadata
                if plan.trip_metadata and plan.trip_metadata.get('guest_id') == guest_id:
                    matching_plans.append(plan)
                elif not plan.trip_metadata or 'guest_id' not in plan.trip_metadata:
                    # Fallback: include all NULL plans without guest_id tracking
                    matching_plans.append(plan)
            
            # Transfer ownership
            transferred_count = 0
            for plan in matching_plans:
                plan.user_id = user_id
                plan.updated_at = datetime.utcnow()
                transferred_count += 1
            
            self.db.commit()
            return transferred_count
            
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Failed to transfer ownership: {str(e)}")

    # --- Helper methods ---

    def _extract_metadata(self, plan: PlanResponse) -> Dict[str, Any]:
        """Extracts metadata from PlanResponse for trip_metadata JSON column."""
        # PlanResponse only has plan_id, version, days
        # Store available data, rest will come from TripInput in future
        return {
            "version": plan.version,
            "days_count": len(plan.days),
            "status": "ready",
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
        
        # Build PlanResponse (only contains plan_id, version, days)
        return PlanResponse(
            plan_id=str(plan.id),
            version=version.version_number,
            days=days
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
