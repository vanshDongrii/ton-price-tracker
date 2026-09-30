# ==============================================================================
# Production Dockerfile for TON Price Tracker Telegram Bot
# ==============================================================================
FROM python:3.12-slim AS base

# Set environment variables for Python runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install security updates and curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first for Docker caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and scripts
COPY src/ /app/src/
COPY scripts/ /app/scripts/

# Create a non-privileged user and switch to it
RUN useradd -m -u 10001 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Health check verifies the live price feed service can initialize
HEALTHCHECK --interval=60s --timeout=10s --start-period=10s --retries=3 \
    CMD python scripts/verify_live.py || exit 1

# Start the Telegram bot
CMD ["python", "-m", "src.main"]
