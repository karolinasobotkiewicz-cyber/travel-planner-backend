# Travel Planner Backend - Dockerfile
# Multi-stage build for optimized production image

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies for compiling wheels
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Chromium headless — libs only (avoid playwright --with-deps broken font packages on slim)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libglib2.0-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libx11-6 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /root/.local

ENV PATH=/root/.local/bin:$PATH

# Browser binaries must live in the runtime image (not only in builder)
RUN playwright install chromium

COPY app/ ./app/
COPY data/ ./data/
COPY static/ ./static/

# Render injects PORT (default 10000) and scans 0.0.0.0:$PORT.
# An image-level PORT=8000 makes the process listen where the scan is not looking.
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT', '10000'))"

CMD ["sh", "-c", "echo \"[boot] uvicorn 0.0.0.0:${PORT:-10000}\" && exec uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
