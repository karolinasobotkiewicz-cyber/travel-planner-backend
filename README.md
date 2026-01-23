# Travel Planner Backend - ETAP 1

Backend API for travel planning application. Generates optimized single-day itineraries based on user preferences, location, and constraints.

## Project Status

Stage: ETAP 1 (Refactoring + Core API)  
Deadline: 29.01.2026  
Version: 1.0.0

## Features (ETAP 1)

- RESTful API with FastAPI
- Intelligent single-day itinerary planning
- Parking logic (car transport)
- Cost estimation (tickets)
- Mandatory lunch break (12:00-13:30)
- All item types: parking, transit, attraction, lunch_break, free_time
- Mock payment endpoints (Stripe interface)
- Repository Pattern (PostgreSQL-ready)
- 80%+ test coverage
- Docker support

## Architecture

Layered architecture following SOLID principles:

```
app/
├── domain/          # Business logic & entities
├── application/     # Use cases & services
├── infrastructure/  # External APIs & persistence
└── api/            # FastAPI routes & schemas
```

## Quick Start

### Prerequisites

- Python 3.11+
- pip

### Installation

1. Clone the repository:
```bash
git clone <repo-url>
cd travel-planner-backend
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

4. Setup environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys
```

5. Run the application:
```bash
uvicorn app.api.main:app --reload
```

API will be available at: `http://localhost:8000`  
Swagger docs: `http://localhost:8000/docs`

## Testing

Run tests with coverage:
```bash
pytest
```

Run tests with detailed coverage report:
```bash
pytest --cov=app --cov-report=html
```

View coverage report:
```bash
open htmlcov/index.html
```

## Development

### Code Quality

Install pre-commit hooks:
```bash
pre-commit install
```

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
