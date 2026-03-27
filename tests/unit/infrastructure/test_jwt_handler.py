"""
Unit tests for JWT token validation.
Tests decode_jwt and get_user_from_token functions.
"""
import pytest
import jwt
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException

from app.infrastructure.auth.jwt_handler import decode_jwt, get_user_from_token
from app.infrastructure.config.settings import settings


class TestDecodeJWT:
    """Test JWT decoding and validation."""
    
    def test_valid_jwt_token(self):
        """Test decoding valid JWT with all required claims."""
        # Arrange
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "user-123-abc",
            "email": "test@example.com",
            "role": "authenticated",
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "iat": int(now.timestamp())
        }
        token = jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")
        
        # Act
        decoded = decode_jwt(token)
        
        # Assert
        assert decoded["sub"] == "user-123-abc"
        assert decoded["email"] == "test@example.com"
        assert decoded["role"] == "authenticated"
        assert "exp" in decoded
        assert "iat" in decoded
    
    def test_expired_jwt_token(self):
        """Test expired JWT raises 401 Unauthorized."""
        # Arrange
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "exp": int((now - timedelta(hours=1)).timestamp()),  # Expired 1 hour ago
            "iat": int((now - timedelta(hours=2)).timestamp())
        }
        token = jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            decode_jwt(token)
        
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()
    
    def test_invalid_signature(self):
        """Test JWT with invalid signature raises 401."""
        # Arrange
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "exp": int((now + timedelta(hours=1)).timestamp())
        }
        # Sign with wrong secret
        token = jwt.encode(payload, "wrong-secret-key", algorithm="HS256")
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            decode_jwt(token)
        
        assert exc_info.value.status_code == 401
        assert "invalid" in exc_info.value.detail.lower()
    
    def test_malformed_jwt(self):
        """Test malformed JWT raises 401."""
        # Arrange
        malformed_token = "not.a.valid.jwt.token"
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            decode_jwt(malformed_token)
        
        assert exc_info.value.status_code == 401
    
    def test_jwt_without_expiration(self):
        """Test JWT without exp claim raises 401."""
        # Arrange
        payload = {
            "sub": "user-123",
            "email": "test@example.com"
            # Missing 'exp' claim
        }
        token = jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            decode_jwt(token)
        
        assert exc_info.value.status_code == 401


class TestGetUserFromToken:
    """Test extracting user info from JWT payload."""
    
    def test_extract_user_info_valid(self):
        """Test extracting user info from valid payload."""
        # Arrange
        payload = {
            "sub": "abc-123-xyz",
            "email": "user@example.com",
            "role": "authenticated"
        }
        
        # Act
        user_info = get_user_from_token(payload)
        
        # Assert
        assert user_info["supabase_id"] == "abc-123-xyz"
        assert user_info["email"] == "user@example.com"
        assert user_info["role"] == "authenticated"
    
    def test_missing_sub_claim(self):
        """Test payload without 'sub' raises 401."""
        # Arrange
        payload = {
            "email": "user@example.com",
            "role": "authenticated"
            # Missing 'sub'
        }
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            get_user_from_token(payload)
        
        assert exc_info.value.status_code == 401
        assert "sub" in exc_info.value.detail.lower()
    
    def test_missing_email_claim(self):
        """Test payload without 'email' raises 401."""
        # Arrange
        payload = {
            "sub": "user-123",
            "role": "authenticated"
            # Missing 'email'
        }
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            get_user_from_token(payload)
        
        assert exc_info.value.status_code == 401
        assert "email" in exc_info.value.detail.lower()
    
    def test_role_defaults_to_authenticated(self):
        """Test role defaults to 'authenticated' if not provided."""
        # Arrange
        payload = {
            "sub": "user-123",
            "email": "user@example.com"
            # Missing 'role'
        }
        
        # Act
        user_info = get_user_from_token(payload)
        
        # Assert
        assert user_info["role"] == "authenticated"


class TestJWTIntegration:
    """Integration tests for complete JWT flow."""
    
    def test_complete_jwt_validation_flow(self):
        """Test complete flow: encode → decode → extract user."""
        # Arrange
        now = datetime.now(timezone.utc)
        original_payload = {
            "sub": "integration-test-user",
            "email": "integration@test.com",
            "role": "authenticated",
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "iat": int(now.timestamp())
        }
        token = jwt.encode(original_payload, settings.supabase_jwt_secret, algorithm="HS256")
        
        # Act
        decoded_payload = decode_jwt(token)
        user_info = get_user_from_token(decoded_payload)
        
        # Assert
        assert user_info["supabase_id"] == "integration-test-user"
        assert user_info["email"] == "integration@test.com"
        assert user_info["role"] == "authenticated"
