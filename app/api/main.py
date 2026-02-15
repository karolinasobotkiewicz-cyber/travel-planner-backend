"""
FastAPI application main entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import plan, payment, content, poi


app = FastAPI(
    title="Travel Planner API",
    description="Backend API for travel planning engine - ETAP 1",
    version="1.0.0",
)

# CORS - TODO: doprecyzowac origins w ETAP 2
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # FIXME: production security
    allow_credentials=True,
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
