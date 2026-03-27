"""
Test prawdziwego payment flow - tak jak będzie użyty przez klientkę.
1. Tworzymy checkout session przez API (z JWT tokenem)
2. Otwieramy URL w przeglądarce
3. Płacimy testową kartą: 4242 4242 4242 4242
4. Stripe wyśle PRAWDZIWY webhook z production secretem
"""
import requests
import webbrowser
from datetime import datetime, timezone, timedelta
import jwt

# Konfiguracja
# BACKEND_URL = "https://travel-planner-backend-xbsp.onrender.com"
BACKEND_URL = "http://localhost:8000"  # Test lokalny

# JWT secret z .env
JWT_SECRET = "pvaAG1JoRNPiJf7ySWPJVnNOn4NfT4MiIOXAuIUgZdYrgYlSphNzqhkfuvelA5KLUG+O5gKoZNok1wn2uJ6DaA=="

# Testowy user
TEST_USER = {
    "id": "c5e0f8a0-1234-5678-9abc-def012345678",
    "email": "test@example.com"
}

def create_jwt_token(user_id: str, email: str) -> str:
    """Tworzy JWT token jak Supabase"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "aud": "authenticated",
        "role": "authenticated",
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "iat": int(now.timestamp())
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def test_payment_flow():
    print("=" * 70)
    print("TEST PAYMENT FLOW - Jak będzie użyty przez klientkę")
    print("=" * 70)
    
    # 1. Tworzymy JWT token
    print("\n[1/4] Tworzę JWT token...")
    token = create_jwt_token(TEST_USER["id"], TEST_USER["email"])
    print(f"✅ Token: {token[:50]}...")
    
    # 2. Tworzymy checkout session
    print("\n[2/4] Tworzę checkout session przez API...")
    try:
        response = requests.post(
            f"{BACKEND_URL}/payment/create-checkout-session",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={
                "plan_id": "test-plan-123",
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            checkout_url = data["url"]
            session_id = data["session_id"]
            
            print(f"✅ Checkout session utworzona!")
            print(f"   Session ID: {session_id}")
            print(f"   URL: {checkout_url}")
            
            # 3. Otwieramy w przeglądarce
            print("\n[3/4] Otwieram checkout w przeglądarce...")
            print("\n" + "=" * 70)
            print("INSTRUKCJA:")
            print("=" * 70)
            print("1. Przeglądarka otworzy Stripe Checkout")
            print("2. Użyj testowej karty: 4242 4242 4242 4242")
            print("3. Data ważności: dowolna przyszła (np. 12/34)")
            print("4. CVC: dowolne 3 cyfry (np. 123)")
            print("5. Email: dowolny")
            print("6. Kliknij 'Pay'")
            print("=" * 70)
            print("\n[4/4] Po zakończeniu płatności:")
            print("   - Stripe wyśle webhook do:", f"{BACKEND_URL}/payment/stripe/webhook")
            print("   - Sprawdź logi Render lub zakładkę 'Event deliveries' w Stripe")
            print("=" * 70)
            
            input("\nNaciśnij Enter aby otworzyć checkout w przeglądarce...")
            webbrowser.open(checkout_url)
            
            print("\n✅ Checkout otwarty! Wykonaj płatność testową.")
            print("\nPo zakończeniu płatności możesz sprawdzić:")
            print("1. Stripe Dashboard → Webhooks → Event deliveries")
            print("2. Render Dashboard → Logs")
            print(f"3. Status sesji: GET {BACKEND_URL}/payment/session/{session_id}/status")
            
        else:
            print(f"❌ Błąd podczas tworzenia checkout session:")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.exceptions.Timeout:
        print("❌ Timeout - backend na Render może się budził (free tier)")
        print("   Spróbuj ponownie za moment...")
    except Exception as e:
        print(f"❌ Błąd: {e}")

if __name__ == "__main__":
    test_payment_flow()
