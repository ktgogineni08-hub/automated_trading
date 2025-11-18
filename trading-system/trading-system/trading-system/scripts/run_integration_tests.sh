#!/bin/bash
# Integration Test Runner
# Runs all integration tests with proper setup and reporting

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================================================"
echo "Trading System - Integration Test Suite"
echo "======================================================================"
echo ""

# Check prerequisites
echo "Checking prerequisites..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python 3 found${NC}"

# Check pytest
if ! python3 -c "import pytest" 2>/dev/null; then
    echo -e "${YELLOW}⚠ pytest not installed. Installing...${NC}"
    pip3 install pytest pytest-asyncio pytest-cov
fi
echo -e "${GREEN}✓ pytest available${NC}"

# Check PostgreSQL
if command -v psql &> /dev/null; then
    echo -e "${GREEN}✓ PostgreSQL client found${NC}"
else
    echo -e "${YELLOW}⚠ PostgreSQL client not found (some tests may fail)${NC}"
fi

# Check Redis
if command -v redis-cli &> /dev/null; then
    if redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Redis running${NC}"
    else
        echo -e "${YELLOW}⚠ Redis not running (some tests may fail)${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Redis not found (some tests may fail)${NC}"
fi

echo ""
echo "======================================================================"
echo "Running Integration Tests"
echo "======================================================================"
echo ""

# Navigate to project root
cd "$(dirname "$0")/.."

# Create test results directory
mkdir -p test_results

# Run tests with coverage
python3 -m pytest \
    tests/integration/ \
    -v \
    --tb=short \
    --durations=10 \
    --cov=infrastructure \
    --cov=core \
    --cov-report=html:test_results/coverage_html \
    --cov-report=term-missing \
    --html=test_results/report.html \
    --self-contained-html \
    2>&1 | tee test_results/test_output.log

# Check test result
TEST_EXIT_CODE=$?

echo ""
echo "======================================================================"

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo ""
    echo "Test results saved to:"
    echo "  - Coverage: test_results/coverage_html/index.html"
    echo "  - Report: test_results/report.html"
    echo "  - Log: test_results/test_output.log"
else
    echo -e "${RED}✗ Some tests failed${NC}"
    echo ""
    echo "Check test_results/test_output.log for details"
    exit 1
fi

echo ""
echo "======================================================================"
