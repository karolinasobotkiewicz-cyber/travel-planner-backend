"""
Payment endpoints - Stripe integration (ETAP 2).
Real Stripe Checkout Session creation and webhook handling.
"""
from fastapi import APIRouter, HTTPException, status, Request, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import stripe

from app.api.dependencies import get_session, get_current_user
from app.infrastructure.database.models import User, PaymentSession, Plan
from app.infrastructure.payment import (
    create_checkout_session as create_stripe_session,
    validate_webhook_signature,
    handle_checkout_completed,
    handle_checkout_expired,
    handle_payment_succeeded
)

router = APIRouter()


class CreateCheckoutRequest(BaseModel):
    """Request to create Stripe checkout session."""
    plan_id: str
    success_url: str
    cancel_url: str


class CheckoutSessionResponse(BaseModel):
    """Response with Stripe Checkout URL."""
    session_id: str
    checkout_url: str
    amount: int
    currency: str
    expires_at: str


class SessionStatusResponse(BaseModel):
    """Payment session status."""
    session_id: str
    status: str  # pending, completed, expired, failed
    amount: int
    currency: str
    created_at: str
    expires_at: str
    completed_at: str | None


@router.post("/create-checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    request: CreateCheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Create Stripe Checkout Session for plan payment.
    
    Flow:
    1. Verify plan exists and belongs to user
    2. Create Stripe Checkout Session (real API call)
    3. Save PaymentSession in database
    4. Return checkout URL for frontend redirect
    
    Security:
    - Requires valid JWT token (get_current_user)
    - User can only pay for their own plans
    
    Example:
        POST /payment/create-checkout-session
        Authorization: Bearer <jwt_token>
        {
            "plan_id": "123e4567-e89b-12d3-a456-426614174000",
            "success_url": "http://localhost:3000/payment/success",
            "cancel_url": "http://localhost:3000/payment/cancel"
        }
        
        Response:
        {
            "session_id": "cs_test_...",
            "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_...",
            "amount": 3999,
            "currency": "pln",
            "expires_at": "2026-02-25T12:00:00"
        }
    """
    # Verify plan exists
    plan = db.query(Plan).filter(Plan.id == request.plan_id).first()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan not found: {request.plan_id}"
        )
    
    # Verify plan belongs to current user (if user_id is set)
    if plan.user_id and str(plan.user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create payment session for another user's plan"
        )
    
    # Check if plan already has completed payment
    existing_payment = db.query(PaymentSession).filter(
        PaymentSession.plan_id == request.plan_id,
        PaymentSession.status == "completed"
    ).first()
    
    if existing_payment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plan already paid for"
        )
    
    try:
        # Create Stripe Checkout Session (real API call)
        stripe_session = create_stripe_session(
            plan_id=request.plan_id,
            user_id=str(current_user.id),
            success_url=request.success_url,
            cancel_url=request.cancel_url
        )
        
        # Save PaymentSession in database
        payment_session = PaymentSession(
            user_id=current_user.id,
            plan_id=request.plan_id,
            stripe_session_id=stripe_session.session_id,
            amount=stripe_session.amount / 100,  # Convert grosz to PLN
            currency=stripe_session.currency.upper(),
            status="pending",
            expires_at=stripe_session.expires_at
        )
        db.add(payment_session)
        
        # Link plan to user if not already
        if not plan.user_id:
            plan.user_id = current_user.id
        
        db.commit()
        db.refresh(payment_session)
        
        return CheckoutSessionResponse(
            session_id=stripe_session.session_id,
            checkout_url=stripe_session.checkout_url,
            amount=stripe_session.amount,
            currency=stripe_session.currency,
            expires_at=stripe_session.expires_at.isoformat()
        )
        
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stripe API error: {str(e)}"
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        ) from e


@router.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_session)
):
    """
    Stripe webhook endpoint - handles payment events.
    
    Events handled:
    - checkout.session.completed: Payment succeeded → update PaymentSession, create Transaction
    - checkout.session.expired: Session expired → update PaymentSession status
    - payment_intent.succeeded: Confirm payment succeeded → update Transaction status
    
    Security:
    - Validates Stripe signature (HMAC)
    - Prevents replay attacks
    - Only processes events from Stripe
    
    Configuration:
    1. In Stripe Dashboard → Developers → Webhooks
    2. Add endpoint: https://your-domain.com/payment/stripe/webhook
    3. Select events: checkout.session.completed, checkout.session.expired, payment_intent.succeeded
    4. Copy webhook secret to STRIPE_WEBHOOK_SECRET in .env
    
    Testing locally:
    ```bash
    stripe listen --forward-to http://localhost:8000/payment/stripe/webhook
    stripe trigger checkout.session.completed
    ```
    """
    # Get raw body and signature
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing stripe-signature header"
        )
    
    try:
        # Validate webhook signature
        event = validate_webhook_signature(payload, sig_header)
        
        # Handle event based on type
        event_type = event.type
        event_data = event.data.object
        
        if event_type == "checkout.session.completed":
            result = handle_checkout_completed(event_data, db)
            
        elif event_type == "checkout.session.expired":
            result = handle_checkout_expired(event_data, db)
            
        elif event_type == "payment_intent.succeeded":
            result = handle_payment_succeeded(event_data, db)
            
        else:
            # Unknown event - log but don't fail
            result = {
                "status": "ignored",
                "message": f"Unhandled event type: {event_type}"
            }
        
        return {
            "received": True,
            "event_type": event_type,
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "result": result
        }
        
    except HTTPException:
        # Re-raise HTTPExceptions from validation/handlers
        raise
        
    except Exception as e:
        # Log unexpected errors but return 200 to avoid Stripe retries
        # (Stripe retries webhooks that return 4xx/5xx)
        return {
            "received": True,
            "error": str(e),
            "note": "Error logged - returning 200 to prevent Stripe retries"
        }


@router.get("/session/{session_id}/status", response_model=SessionStatusResponse)
async def get_session_status(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Get payment session status.
    
    Used by frontend to check if payment completed after redirect from Stripe.
    
    Example:
        GET /payment/session/cs_test_abc123/status
        Authorization: Bearer <jwt_token>
        
        Response:
        {
            "session_id": "cs_test_abc123",
            "status": "completed",
            "amount": 3999,
            "currency": "PLN",
            "created_at": "2026-02-24T10:00:00",
            "expires_at": "2026-02-25T10:00:00",
            "completed_at": "2026-02-24T10:05:00"
        }
    """
    # Find PaymentSession
    payment_session = db.query(PaymentSession).filter(
        PaymentSession.stripe_session_id == session_id
    ).first()
    
    if not payment_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment session not found: {session_id}"
        )
    
    # Verify session belongs to current user
    if str(payment_session.user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access another user's payment session"
        )
    
    return SessionStatusResponse(
        session_id=payment_session.stripe_session_id,
        status=payment_session.status,
        amount=int(payment_session.amount * 100),  # Convert PLN to grosz
        currency=payment_session.currency,
        created_at=payment_session.created_at.isoformat(),
        expires_at=payment_session.expires_at.isoformat(),
        completed_at=payment_session.completed_at.isoformat() if payment_session.completed_at else None
    )
