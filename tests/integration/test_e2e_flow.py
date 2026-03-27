"""
End-to-End tests for complete user journey.
Tests: Auth → Plan Generation → Payment → Verification
"""
import pytest
import uuid
from datetime import datetime, timezone, timedelta
import jwt
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.infrastructure.config.settings import settings


class TestE2EUserJourney:
    """End-to-end tests for complete user flow."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def user_id(self):
        """Generate random user ID for test."""
        return str(uuid.uuid4())
    
    @pytest.fixture
    def user_email(self):
        """Generate random email for test."""
        return f"e2e-test-{uuid.uuid4().hex[:8]}@example.com"
    
    @pytest.fixture
    def auth_token(self, user_id, user_email):
        """Generate JWT token for authenticated user."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "email": user_email,
            "role": "authenticated",
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "iat": int(now.timestamp())
        }
        return jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        """Create Authorization headers."""
        return {"Authorization": f"Bearer {auth_token}"}
    
    @pytest.fixture
    def trip_input(self):
        """Sample trip input for plan generation."""
        return {
            "location": {
                "city": "Zakopane",
                "country": "Poland",
                "region_type": "mountain"
            },
            "group": {
                "type": "couples",
                "size": 2,
                "crowd_tolerance": 1
            },
            "trip_length": {
                "days": 2,
                "start_date": "2026-03-15"
            },
            "daily_time_window": {
                "start": "09:00",
                "end": "19:00"
            },
            "budget": {"level": 2},
            "transport_modes": ["car"],
            "travel_style": "balanced"
        }
    
    def test_complete_journey_anonymous_user(self, client, trip_input):
        """Test complete journey for anonymous user (ETAP 1 compatibility)."""
        # Step 1: Generate plan without authentication
        response = client.post(
            "/plan/preview",
            json=trip_input,
            timeout=120
        )
        
        # Assert: Plan generated successfully
        assert response.status_code == 200
        data = response.json()
        assert "plan_id" in data
        assert "days" in data
        assert len(data["days"]) == 2
        
        plan_id = data["plan_id"]
        
        # Verify: Plan created without user_id (anonymous)
        # In production, would query database to verify user_id is NULL
        assert plan_id is not None
    
    def test_complete_journey_authenticated_user(self, client, auth_headers, trip_input):
        """Test complete journey for authenticated user (ETAP 2)."""
        # Step 1: Generate plan WITH authentication
        response1 = client.post(
            "/plan/preview",
            json=trip_input,
            headers=auth_headers,
            timeout=120
        )
        
        # Assert: Plan generated and linked to user
        assert response1.status_code == 200
        data1 = response1.json()
        assert "plan_id" in data1
        assert "days" in data1
        
        plan_id = data1["plan_id"]
        
        # Step 2: Create payment checkout session
        with patch('app.infrastructure.payment.stripe_client.stripe.checkout.Session.create') as mock_create:
            session_id = "cs_test_e2e_001"
            mock_create.return_value = MagicMock(
                id=session_id,
                url=f"https://checkout.stripe.com/pay/{session_id}",
                expires_at=int((datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp()),
                payment_status="unpaid"
            )
            
            response2 = client.post(
                "/payment/create-checkout-session",
                json={"plan_id": plan_id},
                headers=auth_headers,
                timeout=30
            )
            
            # Assert: Checkout session created
            assert response2.status_code == 200
            data2 = response2.json()
            assert data2["session_id"] == session_id
            assert "checkout_url" in data2
        
        # Step 3: Simulate webhook (payment completed)
        with patch('app.infrastructure.payment.stripe_client.stripe.Webhook.construct_event') as mock_webhook:
            webhook_event = {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": session_id,
                        "payment_status": "paid",
                        "amount_total": 1000,
                        "currency": "usd",
                        "metadata": {"plan_id": plan_id}
                    }
                }
            }
            mock_webhook.return_value = webhook_event
            
            response3 = client.post(
                "/payment/stripe/webhook",
                content='{"type":"checkout.session.completed"}',
                headers={"stripe-signature": "valid_signature"},
                timeout=30
            )
            
            # Assert: Webhook processed successfully
            assert response3.status_code == 200
            assert response3.json()["status"] == "success"
        
        # Step 4: Verify payment status
        with patch('app.infrastructure.payment.stripe_client.stripe.checkout.Session.retrieve') as mock_retrieve:
            mock_retrieve.return_value = MagicMock(
                id=session_id,
                payment_status="paid",
                status="complete",
                amount_total=1000
            )
            
            response4 = client.get(
                f"/payment/session/{session_id}/status",
                headers=auth_headers,
                timeout=30
            )
            
            # Assert: Payment completed
            assert response4.status_code == 200
            data4 = response4.json()
            assert data4["payment_status"] == "paid"
            assert data4["status"] == "complete"
    
    def test_journey_with_invalid_token(self, client, trip_input):
        """Test that invalid token is rejected (security)."""
        # Arrange: Create expired token
        now = datetime.now(timezone.utc)
        expired_payload = {
            "sub": "test-user",
            "email": "test@example.com",
            "exp": int((now - timedelta(hours=1)).timestamp())  # Expired
        }
        expired_token = jwt.encode(expired_payload, settings.supabase_jwt_secret, algorithm="HS256")
        
        # Act: Try to generate plan with expired token
        response = client.post(
            "/plan/preview",
            json=trip_input,
            headers={"Authorization": f"Bearer {expired_token}"},
            timeout=120
        )
        
        # Assert: Request rejected with 401
        assert response.status_code == 401
    
    def test_payment_without_auth_rejected(self, client):
        """Test that payment endpoints require authentication."""
        # Arrange
        plan_id = str(uuid.uuid4())
        
        # Act: Try to create checkout without auth
        response = client.post(
            "/payment/create-checkout-session",
            json={"plan_id": plan_id},
            timeout=30
        )
        
        # Assert: Rejected with 401
        assert response.status_code == 401


class TestBackwardCompatibility:
    """Test backward compatibility with ETAP 1."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def etap1_trip_input(self):
        """Sample trip input from ETAP 1 tests."""
        return {
            "location": {
                "city": "Zakopane",
                "country": "Poland",
                "region_type": "mountain"
            },
            "group": {
                "type": "families_with_kids",
                "size": 4,
                "crowd_tolerance": 2
            },
            "trip_length": {
                "days": 3,
                "start_date": "2026-04-01"
            },
            "daily_time_window": {
                "start": "08:00",
                "end": "20:00"
            },
            "budget": {"level": 2},
            "transport_modes": ["car"],
            "travel_style": "relaxed"
        }
    
    def test_etap1_endpoint_still_works(self, client, etap1_trip_input):
        """Test that ETAP 1 functionality is not broken by ETAP 2 changes."""
        # Act: Call /preview without authentication (ETAP 1 behavior)
        response = client.post(
            "/plan/preview",
            json=etap1_trip_input,
            timeout=120
        )
        
        # Assert: Still works without auth
        assert response.status_code == 200
        data = response.json()
        assert "plan_id" in data
        assert "days" in data
        assert len(data["days"]) == 3
        
        # Verify response structure unchanged
        for day in data["days"]:
            assert "day_number" in day
            assert "date" in day
            assert "pois" in day or "poi_list" in day
            assert "summary" in day


class TestPhase5ProtectedEndpoints:
    """Test Phase 5: Protected Endpoints with optional auth."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def valid_token(self):
        """Generate valid JWT token."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(uuid.uuid4()),
            "email": f"phase5-{uuid.uuid4().hex[:8]}@test.com",
            "role": "authenticated",
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "iat": int(now.timestamp())
        }
        return jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")
    
    @pytest.fixture
    def trip_input(self):
        """Sample trip input."""
        return {
            "location": {"city": "Zakopane", "country": "Poland", "region_type": "mountain"},
            "group": {"type": "couples", "size": 2, "crowd_tolerance": 1},
            "trip_length": {"days": 1, "start_date": "2026-03-20"},
            "daily_time_window": {"start": "10:00", "end": "18:00"},
            "budget": {"level": 2},
            "transport_modes": ["car"],
            "travel_style": "balanced"
        }
    
    def test_preview_without_auth_works(self, client, trip_input):
        """Test /preview works without authentication (backward compatibility)."""
        response = client.post("/plan/preview", json=trip_input, timeout=120)
        
        assert response.status_code == 200
        assert "plan_id" in response.json()
    
    def test_preview_with_valid_auth_works(self, client, trip_input, valid_token):
        """Test /preview works WITH authentication."""
        response = client.post(
            "/plan/preview",
            json=trip_input,
            headers={"Authorization": f"Bearer {valid_token}"},
            timeout=120
        )
        
        assert response.status_code == 200
        assert "plan_id" in response.json()
    
    def test_preview_with_invalid_token_rejected(self, client, trip_input):
        """Test /preview rejects invalid token (security)."""
        response = client.post(
            "/plan/preview",
            json=trip_input,
            headers={"Authorization": "Bearer invalid-token-xyz"},
            timeout=120
        )
        
        assert response.status_code == 401
