# PDF z widoku Next.js (Playwright) — kontrakt frontu

## Endpoint (jedyny)

**POST** `/plan/render-pdf`

**Nagłówek (wymagany):**

`X-Render-Secret: <PDF_RENDER_SECRET>`

Ta sama wartość w env backendu (`PDF_RENDER_SECRET`) i na serwerze Next.js (Route Handler wołający backend). Front **nie** musi znać żadnego secretu do samego tokenu w URL — token jest **opaque** (losowy identyfikator sesji PDF po stronie frontu).

**Body:**

```json
{ "url": "https://<host>/plan/pdf/<opaque_token>" }
```

Backend:

1. Sprawdza `X-Render-Secret`
2. Sprawdza allowlistę hosta + ścieżkę `/plan/pdf/{token}`
3. **Nie** parsuje tokenu (brak JWT)
4. Playwright: `page.goto(url)` — jeśli **HTTP 404** → błąd (zły/wygasły token)
5. Czeka na `html[data-pdf-ready="true"]` (max 20 s)
6. Zwraca `application/pdf`

## Dozwolone hosty (domyślnie)

- `lets-travel.pl`, `www.lets-travel.pl`
- `letstravel-blue.vercel.app`
- `localhost`, `127.0.0.1`
- host z `FRONTEND_BASE_URL`
- hosty z `CORS_ORIGINS`
- dodatkowo: `PDF_RENDER_ALLOWED_HOSTS` (csv)

## Env na Renderze

```env
PDF_RENDER_SECRET=<wspólny z frontem — ten sam co w nagłówku X-Render-Secret>
FRONTEND_BASE_URL=https://lets-travel.pl
PDF_RENDER_WAIT_TIMEOUT_MS=20000
PDF_PLAYWRIGHT_ENABLED=true
```

Możesz zostawić `PDF_RENDER_JWT_SECRET` — backend użyje go **tylko** jako fallback, gdy `PDF_RENDER_SECRET` jest pusty (kompatybilność wsteczna).

## Usunięte (front ich nie woła)

- `POST /plan/{id}/pdf-render-token`
- `GET /plan/pdf-view/{token}`

Mintowanie tokenu i autoryzacja (właściciel + opłacony plan) — **wyłącznie na froncie**, przed wywołaniem render-pdf.

## Widok print w Next.js

Po załadowaniu fontów/obrazków:

```javascript
document.documentElement.setAttribute("data-pdf-ready", "true");
```

## Stary PDF

`GET /plan/{id}/pdf` (ReportLab) — bez zmian, fallback.
