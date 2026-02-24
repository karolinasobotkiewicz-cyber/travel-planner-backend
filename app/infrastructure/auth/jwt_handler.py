"""
JWT token validation for Supabase authentication.
Handles decoding, verification, and user extraction from JWT tokens.
"""
import jwt
from datetime import datetime
from typing import Dict
from fastapi import HTTPException, status
from app.infrastructure.config.settings import settings


def decode_jwt(token: str) -> Dict:
    """
    Decode and validate Supabase JWT token.
    
    Supabase uses HS256 algorithm with a shared secret.
    Token structure includes:
    - sub: User ID (Supabase UUID)
    - email: User email
    - role: User role (anon, authenticated, service_role)
    - exp: Expiration timestamp
    - iat: Issued at timestamp
    
    Args:
        token: JWT token string (without 'Bearer ' prefix)
    
    Returns:
        Decoded token payload with user info
        
    Raises:
        HTTPException 401: If token is invalid, expired, or malformed
        
    Example:
        token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        payload = decode_jwt(token)
        user_id = payload["sub"]
        email = payload["email"]
    """
    if not settings.supabase_jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT secret not configured"
        )
    
    try:
        # Decode JWT using Supabase JWT secret
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            options={
                "verify_aud": False,  # Supabase doesn't use aud claim
                "verify_signature": True,
                "verify_exp": True,
                "require_exp": True
            }
        )
        
        # Additional expiration check (redundant but explicit)
        exp = payload.get("exp")
        if exp and datetime.fromtimestamp(exp) < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return payload
    
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    except Exception as e:
        # Catch any other unexpected errors
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication error: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_user_from_token(payload: Dict) -> Dict:
    """
    Extract user information from decoded JWT payload.
    
    Supabase JWT payload structure:
    {
        "sub": "user-uuid-here",
        "email": "user@example.com",
        "role": "authenticated",
        "iat": 1234567890,
        "exp": 1234571490
    }
    
    Args:
        payload: Decoded JWT payload from decode_jwt()
    
    Returns:
        Dictionary with user info:
        {
            "supabase_id": "user-uuid",
            "email": "user@example.com",
            "role": "authenticated"
        }
        
    Raises:
        HTTPException 401: If required fields missing from payload
        
    Example:
        payload = decode_jwt(token)
        user_info = get_user_from_token(payload)
        print(user_info["email"])
    """
    # Validate required fields
    supabase_id = payload.get("sub")
    email = payload.get("email")
    
    if not supabase_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user ID (sub claim)",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing email claim",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {
        "supabase_id": supabase_id,
        "email": email,
        "role": payload.get("role", "authenticated"),
    }
