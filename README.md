# Travel Planner Backend

Backend API do planowania jednodniowych wycieczek po Polsce. Projekt dla Karoliny Sobotkiewicz.

## Status

**ETAP 1: COMPLETED** (29.01.2026)  
**ETAP 2: COMPLETED** (15.02.2026)  
**Live API:** https://travel-planner-backend-xbsp.onrender.com  
**Docs:** https://travel-planner-backend-xbsp.onrender.com/docs

## Co działa

### API Endpoints (14 total)

**Plan Management:**
- `POST /plan/preview` - Generowanie planu (1-5 dni)
- `GET /plan/{id}` - Pobieranie planu
- `GET /plan/{id}/status` - Status generowania
- `GET /plan/{id}/versions` - Historia wersji
- `GET /plan/{id}/versions/{num}` - Konkretna wersja

**Plan Editing (ETAP 2):**
- `POST /plan/{id}/days/{day}/remove` - Usuń POI z dnia
- `POST /plan/{id}/days/{day}/replace` - Zamień POI (SMART_REPLACE)
- `POST /plan/{id}/days/{day}/regenerate` - Regeneruj przedział czasowy
- `POST /plan/{id}/rollback` - Wróć do poprzedniej wersji

**Content & Payment:**
- `GET /content/home` - Lista 8 destynacji
- `GET /poi/{id}` - Szczegóły atrakcji
- `POST /payment/create-checkout-session` - Mock Stripe
- `POST /payment/stripe/webhook` - Mock webhook
- `GET /health` - Health check

### Logika biznesowa (ETAP 1 + 2)

**Single Day:**
- Parking: 15 minut na start (tylko car mode)
- Lunch break: ZAWSZE 12:00-13:30
- Cost: (2×normalny) + (2×ulgowy) dla rodzin
- Timing: 09:00 → 18:00/19:00

**Multi-Day (ETAP 2):**
- Plan na 1-5 dni
- Cross-day uniqueness: POI się nie powtarzają (dopuszczalne max 2x)
- Core POI rotation: Morskie Oko nie zawsze pierwszy dzień
- Energy system: Dzień 1 = heavy hiking OK, dzień 2-3 = lighter

**Version Control (ETAP 2):**
- Każda zmiana = nowa wersja w DB
- Rollback do dowolnej wersji
- Historia zachowana (immutable)

### Dane

**POI Database:**
- 32 POI z zakopane.xlsx (Muzeum Oscypka, Gubałówka, Termy, etc.)
- Repository Pattern → PostgreSQL (ETAP 2)

**Destinations:**
- 8 destynacji z destinations.json (Zakopane, Kraków, Gdańsk, Warszawa, Wrocław, Poznań, Toruń, Lublin)

**Database (ETAP 2):**
- PostgreSQL na Render
- Alembic migrations
- Tables: `plans`, `plan_versions`, `poi` (read-only)
- Version tracking system

### Testy

**ETAP 1:** 48/48 GREEN
**ETAP 2:** 3 E2E scenarios PASSED (live na Render)
- Multi-day planning (5 dni, 71.4% uniqueness, core rotation)
- Editing workflow (remove, replace, regenerate, rollback) 
- Regression testing (budget penalties, zero regresji Etap 1)

## Tech Stack

- Python 3.11
- FastAPI 0.109.0
- Pydantic 2.5.3
- **PostgreSQL** (ETAP 2)
- **Alembic** (migrations)
- **psycopg2** (DB driver)
- Uvicorn
- Docker
- Render.com (deployment)

## Database Setup

**Local Development:**

```bash
# 1. Zainstaluj PostgreSQL lokalnie
# macOS: brew install postgresql
# Windows: Download from postgresql.org

# 2. Utwórz bazę
createdb travel_planner

# 3. Set env variable
export DATABASE_URL="postgresql://user:pass@localhost:5432/travel_planner"

# 4. Run migrations
alembic upgrade head

# 5. Load POI data (opcjonalnie)
python scripts/seed_poi.py
```

**Render Deployment:**
- Database → Render Postgres (FREE)
- Migrations auto-run on deploy via `render.yaml`
- Connection string w env variable `DATABASE_URL`

## Architecture

```
app/
├── domain/                 # Business logic
│   ├── models/            # Pydantic models (POI, Plan, TripInput)
│   ├── scoring/           # Scoring functions (family, budget, crowd, body_state, preferences, travel_style)
│   └── planner/           # Engine + time utils
├── application/           # Use cases
│   └── services/          # PlanService, TripMapper
├── infrastructure/        # External world
│   ├── repositories/      # POI, Plan, Destinations (in-memory ETAP 1)
│   ├── external/          # OpenWeather, Geocoding APIs
│   └── config/            # Settings, env variables
└── api/                   # FastAPI
    ├── routes/            # Endpoints (plan, payment, content, poi)
    └── schemas/           # Request/Response models
```

Layered architecture, SOLID principles, Repository Pattern.

## Environment Variables

Backend używa tych zmiennych (ustawione na Render):

```env
ENVIRONMENT=production
DEBUG=false
OPENWEATHER_API_KEY=xxx
GEOCODING_API_KEY=xxx
CORS_ORIGINS=*
API_HOST=0.0.0.0
API_PORT=8000
```

## Deployment

Backend jest deployed na **Render.com** (FREE tier).

**WAŻNE:** Free tier "zasypia" po 15 min nieaktywności. Cold start trwa ~30-50s. Do testów OK, do produkcji lepiej Railway ($5/miesiąc).

Szczegóły deployment → [DEPLOYMENT.md](DEPLOYMENT.md)

## Testing API

### Swagger UI (recommended)
Otwórz: https://travel-planner-backend-xbsp.onrender.com/docs

Kliknij endpoint → "Try it out" → wypełnij dane → "Execute"

---

### 1. Multi-Day Planning (ETAP 2)

**Endpoint:** `POST /plan/preview`

**Payload (5-day plan):**
```json
{
  "location": {
    "city": "Zakopane",
    "country": "Poland",
    "region_type": "mountain"
  },
  "group": {
    "type": "couples",
    "size": 2,
    "crowd_tolerance": 1
  },
  "trip_length": {
    "days": 5,
    "start_date": "2026-03-15"
  },
  "daily_time_window": {
    "start": "09:00",
    "end": "19:00"
  },
  "budget": {
    "level": 2
  },
  "transport_modes": ["car"],
  "preferences": [],
  "travel_style": "balanced"
}
```

**Response:** Plan z 5 dniami, POI się nie powtarzają (>70% uniqueness), core POI rotują.

---

### 2. Editing Workflow (ETAP 2)

**Usuń POI:**
```bash
POST /plan/{plan_id}/days/1/remove
{
  "item_id": "poi_30",
  "avoid_cooldown_hours": 24
}
```

**Zamień POI (SMART_REPLACE):**
```bash
POST /plan/{plan_id}/days/1/replace
{
  "item_id": "poi_20",
  "strategy": "SMART_REPLACE",
  "preferences": {}
}
```

**Regeneruj przedział czasowy:**
```bash
POST /plan/{plan_id}/days/1/regenerate
{
  "from_time": "15:00",
  "to_time": "18:00",
  "pinned_items": ["poi_35"]
}
```

**Rollback do wersji:**
```bash
POST /plan/{plan_id}/rollback
{
  "target_version": 3
}
```

**Historia wersji:**
```bash
GET /plan/{plan_id}/versions
```

Response: Lista wszystkich wersji z change_type, change_summary, created_at.

---

### 3. Content API

**Destynacje:**
```bash
GET /content/home
```

Response: 8 destynacji z image_key, description, highlights.

## Known Issues / TODO

- [ ] Frontend URL dla CORS (teraz wildcard *)
- [ ] Railway migration (gdy klientka będzie gotowa na paid tier)
- [ ] Real Stripe integration (ETAP 3+)
- [x] ~~PostgreSQL~~ ✅ DONE (ETAP 2)
- [x] ~~Multi-day planning~~ ✅ DONE (ETAP 2)
- [x] ~~Versioning + Rollback~~ ✅ DONE (ETAP 2)

## Development

Repo: https://github.com/karolinasobotkiewicz-cyber/travel-planner-backend

Latest commits (ETAP 2):
- `0fdf5ad` - Live testing results (Render deployment)
- `e28e676` - Day 10 documentation (E2E tests)
- `b3ab38f` - E2E integration tests + Unicode fixes
- `4d5cf0b` - Multi-day planning + editing workflow
- `a13a2b7` - Docker + Render deployment (ETAP 1)

---

**ETAP 1:** 29.01.2026 ✅  
**ETAP 2:** 15.02.2026 ✅

Więcej info → [ETAP2_FEATURES.md](ETAP2_FEATURES.md)

## Support

Issues? Contact: ngencode.dev@gmail.com

---

Projekt wykonany przez NextGenCode.dev dla Karoliny Sobotkiewicz  
**ETAP 1:** 29.01.2026 ✅  
**ETAP 2:** 15.02.2026 ✅
