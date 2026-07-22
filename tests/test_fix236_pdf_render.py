"""FIX #236 — Playwright PDF render contract (token + URL validation)."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("FRONTEND_BASE_URL", "https://lets-travel.pl")

from app.infrastructure.config.settings import settings  # noqa: E402
from app.infrastructure.pdf.pdf_render_token import (  # noqa: E402
    create_pdf_render_token,
    validate_pdf_render_url,
    verify_pdf_render_token,
)


def _secret() -> str:
    return (settings.pdf_render_jwt_secret or "").strip() or "dev-pdf-render-secret-change-me"


def test_create_and_verify_token_roundtrip():
    settings.pdf_render_jwt_secret = "test-fix236-secret"
    settings.frontend_base_url = "https://lets-travel.pl"
    meta = create_pdf_render_token("11111111-2222-3333-4444-555555555555")
    assert meta["ttl_sec"] == 300
    assert meta["url"].startswith("https://lets-travel.pl/plan/pdf/")
    plan_id = verify_pdf_render_token(meta["token"])
    assert plan_id == "11111111-2222-3333-4444-555555555555"


def test_expired_token_rejected():
    settings.pdf_render_jwt_secret = "test-fix236-secret"
    secret = "test-fix236-secret"
    exp = datetime.now(timezone.utc) - timedelta(minutes=1)
    token = jwt.encode(
        {
            "typ": "pdf_render",
            "plan_id": "abc",
            "exp": int(exp.timestamp()),
            "iat": int(exp.timestamp()) - 60,
        },
        secret,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as exc:
        verify_pdf_render_token(token)
    assert exc.value.status_code == 401


def test_validate_pdf_render_url_ok():
    settings.pdf_render_jwt_secret = "test-fix236-secret"
    settings.frontend_base_url = "https://lets-travel.pl"
    meta = create_pdf_render_token("plan-uuid-1")
    _tok, plan_id = validate_pdf_render_url(meta["url"])
    assert plan_id == "plan-uuid-1"


def test_validate_pdf_render_url_rejects_foreign_host():
    settings.pdf_render_jwt_secret = "test-fix236-secret"
    settings.frontend_base_url = "https://lets-travel.pl"
    meta = create_pdf_render_token("plan-uuid-1")
    bad = meta["url"].replace("lets-travel.pl", "evil.example")
    with pytest.raises(HTTPException) as exc:
        validate_pdf_render_url(bad)
    assert exc.value.status_code == 400


def test_validate_pdf_render_url_rejects_bad_path():
    settings.pdf_render_jwt_secret = "test-fix236-secret"
    settings.frontend_base_url = "https://lets-travel.pl"
    with pytest.raises(HTTPException) as exc:
        validate_pdf_render_url("https://lets-travel.pl/plan/abc")
    assert exc.value.status_code == 400


def test_render_url_to_pdf_mocked(monkeypatch):
    from app.infrastructure.pdf import playwright_renderer as pr

    settings.pdf_playwright_enabled = True

    class _FakePage:
        def goto(self, url, wait_until=None, timeout=None):
            assert "plan/pdf/" in url

        def wait_for_selector(self, selector, timeout=None):
            assert selector == 'html[data-pdf-ready="true"]'

        def pdf(self, **kwargs):
            return b"%PDF-mocked"

    class _FakeBrowser:
        def new_page(self):
            return _FakePage()

        def close(self):
            pass

    class _FakeChromium:
        def launch(self, headless=True):
            return _FakeBrowser()

    class _FakePW:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        @property
        def chromium(self):
            return _FakeChromium()

    def _fake_sync_playwright():
        return _FakePW()

    import playwright.sync_api as sync_api

    monkeypatch.setattr(sync_api, "sync_playwright", _fake_sync_playwright)
    out = pr.render_url_to_pdf("https://lets-travel.pl/plan/pdf/fake-token")
    assert out == b"%PDF-mocked"


def test_render_pdf_endpoint(monkeypatch):
    from app.api.routes.plan import RenderPdfRequest, render_plan_pdf_from_url

    settings.pdf_render_jwt_secret = "test-fix236-secret"
    settings.frontend_base_url = "https://lets-travel.pl"
    settings.pdf_playwright_enabled = True

    meta = create_pdf_render_token("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

    def _fake_render(url: str) -> bytes:
        assert url == meta["url"]
        return b"%PDF-endpoint"

    monkeypatch.setattr(
        "app.api.routes.plan.render_url_to_pdf",
        _fake_render,
    )

    resp = render_plan_pdf_from_url(RenderPdfRequest(url=meta["url"]))
    assert resp.body[:4] == b"%PDF"
    assert resp.media_type == "application/pdf"
