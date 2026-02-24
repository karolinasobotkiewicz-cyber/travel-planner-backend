"""
Stripe API client wrapper.
Handles checkout session creation and management.
"""
import stripe
from typing import Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timezone

from app.infrastructure.config.settings import settings


# Initialize Stripe with secret key
stripe.api_key = settings.stripe_secret_key


class StripeCheckoutSession(BaseModel):
    """Stripe checkout session data."""
    session_id: str
    checkout_url: str
    status: str
    amount: int  # Amount in smallest currency unit (grosz for PLN)
    currency: str
    expires_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


def create_checkout_session(
    plan_id: str,
    user_id: str,
    success_url: str,
    cancel_url: str
) -> StripeCheckoutSession:
    """
    Create Stripe Checkout Session for plan payment.
    
    Args:
        plan_id: UUID of the travel plan
        user_id: UUID of the user making payment
        success_url: URL to redirect after successful payment
        cancel_url: URL to redirect if payment cancelled
        
    Returns:
        StripeCheckoutSession with session_id and checkout_url
        
    Raises:
        stripe.error.StripeError: If Stripe API request fails
        ValueError: If required settings not configured
        
    Example:
        session = create_checkout_session(
            plan_id="123e4567-e89b-12d3-a456-426614174000",
            user_id="987fcdeb-51a2-43d1-9012-345678901234",
            success_url="http://localhost:3000/payment/success",
            cancel_url="http://localhost:3000/payment/cancel"
        )
        # User visits: session.checkout_url
    """
    if not settings.stripe_secret_key or not settings.stripe_price_id:
        raise ValueError(
            "Stripe not configured. Set STRIPE_SECRET_KEY and STRIPE_PRICE_ID in .env"
        )
    
    try:
        # Create Stripe Checkout Session
        session = stripe.checkout.Session.create(
            mode="payment",  # One-time payment (NOT subscription)
            line_items=[{
                "price": settings.stripe_price_id,  # price_1T47aZHKwaztaoKBqd8ewYPw (39.99 PLN)
                "quantity": 1,
            }],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "plan_id": plan_id,
                "user_id": user_id,
            },
            # Expire after 24 hours
            expires_at=int(datetime.now(timezone.utc).timestamp()) + (24 * 60 * 60),
        )
        
        return StripeCheckoutSession(
            session_id=session.id,
            checkout_url=session.url,
            status=session.status,
            amount=session.amount_total,  # 3999 (39.99 PLN in grosz)
            currency=session.currency,  # "pln"
            expires_at=datetime.fromtimestamp(session.expires_at)
        )
        
    except stripe.error.StripeError as e:
        # Stripe API error
        raise stripe.error.StripeError(
            f"Failed to create Stripe checkout session: {str(e)}"
        ) from e


def get_checkout_session(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve Stripe Checkout Session details.
    
    Args:
        session_id: Stripe session ID (cs_test_...)
        
    Returns:
        Session dict or None if not found
        
    Raises:
        stripe.error.StripeError: If Stripe API request fails
        
    Example:
        session = get_checkout_session("cs_test_abc123")
        if session:
            status = session["status"]  # "complete", "expired", "open"
            payment_status = session["payment_status"]  # "paid", "unpaid"
    """
    if not settings.stripe_secret_key:
        raise ValueError("Stripe not configured. Set STRIPE_SECRET_KEY in .env")
    
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        return session
        
    except stripe.error.InvalidRequestError:
        # Session not found
        return None
        
    except stripe.error.StripeError as e:
        # Other Stripe API error
        raise stripe.error.StripeError(
            f"Failed to retrieve Stripe session: {str(e)}"
        ) from e
