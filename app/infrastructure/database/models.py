"""
SQLAlchemy ORM models for ETAP 2.
Defines database schema for plans and plan_versions tables.
"""

import uuid
from datetime import datetime
from decimal import Decimal
import sqlalchemy as sa
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, JSON, UniqueConstraint, Numeric, text, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

# Base class for all models
Base = declarative_base()


class Plan(Base):
    """
    Main plans table - stores high-level plan metadata.
    
    Each plan represents a user's trip (1-7 days).
    Actual day-by-day itineraries are stored in plan_versions table.
    
    Ownership:
    - Authenticated users: user_id is set, guest_id is NULL
    - Guest users: guest_id is set, user_id is NULL
    - One of user_id OR guest_id must be present (check constraint)
    """
    __tablename__ = "plans"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Owner reference (ETAP 2 - Guest Support)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    guest_id = Column(String(255), nullable=True, index=True)  # UUID from frontend localStorage
    
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
    
    # Table constraints
    __table_args__ = (
        # Ensure either user_id OR guest_id is present
        sa.CheckConstraint('user_id IS NOT NULL OR guest_id IS NOT NULL', name='ck_plans_owner_id'),
    )
    
    def __repr__(self):
        owner = f"user_id={self.user_id}" if self.user_id else f"guest_id={self.guest_id}"
        return f"<Plan(id={self.id}, {owner}, location={self.location}, days={self.days_count})>"


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
    
    Ownership:
    - Authenticated users: user_id is set, guest_id is NULL
    - Guest users: guest_id is set, user_id is NULL
    - One of user_id OR guest_id must be present (check constraint)
    """
    __tablename__ = "payment_sessions"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    
    # Owner reference (ETAP 2 - Guest Support)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    guest_id = Column(String(255), nullable=True, index=True)  # UUID from frontend localStorage
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
    
    # Table constraints
    __table_args__ = (
        # Ensure either user_id OR guest_id is present
        sa.CheckConstraint('user_id IS NOT NULL OR guest_id IS NOT NULL', name='ck_payment_sessions_owner_id'),
    )
    
    def __repr__(self):
        owner = f"user={self.user_id}" if self.user_id else f"guest={self.guest_id}"
        return f"<PaymentSession(id={self.id}, {owner}, stripe={self.stripe_session_id}, status={self.status})>"


class Transaction(Base):
    """
    Transactions table - audit trail of completed payments.
    
    Immutable record of successful payments.
    Created by Stripe webhook on checkout.session.completed event.
    
    **GUEST SUPPORT:**
    - user_id: UUID FK for authenticated users (nullable)
    - guest_id: VARCHAR UUID for guest users (nullable)
    - CHECK: (user_id IS NOT NULL OR guest_id IS NOT NULL)
    """
    __tablename__ = "transactions"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    
    # Foreign keys (BOTH nullable - one must be set)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    guest_id = Column(String(255), nullable=True, index=True)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_session_id = Column(UUID(as_uuid=True), ForeignKey("payment_sessions.id", ondelete="CASCADE"), nullable=False)
    
    # Check constraint: user_id XOR guest_id
    __table_args__ = (
        CheckConstraint(
            "(user_id IS NOT NULL AND guest_id IS NULL) OR (user_id IS NULL AND guest_id IS NOT NULL)",
            name="transactions_owner_check"
        ),
    )
    
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


# ==========================================
# ETAP 3: MULTI-CITY POI MODELS
# ==========================================


class RestaurantDB(Base):
    """
    Restaurants table - dining places across 15 cities (ETAP 3).
    
    Static reference data loaded from Planer - restauracje.xlsx.
    310 restaurants (filtered to ~250 after meal_type validation).
    
    Used by meal optimizer for lunch/dinner selection.
    Separate from POI for specialized filtering by meal_type.
    """
    __tablename__ = "restaurants"
    
    # Primary key
    id = Column(String(100), primary_key=True)  # UUID generated from name+city+lat
    
    # Core identity
    name = Column(String(255), nullable=False, index=True)
    city = Column(String(100), nullable=False, index=True)
    region = Column(String(100), nullable=True)
    
    # Location
    lat = Column(Numeric(10, 7), nullable=False)  # 49.2969123
    lng = Column(Numeric(10, 7), nullable=False)  # 19.9489456
    address = Column(Text, nullable=True)
    
    # CRITICAL: meal type for optimizer
    meal_type = Column(String(10), nullable=False, index=True)  # 'lunch' or 'dinner'
    cuisine_type = Column(String(100), nullable=True)
    place_type = Column(String(100), nullable=True)
    
    # Timing
    visit_duration_min = Column(Integer, nullable=False, server_default='60')
    visit_duration_max = Column(Integer, nullable=False, server_default='90')
    opening_hours = Column(JSON, nullable=True)  # {'mon': '11:00-22:00', ...}
    opening_hours_seasonal = Column(JSON, nullable=True)  # [{'season': 'summer', ...}]
    
    # Pricing
    price_level = Column(Integer, nullable=False, server_default='2')  # 1-4
    avg_meal_cost = Column(Integer, nullable=False, server_default='50')  # PLN
    
    # Characteristics
    atmosphere = Column(String(100), nullable=True)
    space = Column(String(50), nullable=True)  # indoor/outdoor/both
    reservations_required = Column(sa.Boolean, nullable=False, server_default='false')
    
    # Target group (stored as JSON array)
    target_group = Column(JSON, nullable=True)  # ['family_kids', 'couple']
    children_friendly = Column(sa.Boolean, nullable=False, server_default='true')
    
    # Quality signals
    popularity_score = Column(Numeric(4, 2), nullable=False, server_default='0.0')  # 0.00-10.00
    rating = Column(Numeric(3, 2), nullable=True)  # 0.00-5.00
    must_try = Column(sa.Boolean, nullable=False, server_default='false')
    
    # Parking
    parking_name = Column(String(255), nullable=True)
    parking_lat = Column(Numeric(10, 7), nullable=True)
    parking_lng = Column(Numeric(10, 7), nullable=True)
    parking_walk_time_min = Column(Integer, nullable=False, server_default='0')
    
    # Metadata
    pro_tip = Column(Text, nullable=True)
    image_key = Column(String(255), nullable=True)
    link_website = Column(Text, nullable=True)
    link_menu = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        sa.Index('idx_restaurants_city_meal_type', 'city', 'meal_type'),
        sa.Index('idx_restaurants_location', 'lat', 'lng'),
    )
    
    def __repr__(self):
        return f"<RestaurantDB(id={self.id}, name={self.name}, city={self.city}, meal_type={self.meal_type})>"


class TrailDB(Base):
    """
    Trails table - mountain hiking trails across 3 regions (ETAP 3).
    
    Static reference data loaded from Planer - szlaki.xlsx.
    37 trails (Tatry, Kotlina Kłodzka, Karkonosze).
    
    Used by hiking optimizer for family_kids and adventure groups.
    Separate from POI for specialized filtering by difficulty/exposure.
    """
    __tablename__ = "trails"
    
    # Primary key
    id = Column(String(100), primary_key=True)  # UUID generated from trail_name+region+start_lat
    
    # Core identity
    trail_name = Column(String(255), nullable=False, index=True)
    peak_name = Column(String(255), nullable=True)
    region = Column(String(100), nullable=False, index=True)  # Tatry, Kotlina Kłodzka, Karkonosze
    
    # Trail characteristics
    trail_color = Column(String(50), nullable=True)  # red, blue, green, yellow, black
    difficulty_level = Column(String(20), nullable=False, index=True)  # easy, moderate, hard, extreme
    length_km = Column(Numeric(6, 2), nullable=False, server_default='0.0')
    elevation_gain_m = Column(Integer, nullable=False, server_default='0')
    
    # Timing
    time_min = Column(Integer, nullable=False, server_default='120')  # minutes
    time_max = Column(Integer, nullable=False, server_default='180')  # minutes
    best_season = Column(String(100), nullable=True)
    
    # CRITICAL: safety & filtering
    family_friendly = Column(sa.Boolean, nullable=False, index=True)  # FILTER by this
    exposure_level = Column(String(20), nullable=False, server_default='low')  # low, medium, high, extreme
    weather_dependency = Column(String(20), nullable=False, server_default='medium')  # low, medium, high
    technical_difficulty = Column(String(50), nullable=True)
    
    # Location (start point)
    start_point_name = Column(String(255), nullable=True)
    start_lat = Column(Numeric(10, 7), nullable=False)
    start_lng = Column(Numeric(10, 7), nullable=False)
    start_elevation_m = Column(Integer, nullable=False, server_default='0')
    end_lat = Column(Numeric(10, 7), nullable=True)
    end_lng = Column(Numeric(10, 7), nullable=True)
    
    # Target group (stored as JSON array)
    target_group = Column(JSON, nullable=True)  # ['family_kids', 'adventure', 'nature_lovers']
    children_min_age = Column(Integer, nullable=False, server_default='0')
    
    # Parking & access
    parking_name = Column(String(255), nullable=True)
    parking_lat = Column(Numeric(10, 7), nullable=True)
    parking_lng = Column(Numeric(10, 7), nullable=True)
    parking_walk_time_min = Column(Integer, nullable=False, server_default='0')
    parking_type = Column(String(50), nullable=True)  # free/paid
    parking_cost = Column(Integer, nullable=False, server_default='0')
    
    # Description
    description_short = Column(Text, nullable=True)
    description_long = Column(Text, nullable=True)
    highlights = Column(Text, nullable=True)
    pro_tip = Column(Text, nullable=True)
    
    # Scoring (internal)
    popularity_score = Column(Numeric(4, 2), nullable=False, server_default='0.0')  # 0.00-10.00
    scenic_score = Column(Numeric(4, 2), nullable=False, server_default='0.0')  # 0.00-10.00
    must_do = Column(sa.Boolean, nullable=False, server_default='false')
    
    # Metadata
    image_key = Column(String(255), nullable=True)
    link_map = Column(Text, nullable=True)
    link_description = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        sa.Index('idx_trails_region_difficulty', 'region', 'difficulty_level'),
        sa.Index('idx_trails_family_friendly', 'family_friendly'),
        sa.Index('idx_trails_location', 'start_lat', 'start_lng'),
    )
    
    def __repr__(self):
        return f"<TrailDB(id={self.id}, trail_name={self.trail_name}, region={self.region}, difficulty={self.difficulty_level})>"
