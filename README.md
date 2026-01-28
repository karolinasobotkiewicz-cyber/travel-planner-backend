# Travel Planner Backend

Backend API do planowania jednodniowych wycieczek po Polsce. Projekt dla Karoliny Sobotkiewicz.

## Status

**ETAP 1: COMPLETED** (29.01.2026)  
**Live API:** https://travel-planner-backend-xbsp.onrender.com  
**Docs:** https://travel-planner-backend-xbsp.onrender.com/docs

## Co działa

### API Endpoints (7/7)
- `GET /health` - Health check
- `GET /` - Root info
- `POST /plan/preview` - Generowanie planu dnia
- `GET /plan/{id}` - Pobieranie gotowego planu
- `GET /content/home` - Lista 8 destynacji
- `GET /poi/{id}` - Szczegóły atrakcji
- `POST /payment/create-checkout-session` - Mock Stripe checkout
- `POST /payment/stripe/webhook` - Mock Stripe webhook

### Logika biznesowa
- Parking: 15 minut na start (tylko dla car mode)
- Lunch break: ZAWSZE 12:00-13:30 (per client requirement)
- Cost estimation: (2×bilet_normalny) + (2×bilet_ulgowy) dla rodzin
- Day structure: 09:00 start → parking → atrakcje → lunch → koniec 18:00

### Dane
- 32 POI z zakopane.xlsx (Muzeum Oscypka, Gubałówka, Termy, etc.)
- 8 destynacji z destinations.json (Zakopane, Kraków, Gdańsk, Warszawa, Wrocław, Poznań, Toruń, Lublin)
- Repository Pattern (gotowy na PostgreSQL w ETAPIE 2)

### Testy
48/48 GREEN (ETAP 1 rozszerzony):
- 9 unit tests: preferences scoring
- 12 unit tests: travel_style scoring
- 15 unit tests: stare scoring modules (family, budget, crowd, body_state)
- 7 unit tests: time utils
- 5 integration tests: preferences + travel_style w pełnym planie

## Tech Stack

- Python 3.11
- FastAPI 0.109.0
- Pydantic 2.5.3
- Uvicorn
- Docker
- Render.com (deployment)

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

### Przykład: POST /plan/preview

```json
{
  "date": "2026-02-15",
  "destination_id": "zakopane",
  "traveler_group": "family_kids",
  "transport_modes": ["car"],
  "crowd_tolerance": 2,
  "budget_level": 2,
  "preferences": ["outdoor", "hiking", "nature"],
  "travel_style": "adventure"
}
```

**Nowe w ETAP 1 (rozszerzenie):**
- `preferences` (optional): Lista preferencji użytkownika (np. ["outdoor", "museums", "culture"]). Scoring system dodaje +5 punktów za każdy matching tag między user preferences a POI tags.
- `travel_style` (optional): Styl podróży - "cultural", "adventure", "relax", "balanced" (default). Scoring system dopasowuje do POI activity_style: adventure→active (+6), relax→relax (+6), cultural→balanced (+6), partial matches (+3).

Response: Plan dnia z parking (15min), atrakcjami, lunch (12:00-13:30), przejściami.

### Przykład: GET /content/home

```bash
curl https://travel-planner-backend-xbsp.onrender.com/content/home
```

Response: 8 destynacji z image_key, description, highlights.

## Known Issues / TODO

- [ ] Frontend URL dla CORS (teraz wildcard *)
- [ ] Railway migration (gdy klientka będzie gotowa na paid tier)
- [ ] PostgreSQL (ETAP 2)
- [ ] Multi-day planning (ETAP 2+)
- [ ] Real Stripe integration (ETAP 2+)

## Development

Repo: https://github.com/karolinasobotkiewicz-cyber/travel-planner-backend

Latest commits:
- `a13a2b7` - Docker + Render deployment setup
- `d2f1e8c` - ETAP 1 core functionality (API, repositories, business logic)

## Support

Issues? Contact: ngencode.dev@gmail.com

---

Projekt wykonany przez NextGenCode.dev dla Karoliny Sobotkiewicz  
Deadline ETAP 1: 29.01.2026 ✅

Format code:
```bash
black .
isort .
```

Type checking:
```bash
mypy app/
```

Linting:
```bash
flake8 app/
```

## Docker

Build and run with Docker:
```bash
docker-compose up --build
```

## ## API Endpoints

### Plan Management
- `POST /api/v1/plan/preview` - Preview plan before payment
- `GET /api/v1/plan/{plan_id}/status` - Check generation status
- `GET /api/v1/plan/{plan_id}` - Get full plan

### Payment (MOCKED in ETAP 1)
- `POST /api/v1/payment/create-checkout-session` - Create Stripe session
- `POST /api/v1/payment/stripe/webhook` - Stripe webhook handler

### Content
- `GET /api/v1/content/home` - Homepage data

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - System architecture & design decisions
- [API Documentation](docs/API.md) - Detailed API specifications
- [Deployment](docs/DEPLOYMENT.md) - Railway.app deployment guide

## Configuration

Key environment variables (see `.env.example`):

- `OPENWEATHER_API_KEY` - OpenWeather API key
- `GEOCODING_API_KEY` - Geocoding API key
- `POI_DATA_PATH` - Path to POI data file (zakopane.xlsx)
- `DEBUG` - Enable debug mode
- `LOG_LEVEL` - Logging level

## Tech Stack

- **Framework:** FastAPI 0.109+
- **Validation:** Pydantic 2.5+
- **Data Processing:** Pandas 2.1+
- **Testing:** Pytest 7.4+
- **Code Quality:** Black, isort, mypy, flake8
- **Deployment:** Docker, Railway.app

## ETAP 1 Scope

### Included:
- Single-day planning (1 day only)
- Mock Stripe payment flow
- Repository Pattern (in-memory)
- Parking logic (1 at start)
- Cost estimation (ticket_normal)
- All API endpoints functional

### Deferred to ETAP 2:
- Multi-day planning (2-7 days)
- Real Stripe integration
- PostgreSQL persistence
- Plan versioning & regeneration
- Email notifications
- Advanced parking logic

## Team

**Developer:** Mateusz Zurowski (ngencode.dev@gmail.com)  
**Client:** Karolina Sobotkiewicz

## License

Proprietary - All rights reserved

## Links

- **Repository:** [GitHub URL will be added]
- **Production:** [Railway URL will be added]
- **Documentation:** See `docs/` folder
