"""
Geocoding API client.
Używa OpenWeather Geocoding API do konwersji nazw miast na współrzędne.
"""
import requests
from typing import Optional, Tuple
from app.infrastructure.config import settings


def geocode(city: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Konwertuje nazwę miasta na współrzędne geograficzne.

    Args:
        city: Nazwa miasta

    Returns:
        Tuple (lat, lng) lub (None, None) w przypadku błędu
    """
    url = (
        "https://api.openweathermap.org/geo/1.0/direct"
        f"?q={city}&limit=1&appid={settings.openweather_api_key}"
    )

    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        print(f"Geocoding API error: {e}")
        return None, None

    # Jeśli API zwróciło błąd (dict), a nie listę
    if not isinstance(data, list):
        print(f"Geocoding error: {data}")
        return None, None

    if len(data) == 0:
        print(f"City not found: {city}")
        return None, None

    lat = data[0].get("lat")
    lon = data[0].get("lon")

    return lat, lon
