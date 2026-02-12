"""
Plan Version Repository - manages plan version history and rollback (ETAP 2).
"""
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.infrastructure.database.models import Plan, PlanVersion


class PlanVersionRepository:
    """
    Repository for managing plan version history.
    
    Features:
    - List all versions of a plan
    - Get specific version by number
    - Rollback to previous version
    - Track version lineage (parent_version_id)
    """

    def __init__(self, db: Session):
        """
        Initialize with SQLAlchemy session.
        
        Args:
            db: SQLAlchemy session (from get_session() dependency)
        """
        self.db = db

    def list_versions(self, plan_id: str) -> List[Dict[str, Any]]:
        """
        Lists all versions of a plan (metadata only, no full days_json).
        
        Args:
            plan_id: UUID string
            
        Returns:
            List of version metadata dicts, sorted by version_number DESC
            
        Example response:
        [
            {
                "version_number": 3,
                "created_at": "2026-02-12T10:30:00",
                "change_type": "regenerated",
                "change_summary": "Regenerated plan (version 3)"
            },
            ...
        ]
        """
        try:
            versions = self.db.query(PlanVersion).filter(
                PlanVersion.plan_id == uuid.UUID(plan_id)
            ).order_by(PlanVersion.version_number.desc()).all()
            
            return [
                {
                    "id": str(v.id),
                    "version_number": v.version_number,
                    "created_at": v.created_at.isoformat(),
                    "change_type": v.change_type,
                    "change_summary": v.change_summary,
                    "parent_version_id": str(v.parent_version_id) if v.parent_version_id else None,
                }
                for v in versions
            ]
            
        except SQLAlchemyError as e:
            raise Exception(f"Failed to list versions: {str(e)}")

    def get_version(self, plan_id: str, version_number: int) -> Optional[Dict[str, Any]]:
        """
        Gets full data for a specific version (including days_json).
        
        Args:
            plan_id: UUID string
            version_number: Version number to retrieve
            
        Returns:
            Full version dict with days_json, or None if not found
        """
        try:
            version = self.db.query(PlanVersion).filter(
                PlanVersion.plan_id == uuid.UUID(plan_id),
                PlanVersion.version_number == version_number
            ).first()
            
            if not version:
                return None
            
            return {
                "id": str(version.id),
                "version_number": version.version_number,
                "created_at": version.created_at.isoformat(),
                "change_type": version.change_type,
                "change_summary": version.change_summary,
                "parent_version_id": str(version.parent_version_id) if version.parent_version_id else None,
                "days_json": version.days_json,  # Full snapshot
            }
            
        except SQLAlchemyError as e:
            raise Exception(f"Failed to get version: {str(e)}")

    def rollback(self, plan_id: str, target_version: int) -> bool:
        """
        Rolls back plan to a previous version.
        
        Logic:
        1. Fetch target version snapshot
        2. Create new version with change_type='rollback'
        3. Set parent_version_id to current latest version
        4. Copy days_json from target version to new version
        
        This creates a new version (doesn't delete newer versions).
        Example: If plan has versions [1, 2, 3] and you rollback to 2,
        result is [1, 2, 3, 4] where 4 is copy of 2.
        
        Args:
            plan_id: UUID string
            target_version: Version number to rollback to
            
        Returns:
            True if successful, False if target version not found
            
        Raises:
            Exception: Database operation failed
        """
        try:
            # Fetch target version
            target = self.db.query(PlanVersion).filter(
                PlanVersion.plan_id == uuid.UUID(plan_id),
                PlanVersion.version_number == target_version
            ).first()
            
            if not target:
                return False
            
            # Get current latest version (for parent_version_id)
            latest = self.db.query(PlanVersion).filter(
                PlanVersion.plan_id == uuid.UUID(plan_id)
            ).order_by(PlanVersion.version_number.desc()).first()
            
            # Calculate next version number
            next_version_number = latest.version_number + 1
            
            # Create rollback version
            rollback_version = PlanVersion(
                id=uuid.uuid4(),
                plan_id=uuid.UUID(plan_id),
                version_number=next_version_number,
                change_type='rollback',
                parent_version_id=latest.id,  # Track lineage
                days_json=target.days_json,  # Copy snapshot from target
                change_summary=f"Rolled back to version {target_version}"
            )
            self.db.add(rollback_version)
            
            # Update Plan.updated_at
            plan = self.db.query(Plan).filter(Plan.id == uuid.UUID(plan_id)).first()
            if plan:
                plan.updated_at = datetime.utcnow()
            
            self.db.commit()
            return True
            
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Failed to rollback: {str(e)}")

    def delete_version(self, plan_id: str, version_number: int) -> bool:
        """
        Deletes a specific version (NOT RECOMMENDED in production).
        
        Warning: Deleting versions can break version lineage.
        Only use this for cleanup/maintenance.
        
        Args:
            plan_id: UUID string
            version_number: Version to delete
            
        Returns:
            True if deleted, False if not found
        """
        try:
            version = self.db.query(PlanVersion).filter(
                PlanVersion.plan_id == uuid.UUID(plan_id),
                PlanVersion.version_number == version_number
            ).first()
            
            if not version:
                return False
            
            self.db.delete(version)
            self.db.commit()
            return True
            
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Failed to delete version: {str(e)}")

    def get_version_diff(self, plan_id: str, from_version: int, to_version: int) -> Dict[str, Any]:
        """
        Compares two versions and returns diff (basic implementation).
        
        Note: This is a simple comparison. For visual diff UI (highlighted changes),
        see DiffGenerator in Phase 3.
        
        Args:
            plan_id: UUID string
            from_version: Older version number
            to_version: Newer version number
            
        Returns:
            Basic diff dict with added/removed activities count
        """
        try:
            v_from = self.db.query(PlanVersion).filter(
                PlanVersion.plan_id == uuid.UUID(plan_id),
                PlanVersion.version_number == from_version
            ).first()
            
            v_to = self.db.query(PlanVersion).filter(
                PlanVersion.plan_id == uuid.UUID(plan_id),
                PlanVersion.version_number == to_version
            ).first()
            
            if not v_from or not v_to:
                return {"error": "Version not found"}
            
            # Basic comparison (count activities)
            from_days = v_from.days_json.get("days", [])
            to_days = v_to.days_json.get("days", [])
            
            from_activity_count = sum(len(day.get("activities", [])) for day in from_days)
            to_activity_count = sum(len(day.get("activities", [])) for day in to_days)
            
            return {
                "from_version": from_version,
                "to_version": to_version,
                "days_changed": len(from_days) != len(to_days),
                "activity_count_diff": to_activity_count - from_activity_count,
                "summary": f"Version {to_version} has {abs(to_activity_count - from_activity_count)} " +
                          f"{'more' if to_activity_count > from_activity_count else 'fewer'} activities"
            }
            
        except SQLAlchemyError as e:
            raise Exception(f"Failed to compare versions: {str(e)}")
