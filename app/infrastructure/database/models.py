"""
SQLAlchemy ORM models for ETAP 2.
Defines database schema for plans and plan_versions tables.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

# Base class for all models
Base = declarative_base()


class Plan(Base):
    """
    Main plans table - stores high-level plan metadata.
    
    Each plan represents a user's trip (1-7 days).
    Actual day-by-day itineraries are stored in plan_versions table.
    """
    __tablename__ = "plans"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Trip metadata
    location = Column(String(255), nullable=False, index=True)
    group_type = Column(String(50), nullable=True)  # family_kids, couples, seniors, etc.
    days_count = Column(Integer, nullable=False)
    budget_level = Column(Integer, nullable=True)  # 1=cheap, 2=standard, 3+=high
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Additional metadata (JSON field for flexibility)
    # Note: 'metadata' is SQLAlchemy reserved, so using 'trip_metadata'
    trip_metadata = Column(JSON, nullable=True)
    
    # Relationships
    versions = relationship("PlanVersion", back_populates="plan", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Plan(id={self.id}, location={self.location}, days={self.days_count})>"


class PlanVersion(Base):
    """
    Plan versions table - stores snapshots of plan changes.
    
    Each time a plan is generated, edited, or rolled back,
    a new version is saved. This enables:
    - History tracking
    - Rollback functionality
    - Audit trail
    """
    __tablename__ = "plan_versions"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign key to plans table
    plan_id = Column(UUID(as_uuid=True), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Version metadata
    version_number = Column(Integer, nullable=False)  # Auto-increment per plan
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    change_type = Column(String(50), nullable=False)  # 'initial', 'regenerated', 'edited', 'rollback'
    
    # Parent version (for rollback tracking)
    parent_version_id = Column(UUID(as_uuid=True), ForeignKey("plan_versions.id"), nullable=True)
    
    # Full plan snapshot (JSON)
    # Stores complete DayPlan[] structure from Etap 1
    days_json = Column(JSON, nullable=False)
    
    # Optional: Summary of changes (for diff in Phase 3)
    change_summary = Column(Text, nullable=True)
    
    # Relationships
    plan = relationship("Plan", back_populates="versions")
    parent_version = relationship("PlanVersion", remote_side=[id], backref="child_versions")
    
    # Table constraints
    __table_args__ = (
        UniqueConstraint('plan_id', 'version_number', name='uq_plan_version'),
    )
    
    def __repr__(self):
        return f"<PlanVersion(id={self.id}, plan_id={self.plan_id}, version={self.version_number}, type={self.change_type})>"
