"""
Playwright headless print → PDF (FIX #236).

Wymaga: pip install playwright && playwright install chromium
Na Render: obraz Docker z Chromium lub buildpack z zależnościami Playwright.
"""
from __future__ import annotations

from fastapi import HTTPException, status

from app.infrastructure.config.settings import settings

_PDF_READY_SELECTOR = 'html[data-pdf-ready="true"]'


def render_url_to_pdf(url: str) -> bytes:
    """Open print URL and return PDF bytes."""
    if not settings.pdf_playwright_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Playwright PDF render is disabled",
        )
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Playwright is not installed on this server",
        ) from e

    timeout_ms = max(5000, int(settings.pdf_render_wait_timeout_ms or 20000))

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                status_code = response.status if response else 0
                if status_code >= 400:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED
                        if status_code == 404
                        else status.HTTP_502_BAD_GATEWAY,
                        detail=(
                            "PDF print page not available (invalid or expired token)"
                            if status_code == 404
                            else f"PDF print page returned HTTP {status_code}"
                        ),
                    )
                page.wait_for_selector(_PDF_READY_SELECTOR, timeout=timeout_ms)
                pdf_bytes = page.pdf(
                    format="A4",
                    print_background=True,
                    margin={"top": "12mm", "bottom": "12mm", "left": "10mm", "right": "10mm"},
                )
            finally:
                browser.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"PDF render failed: {e}",
        ) from e

    if not pdf_bytes:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="PDF render produced empty output",
        )
    return pdf_bytes
