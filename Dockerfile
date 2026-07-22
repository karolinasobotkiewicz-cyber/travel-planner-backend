# Travel Planner Backend - Dockerfile
# Multi-stage build for optimized production image

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt
RUN pip install --no-cache-dir --user playwright==1.49.1 \
    && python -m playwright install --with-deps chromium

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY app/ ./app/
COPY data/ ./data/
COPY static/ ./static/

# Ensure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Render (and most PaaS) assign a dynamic port via $PORT — must bind to it, not a fixed 8000.
ENV PORT=8000
EXPOSE 8000

# Health check (stdlib only; respects $PORT)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/health')"

# Run application — shell form required so $PORT is expanded
CMD ["sh", "-c", "uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
