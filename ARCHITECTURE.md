# Architecture Documentation

Architektura backend Travel Planner - ETAP 1.

## Overview

Backend oparty na **Layered Architecture** (Clean Architecture lite). Oddzielone warstwy: domain, application, infrastructure, api.

**Zalety:**
- Łatwe testowanie (unit tests w domain bez dependencies)
- Łatwa zmiana storage (teraz in-memory, ETAP 2 PostgreSQL)
- Łatwa rozbudowa (nowe features w domain)
- SOLID principles

## Layers

```
┌─────────────────────────────────────────┐
│           API Layer (FastAPI)           │  HTTP requests/responses
├─────────────────────────────────────────┤
│       Application Layer (Services)      │  Use cases, orchestration
├─────────────────────────────────────────┤
│         Domain Layer (Business)         │  Core logic, models
├─────────────────────────────────────────┤
│   Infrastructure (Repos, External APIs) │  Database, external services
└─────────────────────────────────────────┘
```

### Domain Layer (business logic)

**Path:** `app/domain/`

**Co zawiera:**
- `models/` - Pydantic models (POI, Plan, TripInput)
- `scoring/` - Scoring functions (family_fit, budget, crowd, body_state)
- `planner/` - Engine (build_day), time utils

**Przykład - Scoring:**
```python
# domain/scoring/family_fit.py
def calculate_family_score(poi, user):
    """
    Zwraca score dla POI based on family requirements.
    
    Checks:
    - kids_only flag
    - target_group match
    - children age range
    """
    score = 0.0
    
    if user.traveler_group == "family_kids":
        if poi.kids_only:
            score += 15  # bonus dla kids-only attractions
        if "family" in poi.target_group:
            score += 10
    
    return score
```

**Dependencies:** ZERO. Domain nie zna nic o FastAPI, database, external APIs.

### Application Layer (use cases)

**Path:** `app/application/`

**Co zawiera:**
- `services/` - PlanService, TripMapper

**PlanService** - główny orchestrator:
```python
class PlanService:
    def __init__(self, poi_repo, plan_repo):
        self.poi_repo = poi_repo
        self.plan_repo = plan_repo
    
    async def generate_plan_preview(self, trip_input):
        # 1. Pobierz POIs z repository
        pois = self.poi_repo.get_by_destination(...)
        
        # 2. Build plan (domain logic)
        plan = build_day(pois, trip_input, ...)
        
        # 3. Map do response format
        response = TripMapper.to_response(plan)
        
        # 4. Save w repository
        self.plan_repo.save(plan_id, response)
        
        return response
```

**Dependencies:** Domain (używa), Infrastructure (używa repositories przez interfaces).

### Infrastructure Layer (external world)

**Path:** `app/infrastructure/`

**Co zawiera:**
- `repositories/` - POI, Plan, Destinations (in-memory ETAP 1)
- `external/` - OpenWeather API, Geocoding API
- `config/` - Settings (Pydantic Settings, .env)

**Repository Pattern:**
```python
# repositories/interfaces.py
class IPOIRepository(ABC):
    @abstractmethod
    def get_all(self) -> List[POI]:
        pass
    
    @abstractmethod
    def get_by_id(self, poi_id: str) -> Optional[POI]:
        pass

# repositories/poi_repository.py
class POIRepository(IPOIRepository):
    def __init__(self):
        self.pois = load_zakopane_poi()  # 32 POIs z Excel
    
    def get_all(self):
        return self.pois
    
    def get_by_id(self, poi_id):
        return next((p for p in self.pois if p.id == poi_id), None)
```

**ETAP 2:** Zmiana na PostgreSQL = tylko zmiana implementacji repository, interface zostaje.

### API Layer (HTTP)

**Path:** `app/api/`

**Co zawiera:**
- `routes/` - plan, payment, content, poi
- `schemas/` - Request/Response models (Pydantic)
- `dependencies.py` - Dependency injection (repos, services)
- `main.py` - FastAPI app initialization

**Przykład endpoint:**
```python
# routes/plan.py
@router.post("/plan/preview")
async def create_plan_preview(
    trip_input: TripInput,
    plan_service: PlanService = Depends(get_plan_service)
):
    plan = await plan_service.generate_plan_preview(trip_input)
    return plan
```

**Dependency Injection:**
```python
# dependencies.py
def get_poi_repository() -> POIRepository:
    return POIRepository()

def get_plan_repository() -> PlanRepository:
    return PlanRepository()

def get_plan_service(
    poi_repo: POIRepository = Depends(get_poi_repository),
    plan_repo: PlanRepository = Depends(get_plan_repository)
) -> PlanService:
    return PlanService(poi_repo, plan_repo)
```

## Data Flow

### Request Flow (POST /plan/preview)

```
1. Client → POST /plan/preview (JSON: date, destination, group, transport)
   ↓
2. API Layer → validate TripInput (Pydantic)
   ↓
3. PlanService.generate_plan_preview()
   ↓
4. POIRepository.get_by_destination() → 32 POIs z Excel
   ↓
5. Domain: build_day(pois, trip_input) → scoring, selection, time calculation
   ↓
6. TripMapper.to_response() → format dla API
   ↓
7. PlanRepository.save(plan_id, plan) → in-memory dict
   ↓
8. Return PlanResponse → Client (JSON)
```

### POI Loading Flow (startup)

```
1. POIRepository.__init__()
   ↓
2. load_zakopane_poi() → read zakopane.xlsx
   ↓
3. pandas.read_excel() → DataFrame (43 kolumny)
   ↓
4. normalize_poi() → clean data, fix types
   ↓
5. POI(**row) → Pydantic validation + @field_validator
   ↓
6. return List[POI] → 32 POIs in memory
```

**Critical fix (26.01):** @field_validator dla type coercion (dict→str, int→str, bool→str, list→str).

## Models

### TripInput (API request)

```python
class TripInput(BaseModel):
    date: str                      # "2026-02-15"
    destination_id: str            # "zakopane"
    traveler_group: str            # "family_kids", "couple", "solo"
    transport_modes: List[str]     # ["car"], ["walk"], ["car", "public"]
    budget_level: int              # 1=low, 2=medium, 3=high
    crowd_tolerance: int           # 1=low, 2=medium, 3=high
```

### POI (domain model)

```python
class POI(BaseModel):
    id: str
    name: str
    description_short: str
    opening_hours: str             # "09:00-18:00" (field_validator converts dict)
    ticket_normal: float           # 30.0
    ticket_reduced: float          # 15.0
    target_group: str              # "family,couple"
    kids_only: str                 # "true"/"false" (field_validator converts bool)
    tags: str                      # "oscypek,tradycja" (field_validator converts list)
    crowd_level: str               # "1"/"2"/"3" (field_validator converts int)
    # ... +30 more fields
```

### PlanResponse (API response)

```python
class PlanResponse(BaseModel):
    plan_id: str
    destination: Optional[str]
    version: int
    generated_at: str
    days: List[DayPlan]

class DayPlan(BaseModel):
    day_number: int
    date: str
    items: List[PlanItem]  # day_start, parking, attraction, transit, lunch_break, day_end
```

## Business Logic

### Scoring System

**4 funkcje scoringowe:**

1. **family_fit.py** - dopasowanie do grupy (family, couple, solo)
2. **budget.py** - dopasowanie do budżetu użytkownika
3. **crowd.py** - dopasowanie do crowd_tolerance
4. **body_state.py** - transitions (cold→warm→relax)

**Score aggregation (engine.py):**
```python
total_score = (
    family_score * 1.5 +    # najważniejszy
    budget_score * 1.0 +
    crowd_score * 0.8 +
    body_state_score * 0.5
)
```

### Day Planning Algorithm (simplified)

```python
def build_day(pois, trip_input):
    current_time = "09:00"
    items = []
    
    # 1. Day start
    items.append(DayStartItem("09:00"))
    
    # 2. Parking (if car)
    if "car" in trip_input.transport_modes:
        items.append(ParkingItem("09:00", "09:15", 15))
        current_time = "09:15"
    
    # 3. POI selection (score + filter)
    scored_pois = [(poi, calculate_score(poi, trip_input)) for poi in pois]
    scored_pois.sort(key=lambda x: x[1], reverse=True)
    
    # 4. Time fitting
    for poi, score in scored_pois:
        duration = poi.time_min
        if fits_in_day(current_time, duration, lunch_time):
            items.append(AttractionItem(poi, current_time, ...))
            current_time = add_minutes(current_time, duration)
            items.append(TransitItem(...))
    
    # 5. Lunch break (ZAWSZE 12:00-13:30)
    items = insert_lunch_break(items, "12:00", "13:30")
    
    # 6. Day end
    items.append(DayEndItem("18:00"))
    
    return items
```

### Parking Logic (requirement 4.10)

```python
# Tylko dla car mode
if "car" in transport_modes:
    parking = ParkingItem(
        start_time="09:00",
        end_time="09:15",
        duration_min=15,  # STAŁY CZAS
        name="Parking",
        address=first_attraction.parking_address,
        walk_time=first_attraction.parking_walk_time_min
    )
```

### Cost Estimation (requirement 4.11)

```python
def estimate_cost(poi, traveler_group):
    if poi.free_entry:
        return 0
    
    if traveler_group == "family_kids":
        # 2 adults + 2 kids
        return (2 * poi.ticket_normal) + (2 * poi.ticket_reduced)
    
    elif traveler_group == "couple":
        return 2 * poi.ticket_normal
    
    else:  # solo
        return poi.ticket_normal
```

### Lunch Break (requirement 4.12, CRITICAL)

```python
# ZAWSZE obecny 12:00-13:30 (per klientka 26.01)
lunch_item = LunchBreakItem(
    start_time="12:00",
    end_time="13:30",
    duration_min=90,
    suggestions=["Restauracja lokalna", "Bistro", "Lunch na wynos"]
)

# Wymuszony insert nawet jeśli engine zapomni
if not has_lunch_break(items):
    items = insert_lunch_at_noon(items, lunch_item)
```

## Storage (ETAP 1 - In-Memory)

### POI Storage
```python
# Ładowane raz przy starcie z Excel
pois = load_zakopane_poi()  # 32 POIs in memory (List[POI])
```

### Plan Storage
```python
# Dict w pamięci
plans = {
    "plan_123": {
        "plan": PlanResponse(...),
        "status": "ready",
        "created_at": "2026-01-27T10:00:00",
        "metadata": {...}
    }
}
```

**ETAP 2:** PostgreSQL + SQLAlchemy/Prisma ORM.

## External APIs

### OpenWeather API
- Endpoint: `https://api.openweathermap.org/data/2.5/weather`
- Key: `OPENWEATHER_API_KEY` (env variable)
- Usage: Weather check dla POI (currently mocked in ETAP 1)

### Geocoding API
- Currently not used (ETAP 1)
- ETAP 2: Geocode addresses dla navigation

## Configuration

### Settings (Pydantic Settings)

```python
class Settings(BaseSettings):
    environment: str = "development"
    debug: bool = True
    
    openweather_api_key: str
    geocoding_api_key: str
    
    cors_origins: str = "*"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    class Config:
        env_file = ".env"
```

### Environment Variables

Production (Render):
```
ENVIRONMENT=production
DEBUG=false
OPENWEATHER_API_KEY=your_api_key_here
CORS_ORIGINS=*
```

Development (local):
```
ENVIRONMENT=development
DEBUG=true
OPENWEATHER_API_KEY=test_key_123
CORS_ORIGINS=http://localhost:3000
```

## Testing Strategy

### Unit Tests (22 tests)
- Domain/scoring functions (family, budget, crowd, body_state)
- Domain/time_utils (time conversions)
- NO external dependencies

### Integration Tests (7 API tests)
- FastAPI TestClient
- All endpoints (health, plan, content, payment, poi)
- Real POI loading (32 POIs)

### Repository Tests (3 tests)
- POI loading from Excel
- Plan CRUD operations
- Destinations loading from JSON

### Business Logic Tests (2 tests)
- Parking logic (15min, car only)
- Cost estimation formula
- Lunch break presence

**Total: 38/38 GREEN** ✅

## Deployment Architecture

```
GitHub Repo
    ↓
Render.com (auto-deploy on push to main)
    ↓
Docker Build (multi-stage Dockerfile)
    ↓
Container Runtime (Python 3.11-slim)
    ↓
Uvicorn (ASGI server)
    ↓
FastAPI App (listening 0.0.0.0:8000)
    ↓
Render Proxy (HTTPS termination)
    ↓
Public URL: https://travel-planner-backend-xbsp.onrender.com
```

### Docker Multi-Stage Build

**Stage 1 - Builder:**
- Base: python:3.11-slim
- Install gcc, g++ (for building packages)
- Install Python dependencies
- Output: /root/.local (user site-packages)

**Stage 2 - Runtime:**
- Base: python:3.11-slim (clean)
- Copy /root/.local from builder
- Copy app/ data/ static/
- No build tools → smaller image
- CMD: uvicorn app.api.main:app

**Image size:** ~200MB (vs ~800MB without multi-stage).

## Security

### Secrets Management
- API keys w environment variables (NIGDY w kodzie)
- `.env` w `.gitignore`
- Render/Railway UI dla production secrets

### CORS
- Development: `http://localhost:3000`
- Testing: `*` (wildcard)
- Production: specific frontend URL

### Input Validation
- Pydantic models dla all requests
- Type checking, range validation
- SQL injection protection: N/A (no SQL in ETAP 1)

## Performance

### Current Metrics (Render Free)
- Cold start: 30-50s (after 15min inactivity)
- Warm response: 50-200ms
- POI loading: ~1s (32 POIs at startup)
- Memory: ~150MB usage

### Optimization (future)
- Caching (Redis) dla scored POIs
- PostgreSQL indexes
- CDN dla static files (images)
- Rate limiting

## Future Architecture (ETAP 2+)

### Database Layer
```
PostgreSQL
├── pois table (relational data)
├── plans table (user plans)
├── users table (authentication)
└── payments table (Stripe transactions)
```

### Caching Layer
```
Redis
├── Cached POI scores (TTL: 1h)
├── Session data (TTL: 24h)
└── Rate limiting counters
```

### Queue System (ETAP 3+)
```
Celery + Redis
└── Async plan generation (długotrwałe obliczenia)
```

## Troubleshooting

### Common Issues

**Problem:** `ImportError: cannot import name 'XXX'`
**Solution:** Check `__init__.py` exports w module

**Problem:** `ModuleNotFoundError: No module named 'pandas'`
**Solution:** Missing dependency, add to requirements.txt

**Problem:** POI validation error (dict→str)
**Solution:** Use @field_validator dla type coercion

**Problem:** Lunch break missing
**Solution:** Check insert_lunch_break() w plan_service.py

## Documentation References

- FastAPI docs: https://fastapi.tiangolo.com/
- Pydantic docs: https://docs.pydantic.dev/
- Clean Architecture: Robert C. Martin "Clean Architecture"
- Repository Pattern: Martin Fowler "Patterns of Enterprise Application Architecture"

---

Last update: 27.01.2026  
Author: NextGenCode.dev  
Status: ETAP 1 Complete ✅