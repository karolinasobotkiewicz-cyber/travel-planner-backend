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

    def save(self, plan: PlanResponse, user_id: Optional[uuid.UUID] = None, guest_id: Optional[str] = None, trip_input: Optional[Any] = None) -> str:
        """
        Saves plan to database and creates version snapshot.
        
        **ETAP 2 - Guest Support:**
        Plans can be owned by authenticated users OR guests.
        Either user_id OR guest_id should be provided (not both).
        
        Logic:
        1. Check if plan exists (by plan_id)
        2. If exists: UPDATE plan + CREATE new version (change_type='regenerated')
        3. If new: INSERT plan + CREATE initial version (change_type='initial')
        
        Args:
            plan: PlanResponse domain model
            user_id: Optional UUID of authenticated user
            guest_id: Optional guest ID string (UUID from frontend)
            
        Returns:
            plan_id (str)
            
        Raises:
            SQLAlchemyError: Database operation failed
            ValueError: If both user_id and guest_id are provided
        """
        # Validate: not both user_id and guest_id
        if user_id and guest_id:
            raise ValueError("Cannot provide both user_id and guest_id")
        
        try:
            plan_id = plan.plan_id
            
            # Validate UUID format
            try:
                plan_uuid = uuid.UUID(plan_id)
            except (ValueError, AttributeError, TypeError):
                raise ValueError(f"Invalid plan_id UUID format: {plan_id}")
            
            # Check if plan exists
            existing_plan = self.db.query(Plan).filter(Plan.id == plan_uuid).first()
            
            # Derive trip context (city, group, budget, dates, title) from
            # trip_input (preferred) or from PlanResponse fields (fallback).
            ctx = self._derive_trip_context(plan, trip_input)

            if existing_plan:
                # UPDATE existing plan
                existing_plan.updated_at = datetime.utcnow()
                # Preserve payment status already stored in metadata
                _prev_meta = existing_plan.trip_metadata or {}
                new_meta = self._extract_metadata(plan, ctx)
                if _prev_meta.get("paid") is not None:
                    new_meta["paid"] = _prev_meta.get("paid")
                if _prev_meta.get("status"):
                    new_meta["status"] = _prev_meta.get("status")
                existing_plan.trip_metadata = new_meta
                # Backfill real location/group/budget if previously placeholder
                if ctx.get("city") and existing_plan.location in (None, "", "Unknown"):
                    existing_plan.location = ctx["city"]
                if ctx.get("group_type") and existing_plan.group_type in (None, "", "unknown"):
                    existing_plan.group_type = ctx["group_type"]
                if ctx.get("budget_level") is not None:
                    existing_plan.budget_level = ctx["budget_level"]
                
                # Link to user if provided and not already linked
                if user_id and not existing_plan.user_id:
                    existing_plan.user_id = user_id
                    existing_plan.guest_id = None  # Clear guest_id when user claims
                
                # Link to guest if provided and not already linked
                if guest_id and not existing_plan.guest_id and not existing_plan.user_id:
                    existing_plan.guest_id = guest_id
                
                # Get next version number
                max_version = self.db.query(PlanVersion).filter(
                    PlanVersion.plan_id == plan_uuid
                ).count()
                next_version = max_version + 1
                
                # Create new version snapshot
                new_version = PlanVersion(
                    id=uuid.uuid4(),
                    plan_id=plan_uuid,
                    version_number=next_version,
                    change_type='regenerated',
                    parent_version_id=None,  # TODO: track parent when rollback is implemented
                    days_json=self._serialize_days(plan.days),
                    change_summary=f"Regenerated plan (version {next_version})"
                )
                self.db.add(new_version)
                
            else:
                # INSERT new plan
                # FIX (01.07.2026): use real trip context (was hardcoded "Unknown").
                new_plan = Plan(
                    id=uuid.UUID(plan_id),
                    location=ctx.get("city") or "Unknown",
                    group_type=ctx.get("group_type") or "unknown",
                    days_count=len(plan.days),
                    budget_level=ctx.get("budget_level") if ctx.get("budget_level") is not None else 2,
                    user_id=user_id,  # ETAP 2: Link plan to authenticated user
                    guest_id=guest_id,  # ETAP 2: Link plan to guest
                    trip_metadata=self._extract_metadata(plan, ctx)
                )
                self.db.add(new_plan)
                
                # Create initial version snapshot
                initial_version = PlanVersion(
                    id=uuid.uuid4(),
                    plan_id=plan_uuid,
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
            PlanResponse or None if not found or invalid UUID
        """
        try:
            # Validate UUID format before querying
            try:
                plan_uuid = uuid.UUID(plan_id)
            except (ValueError, AttributeError, TypeError):
                # Invalid UUID format - return None instead of crashing
                return None
            
            # Fetch plan metadata
            plan = self.db.query(Plan).filter(Plan.id == plan_uuid).first()
            
            if not plan:
                return None
            
            # Fetch latest version (highest version_number)
            latest_version = self.db.query(PlanVersion).filter(
                PlanVersion.plan_id == plan_uuid
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
            True if updated, False if plan not found or invalid UUID
        """
        try:
            # Validate UUID format
            try:
                plan_uuid = uuid.UUID(plan_id)
            except (ValueError, AttributeError, TypeError):
                # Invalid UUID - return False instead of crashing
                return False
            
            plan = self.db.query(Plan).filter(Plan.id == plan_uuid).first()
            
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
            True if deleted, False if not found or invalid UUID
        """
        try:
            # Validate UUID format
            try:
                plan_uuid = uuid.UUID(plan_id)
            except (ValueError, AttributeError, TypeError):
                # Invalid UUID - return False instead of crashing
                return False
            
            plan = self.db.query(Plan).filter(Plan.id == plan_uuid).first()
            
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
            Metadata dict or None if not found or invalid UUID
        """
        try:
            # Validate UUID format before querying
            try:
                plan_uuid = uuid.UUID(plan_id)
            except (ValueError, AttributeError, TypeError):
                # Invalid UUID format - return None instead of crashing
                # This handles legacy data or corrupted plan_ids gracefully
                return None
            
            plan = self.db.query(Plan).filter(Plan.id == plan_uuid).first()
            
            if not plan:
                return None
            
            # Get version count
            version_count = self.db.query(PlanVersion).filter(
                PlanVersion.plan_id == plan_uuid
            ).count()

            trip_meta = plan.trip_metadata or {}

            # FIX (01.07.2026 - front feedback): expose payment status so the
            # frontend can gate the paywall (was always implicitly 'ready').
            paid = self.is_plan_paid(str(plan.id))
            payment_status = "paid" if paid else "unpaid"

            result = {
                "plan_id": str(plan.id),
                "location": plan.location,
                "city": trip_meta.get("city", plan.location),
                "title": trip_meta.get("title"),
                "group_type": plan.group_type,
                "days_count": plan.days_count,
                "budget_level": plan.budget_level,
                "start_date": trip_meta.get("start_date"),
                "region_type": trip_meta.get("region_type"),
                "created_at": plan.created_at.isoformat(),
                "updated_at": plan.updated_at.isoformat(),
                "version_count": version_count,
                # generation status of the plan itself (always ready when stored)
                "status": trip_meta.get('status', 'ready'),
                # payment fields
                "paid": paid,
                "payment_status": payment_status,
                # ownership (front: can decide if login is required)
                "is_assigned": plan.user_id is not None,
                **trip_meta,  # Include all custom metadata
            }
            # Ensure payment fields are not clobbered by metadata spread
            result["paid"] = paid
            result["payment_status"] = payment_status
            result["is_assigned"] = plan.user_id is not None
            return result
            
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
        Transfers guest plans to authenticated user (ETAP 2 - /claim-guest-plans).
        
        After guest creates plans and then logs in/signs up, this method transfers
        all plans owned by guest_id to the authenticated user_id.
        
        Logic:
        - Find all plans where guest_id = <guest_id>
        - Update: user_id = <user_id>, guest_id = NULL
        - Find all payment_sessions where guest_id = <guest_id>
        - Update: user_id = <user_id>, guest_id = NULL
        
        Args:
            guest_id: Guest identifier (UUID string from localStorage)
            user_id: Authenticated user UUID
            
        Returns:
            Count of transferred plans
            
        Raises:
            Exception: Database error during transfer
        """
        try:
            # Find all plans owned by guest_id
            guest_plans = self.db.query(Plan).filter(
                Plan.guest_id == guest_id
            ).all()
            
            # Transfer ownership
            transferred_count = 0
            for plan in guest_plans:
                plan.user_id = user_id
                plan.guest_id = None  # Clear guest_id after claim
                plan.updated_at = datetime.utcnow()
                transferred_count += 1
            
            # Also transfer payment sessions (if any exist)
            # Import PaymentSession model inline to avoid circular dependency
            from app.infrastructure.database.models import PaymentSession
            
            guest_payments = self.db.query(PaymentSession).filter(
                PaymentSession.guest_id == guest_id
            ).all()
            
            for payment in guest_payments:
                payment.user_id = user_id
                payment.guest_id = None  # Clear guest_id after claim
            
            self.db.commit()
            return transferred_count
            
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Failed to transfer ownership: {str(e)}")

    # --- Helper methods ---

    def _derive_trip_context(self, plan: PlanResponse, trip_input: Optional[Any]) -> Dict[str, Any]:
        """
        Buduje kontekst wycieczki (miasto, grupa, budżet, daty, nazwa).

        Preferuje trip_input (pełne dane wejściowe), a jeśli go brak — korzysta
        z pól przeniesionych już do PlanResponse (city/start_date/title/...).
        """
        ctx: Dict[str, Any] = {
            "city": None,
            "region_type": None,
            "group_type": None,
            "budget_level": None,
            "start_date": None,
            "days_count": len(plan.days),
            "title": None,
        }
        if trip_input is not None:
            try:
                ctx["city"] = (trip_input.location.city or "").strip() or None
                ctx["region_type"] = trip_input.location.region_type
                ctx["group_type"] = trip_input.group.type
                ctx["budget_level"] = trip_input.budget.level
                ctx["days_count"] = trip_input.trip_length.days
                _sd = trip_input.trip_length.start_date
                ctx["start_date"] = _sd.isoformat() if _sd else None
                ctx["preferences"] = list(trip_input.preferences or [])
                ctx["travel_style"] = getattr(trip_input, "travel_style", None)
            except Exception:
                pass
        # Fallback to PlanResponse-carried fields
        ctx["city"] = ctx["city"] or getattr(plan, "city", None)
        ctx["region_type"] = ctx["region_type"] or getattr(plan, "region_type", None)
        ctx["group_type"] = ctx["group_type"] or getattr(plan, "group_type", None)
        ctx["start_date"] = ctx["start_date"] or getattr(plan, "start_date", None)
        if getattr(plan, "preferences", None):
            ctx["preferences"] = plan.preferences
        if getattr(plan, "travel_style", None):
            ctx["travel_style"] = plan.travel_style
        if getattr(plan, "title", None):
            ctx["title"] = plan.title
        # Build a readable title if still missing
        if not ctx.get("title"):
            _c = ctx.get("city") or "Wycieczka"
            _d = ctx.get("days_count")
            if _d:
                ctx["title"] = f"{_c} — {_d} " + ("dzień" if _d == 1 else "dni")
            else:
                ctx["title"] = _c
        return ctx

    def _extract_metadata(self, plan: PlanResponse, ctx: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extracts metadata from PlanResponse for trip_metadata JSON column."""
        ctx = ctx or {}
        meta = {
            "version": plan.version,
            "days_count": ctx.get("days_count", len(plan.days)),
            "status": "ready",
        }
        # FIX (01.07.2026): persist trip context so /status, /my-plans and
        # GET /{id} can return city, dates and a proper plan name.
        for key in ("city", "region_type", "group_type", "start_date", "title", "preferences", "travel_style"):
            if ctx.get(key) is not None:
                meta[key] = ctx[key]
        return meta

    def get_owner_ids(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """
        Zwraca właściciela planu do walidacji dostępu (internal use).

        Returns {"user_id": UUID|None, "guest_id": str|None} lub None gdy brak.
        """
        try:
            plan_uuid = uuid.UUID(plan_id)
        except (ValueError, AttributeError, TypeError):
            return None
        try:
            plan = self.db.query(Plan).filter(Plan.id == plan_uuid).first()
            if not plan:
                return None
            return {"user_id": plan.user_id, "guest_id": plan.guest_id}
        except SQLAlchemyError:
            return None

    def is_plan_paid(self, plan_id: str) -> bool:
        """
        Zwraca True jeśli plan ma zakończoną (opłaconą) sesję płatności.

        Sprawdza PaymentSession.status == 'completed' dla danego plan_id.
        """
        try:
            plan_uuid = uuid.UUID(plan_id)
        except (ValueError, AttributeError, TypeError):
            return False
        try:
            from app.infrastructure.database.models import PaymentSession
            paid = self.db.query(PaymentSession).filter(
                PaymentSession.plan_id == plan_uuid,
                PaymentSession.status == "completed",
            ).first()
            return paid is not None
        except SQLAlchemyError:
            return False

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

        trip_meta = plan.trip_metadata or {}

        # FIX (01.07.2026 - front feedback): carry trip context + payment status
        # so GET /{plan_id} and /my-plans expose city, dates, title, paid.
        paid = self.is_plan_paid(str(plan.id))
        city = trip_meta.get("city") or (
            plan.location if plan.location not in (None, "", "Unknown") else None
        )
        start_date = trip_meta.get("start_date")

        # Backfill per-day date/weekday if missing in stored snapshot
        if start_date:
            try:
                from datetime import date as _date, timedelta as _td
                base = _date.fromisoformat(start_date)
                _pl_weekdays = [
                    "poniedziałek", "wtorek", "środa", "czwartek",
                    "piątek", "sobota", "niedziela",
                ]
                for d in days:
                    if getattr(d, "date", None) is None and d.day:
                        _dd = base + _td(days=d.day - 1)
                        d.date = _dd.isoformat()
                        d.weekday = _pl_weekdays[_dd.weekday()]
            except Exception:
                pass

        return PlanResponse(
            plan_id=str(plan.id),
            version=version.version_number,
            days=days,
            city=city,
            region_type=trip_meta.get("region_type"),
            group_type=plan.group_type if plan.group_type not in (None, "", "unknown") else trip_meta.get("group_type"),
            start_date=start_date,
            days_count=plan.days_count or len(days),
            title=trip_meta.get("title"),
            paid=paid,
            payment_status="paid" if paid else "unpaid",
            preferences=trip_meta.get("preferences") or [],
            travel_style=trip_meta.get("travel_style"),
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
