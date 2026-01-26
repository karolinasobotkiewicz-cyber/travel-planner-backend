"""
Configuration management using Pydantic Settings.
Zarządza env variables i konfiguracją aplikacji.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """
    Globalne ustawienia aplikacji.
    Wczytuje wartości z .env file i environment variables.
    """

    # =========================
    # APP CONFIG
    # =========================

    app_name: str = "Travel Planner API"
    app_version: str = "1.0.0"
    debug: bool = False

    # =========================
    # API KEYS
    # =========================

    openweather_api_key: str = ""
    # W przyszłości: stripe_secret_key, google_maps_api_key, etc.

    # =========================
    # DATABASE (ETAP 2)
    # =========================

    database_url: Optional[str] = None
    # Na razie in-memory, ETAP 2: PostgreSQL

    # =========================
    # CORS
    # =========================

    cors_origins: list[str] = ["*"]
    # Produkcja: konkretne domeny frontendu

    # =========================
    # PLANNER CONFIG
    # =========================

    default_day_start: str = "09:00"
    default_day_end: str = "19:00"
    lunch_time: str = "12:00"
    lunch_duration_min: int = 90
    parking_duration_min: int = 15

    # =========================
    # PYDANTIC SETTINGS CONFIG
    # =========================

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Singleton instance
settings = Settings()
