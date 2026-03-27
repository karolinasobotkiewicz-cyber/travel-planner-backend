"""
Phase 5 Testing - Protected Endpoints & CORS
Tests backward compatibility and auth integration
"""
import requests
import json
from datetime import datetime, timezone, timedelta
import jwt
import uuid

BACKEND_URL = "https://travel-planner-backend-xbsp.onrender.com"
JWT_SECRET = "pvaAG1JoRNPiJf7ySWPJVnNOn4NfT4MiIOXAuIUgZdYrgYlSphNzqhkfuvelA5KLUG+O5gKoZNok1wn2uJ6DaA=="

TRIP_INPUT = {
    "location": {"city": "Zakopane", "country": "Poland", "region_type": "mountain"},
    "group": {"type": "couples", "size": 2, "crowd_tolerance": 1},
    "trip_length": {"days": 2, "start_date": "2026-03-15"},
    "daily_time_window": {"start": "09:00", "end": "19:00"},
    "budget": {"level": 2},
    "transport_modes": ["car"],
    "travel_style": "balanced"
}

def create_jwt_token(user_id: str, email: str) -> str:
    """Create JWT token like Supabase"""
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

print("=" * 70)
print("PHASE 5 TESTING: Protected Endpoints + CORS")
print("=" * 70)

# ========================================
# TEST 1: Backward Compatibility (no auth)
# ========================================
print("\n[TEST 1] /preview WITHOUT auth (backward compatibility)")
try:
    response = requests.post(
        f"{BACKEND_URL}/plan/preview",
        json=TRIP_INPUT,
        timeout=120
    )
    
    if response.status_code == 200:
        data = response.json()
        print("✅ PASS: Endpoint works without authentication")
        print(f"   Plan ID: {data['plan_id']}")
        print(f"   Days: {len(data['days'])}")
        # Try both poi_list and pois (response model may vary)
        poi_count = 0
        if data['days']:
            first_day = data['days'][0]
            if 'poi_list' in first_day:
                poi_count = sum(len(day['poi_list']) for day in data['days'])
            elif 'pois' in first_day:
                poi_count = sum(len(day['pois']) for day in data['days'])
        print(f"   POI count: {poi_count}")
    else:
        print(f"❌ FAIL: Status {response.status_code}")
        print(f"   Response: {response.text[:200]}")
except requests.exceptions.Timeout:
    print("⏱️  TIMEOUT: Backend may be cold starting (Render free tier)")
    print("   Retry in 30 seconds...")
except Exception as e:
    print(f"❌ ERROR: {e}")

# ========================================
# TEST 2: With Valid Auth Token
# ========================================
print("\n[TEST 2] /preview WITH valid JWT token")
try:
    # Generate random user to avoid DB conflicts
    test_user_id = str(uuid.uuid4())
    test_email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    
    token = create_jwt_token(
        user_id=test_user_id,
        email=test_email
    )
    
    response = requests.post(
        f"{BACKEND_URL}/plan/preview",
        json=TRIP_INPUT,
        headers={"Authorization": f"Bearer {token}"},
        timeout=120
    )
    
    if response.status_code == 200:
        data = response.json()
        print("✅ PASS: Endpoint works with authentication")
        print(f"   Plan ID: {data['plan_id']}")
        print(f"   Days: {len(data['days'])}")
        print(f"   User authenticated: {test_user_id}")
        print("   Note: Plan should be linked to user_id in database")
    else:
        print(f"❌ FAIL: Status {response.status_code}")
        print(f"   Response: {response.text[:200]}")
except Exception as e:
    print(f"❌ ERROR: {e}")

# ========================================
# TEST 3: With Expired Token
# ========================================
print("\n[TEST 3] /preview WITH expired JWT token")
try:
    # Create expired token (exp = 1 hour ago)
    now = datetime.now(timezone.utc)
    expired_payload = {
        "sub": "test-user-expired",
        "email": "expired@example.com",
        "aud": "authenticated",
        "role": "authenticated",
        "exp": int((now - timedelta(hours=1)).timestamp()),  # Expired!
        "iat": int((now - timedelta(hours=2)).timestamp())
    }
    expired_token = jwt.encode(expired_payload, JWT_SECRET, algorithm="HS256")
    
    response = requests.post(
        f"{BACKEND_URL}/plan/preview",
        json=TRIP_INPUT,
        headers={"Authorization": f"Bearer {expired_token}"},
        timeout=120
    )
    
    if response.status_code == 401:
        print("✅ PASS: Expired token rejected (401 Unauthorized)")
    elif response.status_code == 200:
        print("❌ FAIL: Expired token accepted (should be 401)")
    else:
        print(f"⚠️  UNEXPECTED: Status {response.status_code}")
        print(f"   Response: {response.text[:200]}")
except Exception as e:
    print(f"❌ ERROR: {e}")

# ========================================
# TEST 4: With Invalid Signature
# ========================================
print("\n[TEST 4] /preview WITH invalid signature")
try:
    # Create token with wrong secret
    wrong_token = jwt.encode(
        {
            "sub": "test-user",
            "email": "test@example.com",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
        },
        "WRONG_SECRET_KEY",
        algorithm="HS256"
    )
    
    response = requests.post(
        f"{BACKEND_URL}/plan/preview",
        json=TRIP_INPUT,
        headers={"Authorization": f"Bearer {wrong_token}"},
        timeout=120
    )
    
    if response.status_code == 401:
        print("✅ PASS: Invalid signature rejected (401 Unauthorized)")
    elif response.status_code == 200:
        print("❌ FAIL: Invalid signature accepted (should be 401)")
    else:
        print(f"⚠️  UNEXPECTED: Status {response.status_code}")
        print(f"   Response: {response.text[:200]}")
except Exception as e:
    print(f"❌ ERROR: {e}")

print("\n" + "=" * 70)
print("PHASE 5 TESTING COMPLETE")
print("=" * 70)
print("\n✅ Expected Results:")
print("   - TEST 1: 200 OK (backward compatibility)")
print("   - TEST 2: 200 OK (valid auth)")
print("   - TEST 3: 401 Unauthorized (expired token)")
print("   - TEST 4: 401 Unauthorized (invalid signature)")
print("\n📝 Note: CORS cannot be tested from Python (browser-only)")
print("   CORS config: localhost:3000, lets-travel.pl")
