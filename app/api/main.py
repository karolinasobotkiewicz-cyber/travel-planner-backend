"""
FastAPI application main entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import plan, payment, content, poi
from app.infrastructure.config.settings import settings


app = FastAPI(
    title="Travel Planner API",
    description="Backend API for travel planning engine - ETAP 2 (Auth + Payment)",
    version="2.0.0",
)

# CORS - ETAP 2: Restricted to frontend URLs (localhost:3000, lets-travel.pl)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # From .env: http://localhost:3000,https://lets-travel.pl
    allow_credentials=True,  # Required for JWT auth
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(plan.router, prefix="/plan", tags=["plan"])
app.include_router(payment.router, prefix="/payment", tags=["payment"])
app.include_router(content.router, prefix="/content", tags=["content"])
app.include_router(poi.router, prefix="/poi", tags=["poi"])


@app.on_event("startup")
async def startup_event():
    """
    Application startup tasks:
    1. Reload POI data from Excel
    2. Test database connection (ETAP 2)
    """
    # POI reload
    print("[STARTUP] Starting POI reload...")
    try:
        from app.api.dependencies import get_poi_repository
        print("[STARTUP] Import successful")
        poi_repo = get_poi_repository()
        print("[STARTUP] Repository instance obtained")
        poi_repo.reload()
        print("[STARTUP] POI Repository reloaded on startup - SUCCESS")
    except Exception as e:
        print(f"[STARTUP] POI ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    # Database connection test (ETAP 2)
    print("[STARTUP] Testing database connection...")
    try:
        from app.infrastructure.database.connection import test_connection
        if test_connection():
            print("[STARTUP] Database connection verified")
        else:
            print("[STARTUP] Database connection failed (but starting anyway)")
    except Exception as e:
        print(f"[STARTUP] Database connection test skipped: {e}")


@app.get("/health")
def health_check():
    """
    Health check endpoint for deployment monitoring.
    
    ETAP 2: Includes database connectivity check.
    """
    response = {
        "status": "ok",
        "service": "travel-planner-api",
        "version": "2.0.0",  # ETAP 2
    }
    
    # Try database connection (don't fail if DB is down)
    try:
        from app.infrastructure.database.connection import test_connection
        db_ok = test_connection()
        response["database"] = "connected" if db_ok else "unavailable"
    except Exception as e:
        response["database"] = f"error: {str(e)[:50]}"
    
    return response


@app.post("/admin/reload-poi")
def admin_reload_poi():
    """Admin endpoint to manually reload POI data from Excel."""
    try:
        from app.api.dependencies import get_poi_repository
        poi_repo = get_poi_repository()
        poi_repo.reload()
        return {
            "status": "success",
            "message": "POI Repository reloaded from Excel",
            "emoji": "🔄"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.get("/")
def root():
    """Root endpoint with API info."""
    return {
        "message": "Travel Planner API - ETAP 1",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/debug/module-paths")
def debug_module_paths():
    """Debug: Show where modules are loaded from."""
    import sys
    import app.application.services.plan_service as plan_service_module
    
    return {
        "plan_service_file": plan_service_module.__file__,
        "module_version_id": getattr(plan_service_module, 'MODULE_VERSION_ID', 'NOT_FOUND'),
        "has_FIX24_code": hasattr(plan_service_module.PlanService.generate_plan, '__code__') and 
                          "FIX #24" in open(plan_service_module.__file__, 'r', encoding='utf-8').read(),
        "sys_prefix": sys.prefix,
        "sys_executable": sys.executable
    }
# Force reload 3
