"""
Configuration management using Pydantic Settings.
Zarządza env variables i konfiguracją aplikacji.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Optional, Union


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
    # W przyszłości: google_maps_api_key, etc.

    # =========================
    # SUPABASE AUTH (ETAP 2)
    # =========================

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""

    # =========================
    # STRIPE PAYMENT (ETAP 2)
    # =========================

    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_price_id: str = ""
    stripe_webhook_secret: str = ""  # Dodamy po deployment

    # =========================
    # DATABASE (ETAP 2)
    # =========================

    database_url: Optional[str] = None
    # Na razie in-memory, ETAP 2: PostgreSQL

    # =========================
    # CORS
    # =========================

    cors_origins: Union[list[str], str] = ["*"]
    # Produkcja: konkretne domeny frontendu
    
    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS_ORIGINS from string or keep as list."""
        if isinstance(v, str):
            # Split by comma and strip whitespace
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        return v

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
