"""
Weather API client.
Używa OpenWeather API do pobierania prognozy pogody.
"""
import requests
from datetime import datetime
from typing import Dict, Any
from app.infrastructure.config import settings


def get_weather(lat: float, lng: float, date: str) -> Dict[str, Any]:
    """
    Pobiera prognozę pogody dla lokalizacji i daty.

    Args:
        lat: Szerokość geograficzna
        lng: Długość geograficzna
        date: Data w formacie 'YYYY-MM-DD'

    Returns:
        Dict z kluczami: temp (float), precip (bool), wind (float)
    """
    url = (
        f"https://api.openweathermap.org/data/3.0/onecall"
        f"?lat={lat}&lon={lng}"
        f"&units=metric"
        f"&exclude=minutely,alerts"
        f"&appid={settings.openweather_api_key}"
    )

    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        print(f"Weather API error: {e}")
        # Fallback na domyślne wartości
        return {"temp": 15.0, "precip": False, "wind": 0.0}

    target = datetime.strptime(date, "%Y-%m-%d").date()

    for day in data.get("daily", []):
        d = datetime.fromtimestamp(day["dt"]).date()
        if d == target:
            temp = day["temp"]["day"]
            wind = day.get("wind_speed", 0)
            precip = ("rain" in day and day["rain"] > 0) or (
                "snow" in day and day["snow"] > 0
            )

            return {
                "temp": float(temp),
                "precip": bool(precip),
                "wind": float(wind),
            }

    # Jeśli nie znaleziono dnia - domyślne wartości
    return {"temp": 15.0, "precip": False, "wind": 0.0}
