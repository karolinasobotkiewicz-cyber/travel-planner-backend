"""
Supabase client wrapper for admin operations.
Singleton pattern for efficient connection reuse.
"""
from functools import lru_cache
from supabase import create_client, Client
from app.infrastructure.config.settings import settings


@lru_cache()
def get_supabase_client() -> Client:
    """
    Get singleton Supabase client.
    
    Used for admin operations like:
    - User verification
    - Profile updates
    - RLS policy checks (future)
    
    Returns:
        Supabase Client instance
        
    Raises:
        ValueError: If Supabase credentials not configured
        
    Example:
        supabase = get_supabase_client()
        user = supabase.auth.get_user(jwt_token)
    """
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise ValueError(
            "Supabase credentials not configured. "
            "Please set SUPABASE_URL and SUPABASE_ANON_KEY in .env"
        )
    
    return create_client(settings.supabase_url, settings.supabase_anon_key)
