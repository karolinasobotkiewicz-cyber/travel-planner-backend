# PDF z widoku Next.js (Playwright) — FIX #236

Backend gotowy pod kontrakt frontu (lipiec 2026). Stary endpoint ReportLab (`GET /plan/{id}/pdf`) nadal działa jako fallback.

## Flow (docelowy)

1. Użytkownik klika **Generuj PDF** w aplikacji.
2. Front buduje krótkotrwały token (5 min) i URL print view:  
   `https://lets-travel.pl/plan/pdf/<token>`
3. Front woła backend:  
   **`POST /plan/render-pdf`**  
   Body: `{ "url": "https://lets-travel.pl/plan/pdf/<token>" }`
4. Backend (Playwright) otwiera ten URL, czeka na gotowość strony, zwraca **`application/pdf`**.

## Widok print w Next.js (`/plan/pdf/[token]`)

1. Pobierz plan: **`GET /plan/pdf-view/{token}`** (ten sam JWT co w URL).  
   Odpowiedź: pełny `PlanResponse` (jak `GET /plan/{id}`), bez sesji użytkownika — autoryzacja = ważny token.
2. Wyrenderuj layout 1:1 jak w aplikacji (fonty, obrazki).
3. Gdy wszystko załadowane:

```javascript
document.documentElement.setAttribute("data-pdf-ready", "true");
```

Backend czeka max **20 s** na selektor: `html[data-pdf-ready="true"]`.

## Token JWT (wspólny secret z backendem)

- Algorytm: **HS256**
- Secret: env **`PDF_RENDER_JWT_SECRET`** (identyczny w Next.js i na Renderze backendu)
- TTL: **300 s** (5 min)
- Payload:

```json
{
  "typ": "pdf_render",
  "plan_id": "<uuid planu>",
  "exp": 1234567890,
  "iat": 1234567890
}
```

Front może podpisać token sam (np. Route Handler w Next.js) **albo** użyć helpera backendu (wymaga dostępu do planu):

**`POST /plan/{plan_id}/pdf-render-token`**  
(nagłówek `Authorization` / `X-Guest-ID` jak przy `GET /plan/{id}`)

Odpowiedź:

```json
{
  "token": "...",
  "url": "https://lets-travel.pl/plan/pdf/...",
  "expires_at": "2026-07-22T12:00:00+00:00",
  "ttl_sec": 300
}
```

Token w URL musi być **jednym segmentem ścieżki** (standardowy JWT z kropkami jest OK). Przy budowaniu linku można użyć `encodeURIComponent(token)`.

## Endpointy — skrót

| Metoda | Ścieżka | Opis |
|--------|---------|------|
| POST | `/plan/render-pdf` | Body `{ "url" }` → plik PDF |
| GET | `/plan/pdf-view/{token}` | Dane planu dla strony print |
| POST | `/plan/{plan_id}/pdf-render-token` | Opcjonalne mintowanie URL |
| GET | `/plan/{plan_id}/pdf` | Stary PDF (ReportLab) |

## Backend — env na Renderze (Ty dodajesz)

```env
FRONTEND_BASE_URL=https://lets-travel.pl
PDF_RENDER_JWT_SECRET=<ten sam co w Next.js>
PDF_RENDER_TOKEN_TTL_SEC=300
PDF_RENDER_WAIT_TIMEOUT_MS=20000
PDF_PLAYWRIGHT_ENABLED=true
CORS_ORIGINS=https://lets-travel.pl,http://localhost:3000
```

Opcjonalnie staging: `PDF_RENDER_ALLOWED_HOSTS=preview.lets-travel.pl`

## Front — przykład wywołania render

```typescript
const res = await fetch(`${API_URL}/plan/render-pdf`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ url: printPageUrl }),
});
const blob = await res.blob();
// pobierz plik…
```

## Błędy typowe

| Kod | Przyczyna |
|-----|-----------|
| 400 | Zły host URL lub ścieżka ≠ `/plan/pdf/{token}` |
| 401 | Token wygasły / zły podpis / zły `typ` |
| 502 | Playwright / timeout 20 s (brak `data-pdf-ready`) |
| 503 | Brak `PDF_RENDER_JWT_SECRET` lub Playwright wyłączony |
