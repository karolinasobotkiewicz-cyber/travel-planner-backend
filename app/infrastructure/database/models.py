"""
SQLAlchemy ORM models for ETAP 2.
Defines database schema for plans and plan_versions tables.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, JSON, UniqueConstraint, Numeric, text
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
    
    # User reference (ETAP 2) - nullable for backward compatibility
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
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
    user = relationship("User", back_populates="plans")
    versions = relationship("PlanVersion", back_populates="plan", cascade="all, delete-orphan")
    payment_sessions = relationship("PaymentSession", back_populates="plan")
    transactions = relationship("Transaction", back_populates="plan")
    
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


# ==========================================
# ETAP 2: AUTH & PAYMENT MODELS
# ==========================================


class User(Base):
    """
    Users table - linked to Supabase auth.
    
    Stores local user data synced with Supabase authentication.
    Auto-created on first API request after Supabase signup.
    """
    __tablename__ = "users"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    
    # Supabase auth reference
    supabase_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    
    # User info
    email = Column(String(255), nullable=False, unique=True, index=True)
    display_name = Column(String(255), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    plans = relationship("Plan", back_populates="user")
    payment_sessions = relationship("PaymentSession", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"


class PaymentSession(Base):
    """
    Payment sessions table - tracks Stripe Checkout sessions.
    
    Each session represents a payment attempt for a travel plan.
    Status transitions: pending → completed/expired/failed
    """
    __tablename__ = "payment_sessions"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    
    # Foreign keys
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Stripe reference
    stripe_session_id = Column(String(255), nullable=False, unique=True, index=True)
    
    # Payment details
    amount = Column(Numeric(10, 2), nullable=False)  # 39.99
    currency = Column(String(3), nullable=False, server_default='PLN')
    
    # Status tracking
    status = Column(String(50), nullable=False, index=True)  # pending, completed, expired, failed
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)  # 24h from creation
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="payment_sessions")
    plan = relationship("Plan", back_populates="payment_sessions")
    transactions = relationship("Transaction", back_populates="payment_session", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<PaymentSession(id={self.id}, stripe_session_id={self.stripe_session_id}, status={self.status})>"


class Transaction(Base):
    """
    Transactions table - audit trail of completed payments.
    
    Immutable record of successful payments.
    Created by Stripe webhook on checkout.session.completed event.
    """
    __tablename__ = "transactions"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    
    # Foreign keys
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_session_id = Column(UUID(as_uuid=True), ForeignKey("payment_sessions.id", ondelete="CASCADE"), nullable=False)
    
    # Stripe reference
    stripe_payment_intent = Column(String(255), nullable=False, unique=True, index=True)
    
    # Payment details
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False, server_default='PLN')
    
    # Status
    status = Column(String(50), nullable=False)  # succeeded, failed, refunded
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="transactions")
    plan = relationship("Plan", back_populates="transactions")
    payment_session = relationship("PaymentSession", back_populates="transactions")
    
    def __repr__(self):
        return f"<Transaction(id={self.id}, amount={self.amount}, status={self.status})>"
