"""
Short-lived JWT for print view / Playwright PDF render (FIX #236).

Token typ: pdf_render, TTL domyślnie 5 min (zgodnie z kontraktem frontu).
Secret: PDF_RENDER_JWT_SECRET (w prod wymagany); dev fallback tylko gdy DEBUG=true.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import jwt
from fastapi import HTTPException, status

from app.infrastructure.config.settings import settings

_PDF_RENDER_TYP = "pdf_render"
_TOKEN_PATH_RE = re.compile(r"^/plan/pdf/(?P<token>[^/?#]+)/?$")


def _signing_secret() -> str:
    secret = (settings.pdf_render_jwt_secret or "").strip()
    if secret:
        return secret
    legacy = (settings.supabase_jwt_secret or "").strip()
    if legacy:
        return legacy
    if settings.debug:
        return "dev-pdf-render-secret-change-me"
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="PDF render tokens are not configured (set PDF_RENDER_JWT_SECRET)",
    )


def create_pdf_render_token(plan_id: str) -> dict[str, Any]:
    """Mint token + metadata for frontend print URL."""
    if not plan_id or not str(plan_id).strip():
        raise ValueError("plan_id required")
    ttl = max(60, int(settings.pdf_render_token_ttl_sec or 300))
    now = datetime.now(timezone.utc)
    exp = now + timedelta(seconds=ttl)
    payload = {
        "typ": _PDF_RENDER_TYP,
        "plan_id": str(plan_id),
        "exp": int(exp.timestamp()),
        "iat": int(now.timestamp()),
    }
    token = jwt.encode(payload, _signing_secret(), algorithm="HS256")
    base = (settings.frontend_base_url or "").rstrip("/")
    if not base:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FRONTEND_BASE_URL is not configured",
        )
    url = f"{base}/plan/pdf/{token}"
    return {
        "token": token,
        "url": url,
        "expires_at": exp.isoformat(),
        "ttl_sec": ttl,
    }


def verify_pdf_render_token(token: str) -> str:
    """Validate token; return plan_id."""
    if not token or not str(token).strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing PDF render token")
    try:
        payload = jwt.decode(
            token,
            _signing_secret(),
            algorithms=["HS256"],
            options={"require_exp": True},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="PDF render token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid PDF render token: {e}",
        )
    if payload.get("typ") != _PDF_RENDER_TYP:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid PDF render token type")
    plan_id = payload.get("plan_id")
    if not plan_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="PDF render token missing plan_id")
    return str(plan_id)


def _allowed_hosts() -> set[str]:
    hosts: set[str] = set()
    base = (settings.frontend_base_url or "").strip()
    if base:
        h = urlparse(base).hostname
        if h:
            hosts.add(h.lower())
    for origin in settings.cors_origins or []:
        if isinstance(origin, str) and origin.strip() and origin != "*":
            h = urlparse(origin.strip()).hostname
            if h:
                hosts.add(h.lower())
    for extra in (settings.pdf_render_allowed_hosts or "").split(","):
        extra = extra.strip().lower()
        if extra:
            hosts.add(extra)
    return hosts


def validate_pdf_render_url(url: str) -> tuple[str, str]:
    """
    Validate client-supplied print URL. Returns (token, plan_id).
    Host must be allowlisted; path must be /plan/pdf/{token}.
    """
    if not url or not str(url).strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="url is required")
    parsed = urlparse(str(url).strip())
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="url must be http(s)")
    host = (parsed.hostname or "").lower()
    allowed = _allowed_hosts()
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PDF render URL allowlist is empty (configure FRONTEND_BASE_URL)",
        )
    if host not in allowed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="url host is not allowed")
    m = _TOKEN_PATH_RE.match(parsed.path or "")
    if not m:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="url path must be /plan/pdf/{token}",
        )
    token = m.group("token")
    plan_id = verify_pdf_render_token(token)
    return token, plan_id
