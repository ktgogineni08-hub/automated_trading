#!/bin/bash
# ==============================================================================
# Trading System Environment Verification Script
# ==============================================================================
# This script verifies that all required environment variables are properly set
#
# Usage:
#   ./scripts/verify_env.sh
# ==============================================================================

set -e

echo "=========================================="
echo "Trading System Environment Verification"
echo "=========================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
ERRORS=0
WARNINGS=0
OK=0

# ------------------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------------------

check_required() {
    local var_name=$1
    local var_desc=$2
    local min_length=${3:-10}
    local var_value=$(eval echo \$$var_name)

    echo -n "Checking $var_name ($var_desc)... "

    if [ -z "$var_value" ]; then
        echo -e "${RED}MISSING${NC}"
        echo "  ❌ $var_name is not set"
        echo "     Required for: $var_desc"
        ((ERRORS++))
        return 1
    elif [ ${#var_value} -lt $min_length ]; then
        echo -e "${YELLOW}TOO SHORT${NC}"
        echo "  ⚠️  $var_name is too short (${#var_value} chars, min: $min_length)"
        echo "     Value: ${var_value:0:10}..."
        ((WARNINGS++))
        return 1
    elif [[ "$var_value" =~ "your_" ]] || [[ "$var_value" =~ "_here" ]]; then
        echo -e "${YELLOW}PLACEHOLDER${NC}"
        echo "  ⚠️  $var_name appears to be a placeholder value"
        echo "     Value: ${var_value:0:30}..."
        ((WARNINGS++))
        return 1
    else
        echo -e "${GREEN}OK${NC}"
        echo "  ✓ Set to: ${var_value:0:15}... (${#var_value} chars)"
        ((OK++))
        return 0
    fi
}

check_optional() {
    local var_name=$1
    local var_desc=$2
    local var_value=$(eval echo \$$var_name)

    echo -n "Checking $var_name ($var_desc)... "

    if [ -z "$var_value" ]; then
        echo -e "${YELLOW}NOT SET${NC}"
        echo "  ℹ️  Optional: $var_desc"
        return 1
    else
        echo -e "${GREEN}SET${NC}"
        echo "  ✓ Value: ${var_value:0:20}..."
        ((OK++))
        return 0
    fi
}

check_mode() {
    local mode="$TRADING_MODE"

    echo -n "Checking TRADING_MODE... "

    if [ -z "$mode" ]; then
        mode="paper"
        echo -e "${YELLOW}NOT SET (using default: paper)${NC}"
        ((WARNINGS++))
        return 1
    elif [ "$mode" != "paper" ] && [ "$mode" != "live" ]; then
        echo -e "${RED}INVALID${NC}"
        echo "  ❌ TRADING_MODE must be 'paper' or 'live', got: $mode"
        ((ERRORS++))
        return 1
    else
        echo -e "${GREEN}OK${NC}"
        echo "  ✓ Mode: $mode"
        ((OK++))

        if [ "$mode" = "live" ]; then
            echo ""
            echo -e "  ${RED}⚠️  WARNING: LIVE TRADING MODE ENABLED!${NC}"
            echo "     This will use REAL MONEY!"
            echo "     Make sure you have:"
            echo "       - Valid Zerodha credentials"
            echo "       - Adequate risk management settings"
            echo "       - Tested thoroughly in paper mode"
            echo ""
        fi

        return 0
    fi
}

# ------------------------------------------------------------------------------
# Required Variables
# ------------------------------------------------------------------------------

echo "REQUIRED VARIABLES (for testing):"
echo "-------------------------------------------"

check_required "DASHBOARD_API_KEY" "Dashboard authentication" 20
check_required "ZERODHA_API_KEY" "Zerodha API access" 10
check_required "ZERODHA_API_SECRET" "Zerodha API secret" 10

echo ""

# ------------------------------------------------------------------------------
# Trading Mode
# ------------------------------------------------------------------------------

echo "TRADING MODE:"
echo "-------------------------------------------"

check_mode

echo ""

# ------------------------------------------------------------------------------
# Optional Variables
# ------------------------------------------------------------------------------

echo "OPTIONAL VARIABLES:"
echo "-------------------------------------------"

check_optional "TRADING_SECURITY_PASSWORD" "State encryption password"
check_optional "DATA_ENCRYPTION_KEY" "Client data encryption"
check_optional "LOG_LEVEL" "Logging verbosity"
check_optional "TRADING_CLIENT_ID" "Client identification"

echo ""

# ------------------------------------------------------------------------------
# Security Checks
# ------------------------------------------------------------------------------

echo "SECURITY CHECKS:"
echo "-------------------------------------------"

# Check for dangerous configurations
echo -n "Checking for dangerous configurations... "

DANGER=0

if [ "$FORCE_DEVELOPMENT_MODE" = "true" ]; then
    echo -e "${RED}FOUND${NC}"
    echo "  ⚠️  FORCE_DEVELOPMENT_MODE=true (disables production safeguards)"
    ((DANGER++))
fi

if [ "$DASHBOARD_DISABLE_TLS_VERIFY" = "true" ]; then
    echo -e "${RED}FOUND${NC}"
    echo "  ⚠️  DASHBOARD_DISABLE_TLS_VERIFY=true (insecure TLS)"
    ((DANGER++))
fi

if [ $DANGER -eq 0 ]; then
    echo -e "${GREEN}NONE${NC}"
    echo "  ✓ No dangerous flags detected"
    ((OK++))
fi

echo ""

# Check .env file existence
echo -n "Checking for .env file... "

if [ -f ".env" ]; then
    echo -e "${GREEN}FOUND${NC}"
    echo "  ✓ .env file exists"
    echo "  ℹ️  Load with: source .env"
else
    echo -e "${YELLOW}NOT FOUND${NC}"
    echo "  ℹ️  No .env file (using shell environment)"
    echo "     Create with: cp .env.example .env"
fi

echo ""

# ------------------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------------------

echo "=========================================="
echo "VERIFICATION SUMMARY"
echo "=========================================="
echo ""
echo -e "${GREEN}✓ Passed:${NC}  $OK"
echo -e "${YELLOW}⚠ Warnings:${NC} $WARNINGS"
echo -e "${RED}✗ Errors:${NC}   $ERRORS"
echo ""

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}=========================================="
    echo "✓ ALL CHECKS PASSED!"
    echo -e "==========================================${NC}"
    echo ""
    echo "Your environment is properly configured."
    echo ""
    echo "Next steps:"
    echo "  1. Run critical tests:"
    echo "     pytest tests/test_critical_fixes.py -v"
    echo ""
    echo "  2. Run full test suite:"
    echo "     pytest tests/ -v"
    echo ""
    exit 0

elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}=========================================="
    echo "⚠ WARNINGS DETECTED"
    echo -e "==========================================${NC}"
    echo ""
    echo "Your environment has warnings but can proceed."
    echo "Review the warnings above."
    echo ""
    echo "To proceed with testing:"
    echo "  pytest tests/test_critical_fixes.py -v"
    echo ""
    exit 0

else
    echo -e "${RED}=========================================="
    echo "✗ ERRORS DETECTED"
    echo -e "==========================================${NC}"
    echo ""
    echo "Please fix the errors above before running tests."
    echo ""
    echo "Quick setup:"
    echo "  source scripts/setup_test_env.sh"
    echo ""
    echo "Or manually set variables:"
    echo "  export DASHBOARD_API_KEY=\"your_key_here\""
    echo "  export ZERODHA_API_KEY=\"your_api_key\""
    echo "  export ZERODHA_API_SECRET=\"your_secret\""
    echo ""
    exit 1
fi
