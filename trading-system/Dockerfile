# Multi-stage Dockerfile for Enhanced NIFTY 50 Trading System
# Production-ready containerization with security hardening

# ============================================================================
# Stage 1: Builder - Install dependencies and compile Python packages
# ============================================================================
FROM python:3.11-slim as builder

LABEL stage="builder"

# Set working directory
WORKDIR /app

# Set build-time environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    git \
    libpq-dev \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies with optimizations
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# ============================================================================
# Stage 2: Runtime - Minimal image with only runtime dependencies
# ============================================================================
FROM python:3.11-slim

# Set metadata
LABEL maintainer="trading-system@example.com" \
      description="Enhanced NIFTY 50 Trading System - Production Ready" \
      version="1.0.0" \
      com.trading-system.week="2-deployment" \
      org.opencontainers.image.source="https://github.com/yourusername/trading-system"

# Set runtime environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    TRADING_HOME=/app \
    TRADING_USER=trader \
    TRADING_UID=1000 \
    TRADING_GID=1000 \
    TZ=Asia/Kolkata

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    postgresql-client \
    redis-tools \
    curl \
    ca-certificates \
    tzdata \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Set timezone to IST (Indian Standard Time) for trading hours
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Create non-root user for security
RUN groupadd -g ${TRADING_GID} ${TRADING_USER} && \
    useradd -u ${TRADING_UID} -g ${TRADING_GID} -m -s /bin/bash ${TRADING_USER}

# Create application directories with proper permissions
RUN mkdir -p ${TRADING_HOME}/logs \
             ${TRADING_HOME}/data \
             ${TRADING_HOME}/backups \
             ${TRADING_HOME}/models \
             ${TRADING_HOME}/state \
             ${TRADING_HOME}/certs \
             ${TRADING_HOME}/test_results && \
    chown -R ${TRADING_USER}:${TRADING_USER} ${TRADING_HOME}

# Set working directory
WORKDIR ${TRADING_HOME}

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY --chown=${TRADING_USER}:${TRADING_USER} . ${TRADING_HOME}/

# Copy SSL certificates if available (ignore errors if not present)
COPY --chown=${TRADING_USER}:${TRADING_USER} certs/* ${TRADING_HOME}/certs/ 2>/dev/null || :

# Switch to non-root user
USER ${TRADING_USER}

# Expose ports
# 8080 - Main dashboard (enhanced_dashboard_server.py)
# 8081 - Monitoring dashboard (web_monitoring_dashboard.py)
# 5000 - API server (if needed)
EXPOSE 8080 8081 5000

# Health check using dashboard health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || python3 -c "import sys; sys.exit(0)"

# Default command - runs main trading system
CMD ["python3", "main.py"]

# Alternative commands (can override with docker run):
# - python3 enhanced_dashboard_server.py (dashboard only)
# - python3 infrastructure/web_monitoring_dashboard.py (monitoring only)
# - python3 robust_trading_loop.py (trading loop only)
