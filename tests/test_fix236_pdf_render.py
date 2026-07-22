"""FIX #236 / front contract — opaque PDF token + X-Render-Secret."""
from __future__ import annotations

import os

import pytest
from fastapi import HTTPException

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("DEBUG", "true")

from app.infrastructure.config.settings import settings  # noqa: E402
from app.infrastructure.pdf.pdf_render_token import (  # noqa: E402
    validate_pdf_render_url,
    verify_x_render_secret,
)


def test_validate_vercel_host_allowed():
    settings.pdf_render_allowed_hosts = ""
    url = (
        "https://letstravel-blue.vercel.app/plan/pdf/"
        "7e23ff2e42ad4b70b7c86918d5867d2cf065b73142729dc52e81712d96743e50"
    )
    token = validate_pdf_render_url(url)
    assert token.startswith("7e23ff2e")


def test_validate_prod_host_allowed():
    url = "https://lets-travel.pl/plan/pdf/abc1234567890abcdef"
    token = validate_pdf_render_url(url)
    assert token == "abc1234567890abcdef"


def test_validate_rejects_unknown_host():
    with pytest.raises(HTTPException) as exc:
        validate_pdf_render_url("https://evil.example/plan/pdf/abc12345678")
    assert exc.value.status_code == 400


def test_opaque_token_not_jwt_parsed():
    """Long hex token must pass without JWT secret configured."""
    settings.pdf_render_secret = "test-secret"
    settings.pdf_render_jwt_secret = ""
    url = "https://localhost:3000/plan/pdf/" + ("a" * 64)
    assert validate_pdf_render_url(url) == "a" * 64


def test_x_render_secret_required():
    settings.pdf_render_secret = "front-backend-shared"
    with pytest.raises(HTTPException) as exc:
        verify_x_render_secret(None)
    assert exc.value.status_code == 401
    verify_x_render_secret("front-backend-shared")


def test_x_render_secret_wrong():
    settings.pdf_render_secret = "right"
    with pytest.raises(HTTPException) as exc:
        verify_x_render_secret("wrong")
    assert exc.value.status_code == 401


def test_render_pdf_endpoint_requires_secret(monkeypatch):
    from app.api.routes.plan import RenderPdfRequest, render_plan_pdf_from_url

    settings.pdf_render_secret = "s3cret"
    url = "https://lets-travel.pl/plan/pdf/abc12345678901"

    with pytest.raises(HTTPException) as exc:
        render_plan_pdf_from_url(RenderPdfRequest(url=url), x_render_secret=None)
    assert exc.value.status_code == 401

    def _fake_render(u: str) -> bytes:
        return b"%PDF-fake"

    monkeypatch.setattr("app.api.routes.plan.render_url_to_pdf", _fake_render)
    resp = render_plan_pdf_from_url(RenderPdfRequest(url=url), x_render_secret="s3cret")
    assert resp.body[:4] == b"%PDF"


def test_render_url_to_pdf_mocked(monkeypatch):
    from app.infrastructure.pdf import playwright_renderer as pr

    settings.pdf_playwright_enabled = True

    class _FakeResponse:
        status = 200

    class _FakePage:
        def goto(self, url, wait_until=None, timeout=None):
            assert "plan/pdf/" in url
            return _FakeResponse()

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

    import playwright.sync_api as sync_api

    monkeypatch.setattr(sync_api, "sync_playwright", lambda: _FakePW())
    out = pr.render_url_to_pdf("https://lets-travel.pl/plan/pdf/fake-token-12345678")
    assert out == b"%PDF-mocked"


def test_render_url_404_raises(monkeypatch):
    from app.infrastructure.pdf import playwright_renderer as pr

    settings.pdf_playwright_enabled = True

    class _FakeResponse:
        status = 404

    class _FakePage:
        def goto(self, url, wait_until=None, timeout=None):
            return _FakeResponse()

        def wait_for_selector(self, *a, **k):
            pass

        def pdf(self, **kwargs):
            return b""

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

    import playwright.sync_api as sync_api

    monkeypatch.setattr(sync_api, "sync_playwright", lambda: _FakePW())
    with pytest.raises(HTTPException) as exc:
        pr.render_url_to_pdf("https://lets-travel.pl/plan/pdf/bad")
    assert exc.value.status_code == 401
