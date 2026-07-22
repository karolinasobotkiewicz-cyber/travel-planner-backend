"""
PDF render URL validation (FIX #236 / front contract update).

Opaque token in path — backend does NOT parse or verify token content.
Auth happens on frontend at mint time; this service only:
- allowlists print URL hosts
- validates path /plan/pdf/{opaque_token}
- Playwright checks HTTP status of the print page (404 = bad/expired token)
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from fastapi import HTTPException, status

from app.infrastructure.config.settings import settings

_TOKEN_PATH_RE = re.compile(r"^/plan/pdf/(?P<token>[^/?#]+)/?$")

# Domyślne hosty frontu (prod + staging Vercel + local dev)
_DEFAULT_PDF_HOSTS = frozenset({
    "lets-travel.pl",
    "www.lets-travel.pl",
    "letstravel-blue.vercel.app",
    "localhost",
    "127.0.0.1",
})


def pdf_render_shared_secret() -> str:
    """Secret for X-Render-Secret (PDF_RENDER_SECRET env)."""
    secret = (settings.pdf_render_secret or "").strip()
    if not secret:
        # Migracja: stara nazwa env u klienta/backendu
        secret = (settings.pdf_render_jwt_secret or "").strip()
    if secret:
        return secret
    if settings.debug:
        return "dev-pdf-render-secret-change-me"
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="PDF render is not configured (set PDF_RENDER_SECRET)",
    )


def verify_x_render_secret(header_value: str | None) -> None:
    if not header_value or not str(header_value).strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Render-Secret header",
        )
    expected = pdf_render_shared_secret()
    if header_value.strip() != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid X-Render-Secret",
        )


def _allowed_hosts() -> set[str]:
    hosts: set[str] = set(_DEFAULT_PDF_HOSTS)
    base = (settings.frontend_base_url or "").strip()
    if base:
        h = urlparse(base).hostname
        if h:
            hosts.add(h.lower())
    origins = settings.cors_origins
    if isinstance(origins, str):
        origins = [o.strip() for o in origins.split(",") if o.strip()]
    for origin in origins or []:
        if isinstance(origin, str) and origin.strip() and origin != "*":
            h = urlparse(origin.strip()).hostname
            if h:
                hosts.add(h.lower())
    for extra in (settings.pdf_render_allowed_hosts or "").split(","):
        extra = extra.strip().lower()
        if extra:
            hosts.add(extra)
    return hosts


def validate_pdf_render_url(url: str) -> str:
    """
    Validate client-supplied print URL. Returns opaque token from path.
    Does not inspect token payload.
    """
    if not url or not str(url).strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="url is required")
    parsed = urlparse(str(url).strip())
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="url must be http(s)")
    host = (parsed.hostname or "").lower()
    allowed = _allowed_hosts()
    if host not in allowed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="url host is not allowed")
    m = _TOKEN_PATH_RE.match(parsed.path or "")
    if not m:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="url path must be /plan/pdf/{token}",
        )
    token = (m.group("token") or "").strip()
    if len(token) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="url token is too short")
    return token
