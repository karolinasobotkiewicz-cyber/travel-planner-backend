"""
JWT token validation for Supabase authentication.
Handles decoding, verification, and user extraction from JWT tokens.
"""
import jwt
from datetime import datetime
from typing import Dict
from fastapi import HTTPException, status
from app.infrastructure.config.settings import settings


def _normalize_pem_key(key: str) -> str:
    """
    Normalize PEM key format by replacing literal \\n with actual newlines.
    
    Environment variables (especially from Render) may contain literal \\n 
    characters instead of actual newlines. This function fixes that.
    
    Args:
        key: PEM key string (may contain literal \\n or actual newlines)
        
    Returns:
        Normalized PEM key with actual newline characters
        
    Example:
        Input:  "-----BEGIN PUBLIC KEY-----\\nMFkw...\\n-----END PUBLIC KEY-----"
        Output: "-----BEGIN PUBLIC KEY-----\nMFkw...\n-----END PUBLIC KEY-----"
    """
    # Replace literal \\n with actual newlines
    # This handles cases where env vars contain escaped newlines
    if "\\n" in key:
        key = key.replace("\\n", "\n")
    
    # Remove any quotes that might have been added by env var parsing
    key = key.strip('"').strip("'")
    
    return key


def decode_jwt(token: str) -> Dict:
    """
    Decode and validate Supabase JWT token.
    
    Supports both ES256 (recommended, default for new Supabase projects) 
    and HS256 (legacy) algorithms.
    
    ES256 uses asymmetric cryptography with a public key for verification.
    HS256 uses symmetric cryptography with a shared secret.
    
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
        HTTPException 500: If neither public key nor secret is configured
        
    Example:
        token = "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9..."
        payload = decode_jwt(token)
        user_id = payload["sub"]
        email = payload["email"]
    """
    # Determine which key/algorithm to use
    if settings.supabase_jwt_public_key:
        # ES256 (recommended): Use public key for verification
        # Normalize the key format (replace literal \n with actual newlines)
        key = _normalize_pem_key(settings.supabase_jwt_public_key)
        algorithms = ["ES256"]
    elif settings.supabase_jwt_secret:
        # HS256 (legacy): Use shared secret
        key = settings.supabase_jwt_secret
        algorithms = ["HS256"]
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT verification key not configured (need SUPABASE_JWT_PUBLIC_KEY or SUPABASE_JWT_SECRET)"
        )
    
    try:
        # Decode JWT using configured key and algorithm
        payload = jwt.decode(
            token,
            key,
            algorithms=algorithms,
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
