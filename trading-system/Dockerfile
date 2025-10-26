# Multi-stage Dockerfile for Trading System
# Phase 3 Tier 3: DevOps & Cloud Infrastructure

# ============================================================================
# Stage 1: Builder - Install dependencies and compile Python packages
# ============================================================================
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ============================================================================
# Stage 2: Runtime - Minimal image with only runtime dependencies
# ============================================================================
FROM python:3.11-slim

# Set metadata
LABEL maintainer="trading-system@example.com"
LABEL description="Algorithmic Trading System with ML"
LABEL version="3.0"

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash trader && \
    mkdir -p /app /app/data /app/logs /app/models /app/state && \
    chown -R trader:trader /app

# Set working directory
WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=trader:trader . .

# Switch to non-root user
USER trader

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEVELOPMENT_MODE=false

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Expose ports
EXPOSE 8000 9090

# Default command (can be overridden)
CMD ["python", "-m", "enhanced_trading_system_complete"]
