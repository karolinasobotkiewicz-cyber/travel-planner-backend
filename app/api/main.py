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


@app.get("/health")
def health_check():
    """Health check endpoint for Railway deployment."""
    return {"status": "ok", "service": "travel-planner-api"}


@app.get("/")
def root():
    """Root endpoint with API info."""
    return {
        "message": "Travel Planner API - ETAP 1",
        "docs": "/docs",
        "health": "/health",
    }
