"""
Payment endpoints - mock Stripe integration (ETAP 1).
"""
from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel
import uuid
from datetime import datetime

router = APIRouter()


class CreateCheckoutRequest(BaseModel):
    """Request dla utworzenia sesji platnosci."""
    plan_id: str
    success_url: str
    cancel_url: str


class CheckoutSessionResponse(BaseModel):
    """Response z URL do Stripe Checkout."""
    session_id: str
    checkout_url: str


@router.post("/create-checkout-session", response_model=CheckoutSessionResponse)
def create_checkout_session(request: CreateCheckoutRequest):
    """
    Tworzy sesje platnosci Stripe.
    
    ETAP 1: Mock implementation - zwraca fake URL.
    ETAP 2: Prawdziwa integracja ze Stripe.
    """
    # Mock session ID
    session_id = f"cs_test_{uuid.uuid4().hex[:24]}"
    
    # Mock checkout URL
    # W ETAP 2 tutaj bedzie prawdziwy Stripe Checkout URL
    mock_checkout_url = (
        f"https://checkout.stripe.com/pay/{session_id}"
        f"?success_url={request.success_url}"
        f"&cancel_url={request.cancel_url}"
    )
    
    # TODO: zapisac session w bazie z plan_id
    # TODO: ustawic timeout na sesje (24h)
    
    return CheckoutSessionResponse(
        session_id=session_id,
        checkout_url=mock_checkout_url
    )


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    """
    Webhook od Stripe - obsluga zdarzen platnosci.
    
    ETAP 1: Mock - akceptuje wszystko.
    ETAP 2: Walidacja Stripe signature, obsluga eventow.
    
    Zdarzenia do obslugi:
    - checkout.session.completed: platnosc sukces
    - checkout.session.expired: sesja wygasla
    - payment_intent.succeeded: potwierdzenie platnosci
    """
    # W ETAP 2 tutaj walidacja:
    # sig_header = request.headers.get('stripe-signature')
    # event = stripe.Webhook.construct_event(payload, sig_header, secret)
    
    payload = await request.json()
    event_type = payload.get("type", "unknown")
    
    # Mock response - przyjmujemy wszystko
    return {
        "received": True,
        "event_type": event_type,
        "processed_at": datetime.utcnow().isoformat(),
        "note": "ETAP 1: mock webhook - always accepts"
    }
