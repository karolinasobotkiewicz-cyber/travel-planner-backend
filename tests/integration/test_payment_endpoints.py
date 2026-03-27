"""
Integration tests for payment endpoints.
Tests Stripe checkout session creation, retrieval, and webhook processing.
"""
import pytest
import uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta
import jwt

from app.main import app
from app.infrastructure.config.settings import settings


class TestPaymentEndpoints:
    """Integration tests for payment API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def auth_token(self):
        """Generate valid JWT token for authenticated requests."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(uuid.uuid4()),
            "email": f"test-{uuid.uuid4().hex[:8]}@example.com",
            "role": "authenticated",
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "iat": int(now.timestamp())
        }
        return jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        """Create Authorization header with JWT token."""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_create_checkout_session_success(self, client, auth_headers):
        """Test creating checkout session with valid data."""
        # Arrange
        plan_id = str(uuid.uuid4())
        
        with patch('app.infrastructure.payment.stripe_client.stripe.checkout.Session.create') as mock_create:
            mock_create.return_value = MagicMock(
                id="cs_test_123",
                url="https://checkout.stripe.com/pay/cs_test_123",
                expires_at=1234567890,
                payment_status="unpaid"
            )
            
            # Act
            response = client.post(
                "/payment/create-checkout-session",
                json={"plan_id": plan_id},
                headers=auth_headers,
                timeout=30
            )
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert "checkout_url" in data
            assert "session_id" in data
            assert "expires_at" in data
            assert data["session_id"] == "cs_test_123"
            assert "checkout.stripe.com" in data["checkout_url"]
    
    def test_create_checkout_session_no_auth_returns_401(self, client):
        """Test creating checkout session without auth returns 401."""
        # Arrange
        plan_id = str(uuid.uuid4())
        
        # Act
        response = client.post(
            "/payment/create-checkout-session",
            json={"plan_id": plan_id},
            timeout=30
        )
        
        # Assert
        assert response.status_code == 401
    
    def test_create_checkout_session_invalid_plan_id(self, client, auth_headers):
        """Test creating session with invalid plan_id format."""
        # Arrange
        invalid_plan_id = "not-a-uuid"
        
        # Act
        response = client.post(
            "/payment/create-checkout-session",
            json={"plan_id": invalid_plan_id},
            headers=auth_headers,
            timeout=30
        )
        
        # Assert
        # Should return 422 (validation error) or 400 (bad request)
        assert response.status_code in [400, 422]
    
    def test_get_session_status_success(self, client, auth_headers):
        """Test retrieving session status."""
        # Arrange
        session_id = "cs_test_456"
        
        with patch('app.infrastructure.payment.stripe_client.stripe.checkout.Session.retrieve') as mock_retrieve:
            mock_retrieve.return_value = MagicMock(
                id=session_id,
                payment_status="paid",
                status="complete",
                amount_total=1000,
                currency="usd"
            )
            
            # Act
            response = client.get(
                f"/payment/session/{session_id}/status",
                headers=auth_headers,
                timeout=30
            )
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["session_id"] == session_id
            assert data["payment_status"] == "paid"
            assert data["status"] == "complete"
    
    def test_get_session_status_no_auth_returns_401(self, client):
        """Test getting session status without auth returns 401."""
        # Arrange
        session_id = "cs_test_789"
        
        # Act
        response = client.get(
            f"/payment/session/{session_id}/status",
            timeout=30
        )
        
        # Assert
        assert response.status_code == 401
    
    def test_get_session_status_not_found(self, client, auth_headers):
        """Test retrieving non-existent session."""
        # Arrange
        session_id = "cs_test_nonexistent"
        
        with patch('app.infrastructure.payment.stripe_client.stripe.checkout.Session.retrieve') as mock_retrieve:
            import stripe
            mock_retrieve.side_effect = stripe.error.InvalidRequestError(
                message="No such checkout session",
                param="id"
            )
            
            # Act
            response = client.get(
                f"/payment/session/{session_id}/status",
                headers=auth_headers,
                timeout=30
            )
            
            # Assert
            assert response.status_code == 404


class TestWebhookEndpoint:
    """Tests for Stripe webhook endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_webhook_invalid_signature_returns_400(self, client):
        """Test webhook rejects requests with invalid signature."""
        # Arrange
        webhook_payload = {
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test_123"}}
        }
        invalid_signature = "invalid_signature_value"
        
        # Act
        response = client.post(
            "/payment/stripe/webhook",
            json=webhook_payload,
            headers={"stripe-signature": invalid_signature},
            timeout=30
        )
        
        # Assert
        assert response.status_code == 400
    
    def test_webhook_missing_signature_returns_400(self, client):
        """Test webhook rejects requests without signature header."""
        # Arrange
        webhook_payload = {
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test_123"}}
        }
        
        # Act
        response = client.post(
            "/payment/stripe/webhook",
            json=webhook_payload,
            timeout=30
        )
        
        # Assert
        assert response.status_code == 400
    
    def test_webhook_valid_signature_processes_event(self, client):
        """Test webhook processes event with valid signature."""
        # Arrange
        webhook_payload = '{"type":"checkout.session.completed","data":{"object":{"id":"cs_test_123"}}}'
        
        with patch('app.infrastructure.payment.stripe_client.stripe.Webhook.construct_event') as mock_construct:
            mock_event = {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_test_123",
                        "payment_status": "paid",
                        "amount_total": 1000,
                        "metadata": {"plan_id": str(uuid.uuid4())}
                    }
                }
            }
            mock_construct.return_value = mock_event
            
            with patch('app.infrastructure.repositories.payment_repository_postgresql.PaymentRepository.update_session_status') as mock_update:
                # Act
                response = client.post(
                    "/payment/stripe/webhook",
                    content=webhook_payload,
                    headers={"stripe-signature": "valid_signature"},
                    timeout=30
                )
                
                # Assert
                assert response.status_code == 200
                assert response.json()["status"] == "success"


class TestPaymentIntegration:
    """End-to-end integration tests for payment flow."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def auth_token(self):
        """Generate valid JWT token."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(uuid.uuid4()),
            "email": f"integration-{uuid.uuid4().hex[:8]}@test.com",
            "role": "authenticated",
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "iat": int(now.timestamp())
        }
        return jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        """Create auth headers."""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_complete_payment_flow(self, client, auth_headers):
        """Test complete flow: create session → webhook → check status."""
        # Arrange
        plan_id = str(uuid.uuid4())
        session_id = "cs_test_integration"
        
        with patch('app.infrastructure.payment.stripe_client.stripe.checkout.Session.create') as mock_create, \
             patch('app.infrastructure.payment.stripe_client.stripe.checkout.Session.retrieve') as mock_retrieve, \
             patch('app.infrastructure.payment.stripe_client.stripe.Webhook.construct_event') as mock_webhook:
            
            # Step 1: Create checkout session
            mock_create.return_value = MagicMock(
                id=session_id,
                url=f"https://checkout.stripe.com/pay/{session_id}",
                expires_at=1234567890,
                payment_status="unpaid"
            )
            
            response1 = client.post(
                "/payment/create-checkout-session",
                json={"plan_id": plan_id},
                headers=auth_headers,
                timeout=30
            )
            
            assert response1.status_code == 200
            assert response1.json()["session_id"] == session_id
            
            # Step 2: Simulate webhook (payment completed)
            webhook_event = {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": session_id,
                        "payment_status": "paid",
                        "amount_total": 1000,
                        "metadata": {"plan_id": plan_id}
                    }
                }
            }
            mock_webhook.return_value = webhook_event
            
            response2 = client.post(
                "/payment/stripe/webhook",
                content='{"type":"checkout.session.completed"}',
                headers={"stripe-signature": "valid"},
                timeout=30
            )
            
            assert response2.status_code == 200
            
            # Step 3: Check session status
            mock_retrieve.return_value = MagicMock(
                id=session_id,
                payment_status="paid",
                status="complete"
            )
            
            response3 = client.get(
                f"/payment/session/{session_id}/status",
                headers=auth_headers,
                timeout=30
            )
            
            assert response3.status_code == 200
            assert response3.json()["payment_status"] == "paid"
