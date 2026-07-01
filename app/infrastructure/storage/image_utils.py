"""
Image URL utilities for Supabase Storage.

Konwencja (11.03.2026 - confirmed by klientka):
- Bucket `destinations` - zdjęcia miast
- Bucket `poi` - zdjęcia atrakcji
- Bucket `restaurants` - zdjęcia restauracji
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
    # Graceful handling: brak image_key / None / pandas NaN / "nan" / "null".
    # FIX (01.07.2026 - front feedback): image_key bywa float NaN z Excela albo
    # napisem "NaN" — dawało to błędny URL ".../NaN.webp". Normalizujemy wejście.
    if image_key is None:
        return None
    key = str(image_key).strip()
    if not key or key.lower() in ("nan", "none", "null"):
        return None

    # Jeśli brak Supabase URL w config - zwróć None (fallback)
    if not settings.supabase_url:
        print(f"WARNING: SUPABASE_URL not configured, cannot build image URL for {key}")
        return None

    # FIX (01.07.2026 - front feedback): image_key w bazie bywa z rozszerzeniem
    # (np. "destination_wroclaw.jpg"), a w Supabase pliki są w .webp. Poprzednio
    # doklejaliśmy ".webp" na ślepo → "destination_wroclaw.jpg.webp" (404).
    # Zdejmujemy dowolne znane rozszerzenie obrazka i dopiero doklejamy .webp.
    lower_key = key.lower()
    for ext in (".webp", ".jpg", ".jpeg", ".png", ".gif", ".bmp"):
        if lower_key.endswith(ext):
            key = key[: -len(ext)]
            break

    # Buduj URL: {supabase_url}/storage/v1/object/public/{bucket}/{image_key}.webp
    image_url = (
        f"{settings.supabase_url}/storage/v1/object/public/"
        f"{bucket}/{key}.webp"
    )

    return image_url


def normalize_image_key(image_key) -> Optional[str]:
    """
    Zwraca czysty image_key (bez rozszerzenia), spójny z image_url.

    Obsługuje None / pandas NaN / "NaN" / puste → None, oraz zdejmuje
    znane rozszerzenia obrazków. Dzięki temu API zwraca image_key i
    image_url wskazujące na ten sam plik .webp w Supabase.
    """
    if image_key is None:
        return None
    key = str(image_key).strip()
    if not key or key.lower() in ("nan", "none", "null"):
        return None
    lower_key = key.lower()
    for ext in (".webp", ".jpg", ".jpeg", ".png", ".gif", ".bmp"):
        if lower_key.endswith(ext):
            return key[: -len(ext)]
    return key


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


def build_restaurant_image_url(image_key: str) -> Optional[str]:
    """
    Helper dla restaurant images - używa bucketu 'restaurants'.
    """
    return build_image_url('restaurants', image_key)
