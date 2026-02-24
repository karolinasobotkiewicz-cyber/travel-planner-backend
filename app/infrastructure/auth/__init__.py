"""
Authentication module for ETAP 2.
Handles Supabase JWT validation and user management.
"""
from .jwt_handler import decode_jwt, get_user_from_token
from .supabase_client import get_supabase_client

__all__ = ["decode_jwt", "get_user_from_token", "get_supabase_client"]
