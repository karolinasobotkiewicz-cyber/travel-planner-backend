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
    # OpenRouteService (FIX #220)
    ors_api_key: str = ""
    ors_enabled: bool = False
    ors_routing_enabled: bool = True
    ors_matrix_enabled: bool = True
    ors_poi_supplement_enabled: bool = False
    ors_cache_ttl_days: int = 60
    ors_daily_budget_directions: int = 1500
    ors_daily_budget_matrix: int = 120
    ors_matrix_max_locations: int = 8
    ors_overpass_radius_m: int = 2500

    # =========================
    # SUPABASE AUTH (ETAP 2)
    # =========================

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""  # Legacy HS256 secret (deprecated)
    supabase_jwt_public_key: str = ""  # ES256 public key (recommended)

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
    # PLAN ACCESS CONTROL (01.07.2026 - front feedback)
    # =========================

    # Gdy True: GET /plan/{id} blokuje nieopłacone plany dla osób innych niż
    # właściciel (paywall). Zwraca 402 Payment Required. Domyślnie ON — to
    # bezpośrednio zamyka lukę zgłoszoną przez frontowca (podgląd nieopłaconego
    # planu przez zmianę URL). Właściciel (auth/guest) zawsze widzi swój plan.
    enforce_plan_payment: bool = True

    # Gdy True: plany przypisane do konta (user_id / is_assigned) wymagają zalogowania
    # jako właściciel (401 dla obcych). Włączone domyślnie — front testuje z tokenem
    # Bearer przy GET /plan/{id}. Wyłącz env ENFORCE_ASSIGNED_PLAN_AUTH=false jeśli potrzeba.
    enforce_assigned_plan_auth: bool = True

    # =========================
    # PDF RENDER (Playwright + short-lived token) — FIX #236
    # =========================

    frontend_base_url: str = "https://lets-travel.pl"
    pdf_render_jwt_secret: str = ""
    pdf_render_token_ttl_sec: int = 300  # 5 min — kontrakt klientki
    pdf_render_wait_timeout_ms: int = 20000
    pdf_playwright_enabled: bool = True
    # Dodatkowe hosty (csv), np. staging: pdf_render_allowed_hosts=preview.lets-travel.pl

    pdf_render_allowed_hosts: str = ""

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
