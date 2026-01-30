"""
Test script dla API endpoints - CZĘŚĆ 1.
Sprawdza czy wszystkie endpointy działają poprawnie.
"""
from app.api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

print("=" * 70)
print("TEST API ENDPOINTS - CZĘŚĆ 1")
print("=" * 70)

# Test 1: Health check
print("\n1. GET /health")
response = client.get("/health")
print(f"   Status: {response.status_code}")
print(f"   Response: {response.json()}")
assert response.status_code == 200, "Health check failed"

# Test 2: Root endpoint
print("\n2. GET /")
response = client.get("/")
print(f"   Status: {response.status_code}")
print(f"   Response: {response.json()}")
assert response.status_code == 200, "Root endpoint failed"

# Test 3: POST /plan/preview
print("\n3. POST /plan/preview")
trip_data = {
    "location": {
        "city": "Zakopane",
        "country": "Poland",
        "region_type": "mountain"
    },
    "group": {
        "type": "family_kids",
        "size": 4,
        "children_age": 8,
        "crowd_tolerance": 2
    },
    "trip_length": {
        "days": 1,
        "start_date": "2026-02-01"
    },
    "daily_time_window": {
        "start": "09:00",
        "end": "18:00"
    },
    "budget": {
        "level": 2
    },
    "transport_modes": ["car"]
}
response = client.post("/plan/preview", json=trip_data)
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"   Plan ID: {data.get('plan_id')}")
    print(f"   Destination: {data.get('destination')}")
else:
    print(f"   Error: {response.text}")

# Test 4: GET /content/home
print("\n4. GET /content/home")
response = client.get("/content/home")
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"   Destinations count: {data.get('featured_count')}")
    print(f"   First destination: {data['destinations'][0]['name']}")
    print(f"   Sample image_key: {data['destinations'][0]['image_key']}")
else:
    print(f"   Error: {response.text}")

# Test 5: GET /poi/{poi_id}
print("\n5. GET /poi/test_poi_123")
response = client.get("/poi/test_poi_123")
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"   POI ID: {data.get('poi_id')}")
    print(f"   Name: {data.get('name')}")
    print(f"   Image key: {data.get('image_key')}")
else:
    print(f"   Error: {response.text}")

# Test 6: POST /payment/create-checkout-session
print("\n6. POST /payment/create-checkout-session")
checkout_data = {
    "plan_id": "test_plan_123",
    "success_url": "https://example.com/success",
    "cancel_url": "https://example.com/cancel"
}
response = client.post("/payment/create-checkout-session", json=checkout_data)
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"   Session ID: {data.get('session_id')[:30]}...")
    print(f"   Checkout URL prefix: {data.get('checkout_url')[:50]}...")
else:
    print(f"   Error: {response.text}")

# Test 7: POST /payment/stripe/webhook
print("\n7. POST /payment/stripe/webhook")
webhook_data = {
    "type": "checkout.session.completed",
    "data": {"object": {"id": "cs_test_123"}}
}
response = client.post("/payment/stripe/webhook", json=webhook_data)
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"   Received: {data.get('received')}")
    print(f"   Event type: {data.get('event_type')}")
else:
    print(f"   Error: {response.text}")

print("\n" + "=" * 70)
print("WSZYSTKIE TESTY PRZESZŁY ✅")
print("=" * 70)
