"""
Database connection setup for PostgreSQL (Supabase).
ETAP 2: PostgreSQL Migration
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from typing import Generator

# Load environment variables from .env (for local development)
env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Get DATABASE_URL from environment (never hardcoded!)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL not found in environment variables. "
        "Please set it in Render or create .env file locally."
    )

# Create SQLAlchemy engine
# Use NullPool for serverless/short-lived connections (Render Free)
engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,  # No connection pooling (better for serverless)
    echo=False,  # Set to True for SQL query logging (debug only)
    future=True,  # SQLAlchemy 2.0 style
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_engine():
    """Get SQLAlchemy engine instance."""
    return engine


def get_session() -> Generator[Session, None, None]:
    """
    Dependency for FastAPI routes to get database session.
    
    Usage:
        @app.get("/plans")
        def get_plans(db: Session = Depends(get_session)):
            plans = db.query(Plan).all()
            return plans
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Optional: Ping database on startup to verify connection
def test_connection():
    """Test database connection (call during app startup)."""
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✅ Database connection successful!")
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False
