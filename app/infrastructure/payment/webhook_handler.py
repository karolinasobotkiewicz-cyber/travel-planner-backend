"""
Stripe webhook handler.
Validates webhook signatures and processes payment events.
"""
import stripe
from typing import Dict, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.infrastructure.config.settings import settings
from app.infrastructure.database.models import PaymentSession, Transaction, Plan


def validate_webhook_signature(payload: bytes, sig_header: str) -> stripe.Event:
    """
    Validate Stripe webhook signature and construct event.
    
    Args:
        payload: Raw request body (bytes)
        sig_header: Stripe-Signature header value
        
    Returns:
        Validated Stripe Event object
        
    Raises:
        HTTPException 400: If signature validation fails
        ValueError: If webhook secret not configured
        
    Security:
        - Prevents replay attacks (timestamp verification)
        - Validates HMAC signature
        - Ensures request came from Stripe
        
    Example:
        event = validate_webhook_signature(
            payload=await request.body(),
            sig_header=request.headers.get("stripe-signature")
        )
        if event.type == "checkout.session.completed":
            # Process payment...
    """
    if not settings.stripe_webhook_secret:
        raise ValueError(
            "Stripe webhook secret not configured. "
            "Set STRIPE_WEBHOOK_SECRET in .env after configuring webhook in Stripe dashboard"
        )
    
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=settings.stripe_webhook_secret
        )
        return event
        
    except ValueError as e:
        # Invalid payload
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid webhook payload: {str(e)}"
        ) from e
        
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid webhook signature: {str(e)}"
        ) from e


def handle_checkout_completed(
    session: Dict,
    db: Session
) -> Dict[str, str]:
    """
    Handle checkout.session.completed event.
    
    Flow:
    1. Extract plan_id, user_id from session.metadata
    2. Find PaymentSession in database
    3. Update PaymentSession status to "completed"
    4. Create Transaction record (audit trail)
    5. Success!
    
    Args:
        session: Stripe Session object (dict)
        db: Database session
        
    Returns:
        Dict with status message
        
    Raises:
        HTTPException 404: If PaymentSession not found
        
    Example:
        event = validate_webhook_signature(...)
        if event.type == "checkout.session.completed":
            result = handle_checkout_completed(event.data.object, db)
    """
    session_id = session["id"]
    payment_status = session.get("payment_status")
    
    # Extract metadata
    metadata = session.get("metadata", {})
    plan_id = metadata.get("plan_id")
    user_id = metadata.get("user_id")
    
    if not plan_id or not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing plan_id or user_id in session metadata"
        )
    
    # Find PaymentSession
    payment_session = db.query(PaymentSession).filter(
        PaymentSession.stripe_session_id == session_id
    ).first()
    
    if not payment_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PaymentSession not found for session_id: {session_id}"
        )
    
    # Update PaymentSession
    payment_session.status = "completed"
    payment_session.completed_at = datetime.now(timezone.utc)
    
    # Create Transaction (audit trail)
    transaction = Transaction(
        user_id=user_id,
        plan_id=plan_id,
        payment_session_id=payment_session.id,
        stripe_payment_intent=session.get("payment_intent"),  # pi_...
        amount=payment_session.amount,
        currency=payment_session.currency,
        status="succeeded" if payment_status == "paid" else "pending"
    )
    db.add(transaction)
    
    db.commit()
    
    return {
        "status": "success",
        "message": f"Payment completed for plan {plan_id}",
        "transaction_id": str(transaction.id)
    }


def handle_checkout_expired(
    session: Dict,
    db: Session
) -> Dict[str, str]:
    """
    Handle checkout.session.expired event.
    
    Flow:
    1. Find PaymentSession by stripe_session_id
    2. Update status to "expired"
    3. User can create new session if they want to retry
    
    Args:
        session: Stripe Session object (dict)
        db: Database session
        
    Returns:
        Dict with status message
        
    Example:
        event = validate_webhook_signature(...)
        if event.type == "checkout.session.expired":
            result = handle_checkout_expired(event.data.object, db)
    """
    session_id = session["id"]
    
    # Find PaymentSession
    payment_session = db.query(PaymentSession).filter(
        PaymentSession.stripe_session_id == session_id
    ).first()
    
    if not payment_session:
        # Session not found - log warning but don't fail
        return {
            "status": "warning",
            "message": f"PaymentSession not found for expired session: {session_id}"
        }
    
    # Update status
    payment_session.status = "expired"
    db.commit()
    
    return {
        "status": "success",
        "message": f"Payment session expired: {session_id}"
    }


def handle_payment_succeeded(
    payment_intent: Dict,
    db: Session
) -> Dict[str, str]:
    """
    Handle payment_intent.succeeded event.
    
    This is a backup handler - normally checkout.session.completed
    handles everything. But payment_intent.succeeded confirms the
    actual money transfer succeeded.
    
    Flow:
    1. Find Transaction by stripe_payment_intent
    2. Update status to "succeeded"
    3. Double-confirm payment is complete
    
    Args:
        payment_intent: Stripe PaymentIntent object (dict)
        db: Database session
        
    Returns:
        Dict with status message
        
    Example:
        event = validate_webhook_signature(...)
        if event.type == "payment_intent.succeeded":
            result = handle_payment_succeeded(event.data.object, db)
    """
    payment_intent_id = payment_intent["id"]
    
    # Find Transaction
    transaction = db.query(Transaction).filter(
        Transaction.stripe_payment_intent == payment_intent_id
    ).first()
    
    if not transaction:
        # Transaction not found - might be processed by checkout.session.completed first
        return {
            "status": "info",
            "message": f"Transaction not found for payment_intent: {payment_intent_id}"
        }
    
    # Update status
    transaction.status = "succeeded"
    db.commit()
    
    return {
        "status": "success",
        "message": f"Payment intent confirmed: {payment_intent_id}"
    }
