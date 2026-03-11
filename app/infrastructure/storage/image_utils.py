"""
Image URL utilities for Supabase Storage.

Konwencja (11.03.2026 - confirmed by klientka):
- Bucket `destinations` - zdjęcia miast
- Bucket `poi` - zdjęcia atrakcji
- Format: WebP (.webp)
- Naming: zgodne z image_key (np. poi_morskie_oko.webp)
"""
from typing import Optional
from app.infrastructure.config.settings import settings


def build_image_url(bucket: str, image_key: str) -> Optional[str]:
    """
    Buduje pełny URL do obrazka w Supabase Storage.
    
    Args:
        bucket: Nazwa bucketu ('destinations' lub 'poi')
        image_key: Klucz obrazka (np. 'poi_morskie_oko' lub 'destination_zakopane')
    
    Returns:
        Pełny URL do obrazka lub None jeśli image_key pusty/None
    
    Example:
        >>> build_image_url('poi', 'poi_morskie_oko')
        'https://usztzcigcnsyyatguxay.supabase.co/storage/v1/object/public/poi/poi_morskie_oko.webp'
    """
    # Jeśli brak image_key - zwróć None (graceful handling)
    if not image_key or image_key == "":
        return None
    
    # Jeśli brak Supabase URL w config - zwróć None (fallback)
    if not settings.supabase_url:
        print(f"WARNING: SUPABASE_URL not configured, cannot build image URL for {image_key}")
        return None
    
    # Dodaj .webp extension jeśli nie ma
    if not image_key.endswith('.webp'):
        image_key_with_ext = f"{image_key}.webp"
    else:
        image_key_with_ext = image_key
    
    # Buduj URL: {supabase_url}/storage/v1/object/public/{bucket}/{image_key}.webp
    image_url = f"{settings.supabase_url}/storage/v1/object/public/{bucket}/{image_key_with_ext}"
    
    return image_url


def build_poi_image_url(image_key: str) -> Optional[str]:
    """
    Helper dla POI images - używa bucketu 'poi'.
    
    Args:
        image_key: Klucz obrazka POI (np. 'poi_morskie_oko')
    
    Returns:
        Pełny URL do obrazka POI lub None jeśli image_key pusty
    """
    return build_image_url('poi', image_key)


def build_destination_image_url(image_key: str) -> Optional[str]:
    """
    Helper dla destination images - używa bucketu 'destinations'.
    
    Args:
        image_key: Klucz obrazka destination (np. 'destination_zakopane')
    
    Returns:
        Pełny URL do obrazka destination lub None jeśli image_key pusty
    """
    return build_image_url('destinations', image_key)
