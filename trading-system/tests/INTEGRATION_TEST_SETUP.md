# Integration Test Setup Guide

**Purpose:** Run integration tests that require external services (PostgreSQL, Redis, APIs)
**Audience:** Developers, QA Engineers, CI/CD pipelines
**Last Updated:** November 2025

---

## Overview

Integration tests validate the interaction between the trading system and external services:

- **PostgreSQL** - Database persistence and queries
- **Redis** - State management and caching
- **Zerodha API** - Market data and order execution (paper trading)

## Quick Start (Docker Compose)

The easiest way to run integration tests is using Docker Compose:

```bash
cd /Users/gogineni/Python/trading-system

# Start all services
docker-compose up -d postgres redis

# Wait for services to be ready
docker-compose ps

# Run integration tests
pytest tests/integration/ -v

# Cleanup
docker-compose down
```

## Service Requirements

### 1. PostgreSQL

**Version:** 15.x or higher
**Purpose:** Trade history, portfolio state, analytics

**Required Configuration:**
```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=trading_system
POSTGRES_USER=trading_user
POSTGRES_PASSWORD=<secure_password>
```

**Docker Setup:**
```bash
docker run -d \
  --name trading-postgres \
  -e POSTGRES_DB=trading_system \
  -e POSTGRES_USER=trading_user \
  -e POSTGRES_PASSWORD=trading_pass \
  -p 5432:5432 \
  postgres:15-alpine
```

**Manual Setup:**
```bash
# Install PostgreSQL
brew install postgresql@15  # macOS
# or
sudo apt-get install postgresql-15  # Ubuntu

# Create database
createdb trading_system

# Create user
psql -c "CREATE USER trading_user WITH PASSWORD 'trading_pass';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE trading_system TO trading_user;"

# Initialize schema
psql -U trading_user trading_system < database/schema.sql
```

### 2. Redis

**Version:** 7.x or higher
**Purpose:** State management, rate limiting, caching

**Required Configuration:**
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=<secure_password>  # Optional but recommended
REDIS_DB=0
```

**Docker Setup:**
```bash
docker run -d \
  --name trading-redis \
  -p 6379:6379 \
  redis:7-alpine \
  redis-server --requirepass trading_pass
```

**Manual Setup:**
```bash
# Install Redis
brew install redis  # macOS
# or
sudo apt-get install redis-server  # Ubuntu

# Start Redis
redis-server --daemonize yes --requirepass trading_pass

# Verify
redis-cli -a trading_pass ping
# Should return: PONG
```

### 3. Zerodha API (Optional)

**Purpose:** Live market data testing (paper trading mode)

**Required Configuration:**
```bash
KITE_API_KEY=<your_api_key>
KITE_API_SECRET=<your_api_secret>
KITE_REQUEST_TOKEN=<session_token>  # Generated per session
```

**Setup:**
```bash
# Store credentials securely
cat > .env << 'EOF'
KITE_API_KEY=your_key_here
KITE_API_SECRET=your_secret_here
EOF

# Generate request token (manual process via Zerodha login)
# See: https://kite.trade/docs/connect/v3/user/
```

## Environment Setup

### Create Test Environment File

```bash
cd /Users/gogineni/Python/trading-system

cat > .env.test << 'EOF'
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=trading_system_test
POSTGRES_USER=trading_user
POSTGRES_PASSWORD=trading_pass

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=trading_pass
REDIS_DB=1  # Use different DB for tests

# Testing mode
TESTING=true
PAPER_TRADING=true
EOF
```

### Load Environment Variables

```bash
# Load test environment
export $(cat .env.test | xargs)

# Verify
echo $POSTGRES_HOST
echo $REDIS_HOST
```

## Running Integration Tests

### All Integration Tests

```bash
# Run all integration tests
pytest tests/integration/ -v

# With coverage
pytest tests/integration/ --cov=infrastructure --cov-report=html
```

### Specific Test Categories

```bash
# Database integration tests
pytest tests/integration/test_postgresql_*.py -v

# Redis integration tests
pytest tests/integration/test_redis_*.py -v

# API integration tests (requires Zerodha credentials)
pytest tests/integration/test_zerodha_*.py -v

# End-to-end tests
pytest tests/integration/test_e2e_*.py -v
```

### Skip Integration Tests

```bash
# Run only unit tests (no external dependencies)
pytest tests/ -v -m "not integration"

# Or explicitly skip integration directory
pytest tests/ --ignore=tests/integration/ -v
```

## Docker Compose Configuration

Create `docker-compose.test.yml`:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: trading_system_test
      POSTGRES_USER: trading_user
      POSTGRES_PASSWORD: trading_pass
    ports:
      - "5432:5432"
    volumes:
      - ./database/schema.sql:/docker-entrypoint-initdb.d/01-schema.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U trading_user"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass trading_pass
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "trading_pass", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

networks:
  default:
    name: trading-system-test
```

**Usage:**
```bash
# Start services
docker-compose -f docker-compose.test.yml up -d

# Wait for health checks
docker-compose -f docker-compose.test.yml ps

# Run tests
pytest tests/integration/ -v

# Stop services
docker-compose -f docker-compose.test.yml down -v
```

## Continuous Integration (CI/CD)

### GitHub Actions Example

```yaml
# .github/workflows/integration-tests.yml
name: Integration Tests

on: [push, pull_request]

jobs:
  integration-tests:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: trading_system_test
          POSTGRES_USER: trading_user
          POSTGRES_PASSWORD: trading_pass
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run integration tests
        env:
          POSTGRES_HOST: localhost
          POSTGRES_PORT: 5432
          POSTGRES_DB: trading_system_test
          POSTGRES_USER: trading_user
          POSTGRES_PASSWORD: trading_pass
          REDIS_HOST: localhost
          REDIS_PORT: 6379
          TESTING: true
        run: pytest tests/integration/ -v --cov
```

## Troubleshooting

### PostgreSQL Connection Errors

```bash
# Error: connection refused
# Solution: Check if PostgreSQL is running
docker ps | grep postgres
# or
pg_isready -h localhost -p 5432

# Error: authentication failed
# Solution: Verify credentials
psql -h localhost -U trading_user -d trading_system_test
```

### Redis Connection Errors

```bash
# Error: connection refused
# Solution: Check if Redis is running
redis-cli -h localhost -p 6379 ping

# Error: NOAUTH authentication required
# Solution: Provide password
redis-cli -h localhost -p 6379 -a trading_pass ping
```

### Port Conflicts

```bash
# Find process using port 5432
lsof -i :5432
# or
netstat -an | grep 5432

# Kill process if needed
kill -9 <PID>
```

## Test Data Management

### Database Fixtures

```python
# tests/integration/conftest.py
import pytest
from infrastructure.postgresql_manager import PostgreSQLManager

@pytest.fixture(scope="session")
def db_connection():
    """Provide database connection for tests"""
    manager = PostgreSQLManager(
        host="localhost",
        port=5432,
        database="trading_system_test",
        user="trading_user",
        password="trading_pass"
    )
    yield manager
    manager.close()

@pytest.fixture(scope="function")
def clean_database(db_connection):
    """Clean database before each test"""
    db_connection.execute("TRUNCATE TABLE trades, positions, orders CASCADE;")
    yield
    db_connection.execute("TRUNCATE TABLE trades, positions, orders CASCADE;")
```

### Redis Fixtures

```python
@pytest.fixture(scope="function")
def redis_client():
    """Provide Redis client for tests"""
    import redis
    client = redis.Redis(
        host="localhost",
        port=6379,
        password="trading_pass",
        db=1,  # Use test DB
        decode_responses=True
    )
    yield client
    client.flushdb()  # Clean after test
```

## Performance Considerations

### Parallel Test Execution

```bash
# Install pytest-xdist
pip install pytest-xdist

# Run tests in parallel (4 workers)
pytest tests/integration/ -v -n 4

# Auto-detect optimal worker count
pytest tests/integration/ -v -n auto
```

### Test Database Isolation

```bash
# Use separate test database per worker
pytest tests/integration/ -v -n 4 --tx=pgsql:database_isolation
```

## Summary

| Service | Required | Setup Time | Alternative |
|---------|----------|------------|-------------|
| **PostgreSQL** | Yes (for DB tests) | 2 minutes | Docker Compose |
| **Redis** | Yes (for state tests) | 1 minute | Docker Compose |
| **Zerodha API** | No (unit tests mock it) | 5 minutes | Mock in tests |

**Recommended Approach:**
1. Use Docker Compose for local development
2. Use GitHub Actions services for CI/CD
3. Mock external APIs for unit tests
4. Run integration tests before releases only

**Quick Commands:**
```bash
# Start services
docker-compose -f docker-compose.test.yml up -d

# Run tests
pytest tests/integration/ -v

# Stop services
docker-compose -f docker-compose.test.yml down -v
```

---

**Related Documentation:**
- [Docker Compose Configuration](../docker-compose.yml)
- [Database Schema](../database/schema.sql)
- [Testing Checklist](../Documentation/Checklists/TESTING_CHECKLIST.md)
