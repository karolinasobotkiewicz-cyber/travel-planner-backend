"""
Unit tests for authentication dependencies.
Tests get_current_user and get_optional_user functions.
"""
import pytest
import uuid
from unittest.mock import Mock, patch, MagicMock
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.dependencies import get_current_user, get_optional_user
from app.infrastructure.database.models import User


class TestGetCurrentUser:
    """Test get_current_user dependency."""
    
    @pytest.mark.asyncio
    async def test_valid_token_existing_user(self):
        """Test authentication with valid token for existing user."""
        # Arrange
        mock_credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="valid-jwt-token"
        )
        
        existing_user = User(
            id=uuid.uuid4(),
            supabase_id="user-123",
            email="existing@example.com"
        )
        
        mock_db = MagicMock()
        mock_db.query().filter().first.return_value = existing_user
        
        with patch('app.api.dependencies.decode_jwt') as mock_decode, \
             patch('app.api.dependencies.get_user_from_token') as mock_get_user:
            
            mock_decode.return_value = {
                "sub": "user-123",
                "email": "existing@example.com"
            }
            mock_get_user.return_value = {
                "supabase_id": "user-123",
                "email": "existing@example.com"
            }
            
            # Act
            result = await get_current_user(mock_credentials, mock_db)
            
            # Assert
            assert result == existing_user
            assert result.supabase_id == "user-123"
            assert result.email == "existing@example.com"
    
    @pytest.mark.asyncio
    async def test_valid_token_new_user_auto_create(self):
        """Test auto-creating user on first valid auth request."""
        # Arrange
        mock_credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="valid-jwt-token"
        )
        
        mock_db = MagicMock()
        mock_db.query().filter().first.return_value = None  # User doesn't exist
        
        with patch('app.api.dependencies.decode_jwt') as mock_decode, \
             patch('app.api.dependencies.get_user_from_token') as mock_get_user:
            
            mock_decode.return_value = {
                "sub": "new-user-456",
                "email": "newuser@example.com"
            }
            mock_get_user.return_value = {
                "supabase_id": "new-user-456",
                "email": "newuser@example.com"
            }
            
            # Mock the created user
            new_user = User(
                id=uuid.uuid4(),
                supabase_id="new-user-456",
                email="newuser@example.com"
            )
            
            def mock_refresh(user):
                user.id = new_user.id
            
            mock_db.refresh = mock_refresh
            
            # Act
            result = await get_current_user(mock_credentials, mock_db)
            
            # Assert
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            # User was created
            added_user = mock_db.add.call_args[0][0]
            assert added_user.supabase_id == "new-user-456"
            assert added_user.email == "newuser@example.com"
    
    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self):
        """Test invalid token raises HTTPException 401."""
        # Arrange
        mock_credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="invalid-token"
        )
        mock_db = MagicMock()
        
        with patch('app.api.dependencies.decode_jwt') as mock_decode:
            mock_decode.side_effect = HTTPException(
                status_code=401,
                detail="Invalid token"
            )
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_credentials, mock_db)
            
            assert exc_info.value.status_code == 401
    
    @pytest.mark.asyncio
    async def test_expired_token_raises_401(self):
        """Test expired token raises HTTPException 401."""
        # Arrange
        mock_credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="expired-token"
        )
        mock_db = MagicMock()
        
        with patch('app.api.dependencies.decode_jwt') as mock_decode:
            mock_decode.side_effect = HTTPException(
                status_code=401,
                detail="Token expired"
            )
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_credentials, mock_db)
            
            assert exc_info.value.status_code == 401
            assert "expired" in exc_info.value.detail.lower()


class TestGetOptionalUser:
    """Test get_optional_user dependency for optional auth."""
    
    @pytest.mark.asyncio
    async def test_no_credentials_returns_none(self):
        """Test that missing credentials returns None (not error)."""
        # Arrange
        mock_db = MagicMock()
        
        # Act
        result = await get_optional_user(credentials=None, db=mock_db)
        
        # Assert
        assert result is None
    
    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self):
        """Test valid token returns User instance."""
        # Arrange
        mock_credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="valid-token"
        )
        
        expected_user = User(
            id=uuid.uuid4(),
            supabase_id="user-789",
            email="optional@example.com"
        )
        
        mock_db = MagicMock()
        
        with patch('app.api.dependencies.get_current_user') as mock_get_current:
            mock_get_current.return_value = expected_user
            
            # Act
            result = await get_optional_user(mock_credentials, mock_db)
            
            # Assert
            assert result == expected_user
            assert result.email == "optional@example.com"
    
    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self):
        """Test invalid token raises 401 (not returns None)."""
        # Arrange
        mock_credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="invalid-token"
        )
        mock_db = MagicMock()
        
        with patch('app.api.dependencies.get_current_user') as mock_get_current:
            mock_get_current.side_effect = HTTPException(
                status_code=401,
                detail="Invalid token"
            )
            
            # Act & Assert
            # get_optional_user should let the exception propagate (not catch it)
            with pytest.raises(HTTPException) as exc_info:
                await get_optional_user(mock_credentials, mock_db)
            
            assert exc_info.value.status_code == 401
    
    @pytest.mark.asyncio
    async def test_expired_token_raises_401(self):
        """Test expired token raises 401 (security requirement)."""
        # Arrange
        mock_credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="expired-token"
        )
        mock_db = MagicMock()
        
        with patch('app.api.dependencies.get_current_user') as mock_get_current:
            mock_get_current.side_effect = HTTPException(
                status_code=401,
                detail="Token expired"
            )
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await get_optional_user(mock_credentials, mock_db)
            
            assert exc_info.value.status_code == 401
