#!/bin/bash
# ==============================================================================
# Trading System Test Environment Setup Script
# ==============================================================================
# This script helps you configure environment variables for running the test suite
#
# Usage:
#   source scripts/setup_test_env.sh
#   OR
#   . scripts/setup_test_env.sh
#
# Note: Must use 'source' or '.' to export variables to your current shell
# ==============================================================================

set -e

echo "=========================================="
echo "Trading System Test Environment Setup"
echo "=========================================="
echo ""

# ------------------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------------------

generate_random_key() {
    # Generate random hex string (32 bytes = 64 hex chars)
    if command -v openssl &> /dev/null; then
        openssl rand -hex 32
    else
        # Fallback to Python
        python3 -c "import secrets; print(secrets.token_hex(32))"
    fi
}

check_env_var() {
    local var_name=$1
    local var_value=$(eval echo \$$var_name)

    if [ -n "$var_value" ]; then
        echo "  ✓ $var_name is set"
        return 0
    else
        echo "  ✗ $var_name is NOT set"
        return 1
    fi
}

# ------------------------------------------------------------------------------
# Check Current Environment
# ------------------------------------------------------------------------------

echo "Current Environment Status:"
echo "-------------------------------------------"

all_set=true

check_env_var "DASHBOARD_API_KEY" || all_set=false
check_env_var "ZERODHA_API_KEY" || all_set=false
check_env_var "ZERODHA_API_SECRET" || all_set=false

echo ""

# ------------------------------------------------------------------------------
# Offer to Set Up Test Environment
# ------------------------------------------------------------------------------

if [ "$all_set" = true ]; then
    echo "✓ All required variables are already set!"
    echo ""
    echo "Current values:"
    echo "  DASHBOARD_API_KEY: ${DASHBOARD_API_KEY:0:10}..."
    echo "  ZERODHA_API_KEY: ${ZERODHA_API_KEY:0:10}..."
    echo "  ZERODHA_API_SECRET: ${ZERODHA_API_SECRET:0:10}..."
    echo ""
    read -p "Do you want to reconfigure? (y/N): " reconfigure

    if [[ ! "$reconfigure" =~ ^[Yy]$ ]]; then
        echo "Keeping existing configuration."
        return 0 2>/dev/null || exit 0
    fi
fi

echo "Setting up test environment..."
echo ""

# ------------------------------------------------------------------------------
# Setup Mode Selection
# ------------------------------------------------------------------------------

echo "Select setup mode:"
echo "  1) Testing/Development (auto-generate safe test credentials)"
echo "  2) Production (enter your actual Zerodha credentials)"
echo ""
read -p "Enter choice (1 or 2): " setup_mode

echo ""

# ------------------------------------------------------------------------------
# Configure Based on Mode
# ------------------------------------------------------------------------------

if [ "$setup_mode" = "1" ]; then
    echo "🧪 Configuring TEST environment (safe for development)..."
    echo ""

    # Generate test credentials
    export DASHBOARD_API_KEY="test_dashboard_key_$(generate_random_key | cut -c1-32)"
    export ZERODHA_API_KEY="test_api_key_1234567890abcdef"
    export ZERODHA_API_SECRET="test_api_secret_1234567890abcdef"
    export TRADING_MODE="paper"

    echo "✓ Generated test credentials:"
    echo "  DASHBOARD_API_KEY: ${DASHBOARD_API_KEY:0:20}..."
    echo "  ZERODHA_API_KEY: $ZERODHA_API_KEY"
    echo "  ZERODHA_API_SECRET: $ZERODHA_API_SECRET"
    echo "  TRADING_MODE: $TRADING_MODE"
    echo ""
    echo "⚠️  These are DUMMY credentials for testing only!"
    echo "   They will work for paper trading and tests, but NOT for live trading."

elif [ "$setup_mode" = "2" ]; then
    echo "🚀 Configuring PRODUCTION environment (real credentials)..."
    echo ""
    echo "⚠️  WARNING: You are about to enter real credentials!"
    echo "   Make sure you are in a secure environment."
    echo ""

    # Dashboard API Key
    echo "1. Dashboard API Key"
    echo "   Generate with: openssl rand -hex 32"
    read -p "   Enter DASHBOARD_API_KEY (or press Enter to generate): " dashboard_key

    if [ -z "$dashboard_key" ]; then
        export DASHBOARD_API_KEY=$(generate_random_key)
        echo "   ✓ Generated: ${DASHBOARD_API_KEY:0:20}..."
    else
        export DASHBOARD_API_KEY="$dashboard_key"
        echo "   ✓ Set to: ${DASHBOARD_API_KEY:0:20}..."
    fi
    echo ""

    # Zerodha API Key
    echo "2. Zerodha API Key"
    echo "   Get from: https://kite.zerodha.com/connect/login"
    read -p "   Enter ZERODHA_API_KEY: " zerodha_key
    export ZERODHA_API_KEY="$zerodha_key"
    echo "   ✓ Set to: ${ZERODHA_API_KEY:0:10}..."
    echo ""

    # Zerodha API Secret
    echo "3. Zerodha API Secret"
    read -p "   Enter ZERODHA_API_SECRET: " zerodha_secret
    export ZERODHA_API_SECRET="$zerodha_secret"
    echo "   ✓ Set to: ${ZERODHA_API_SECRET:0:10}..."
    echo ""

    # Trading Mode
    echo "4. Trading Mode"
    read -p "   Enter TRADING_MODE (paper/live) [paper]: " trading_mode
    export TRADING_MODE="${trading_mode:-paper}"
    echo "   ✓ Set to: $TRADING_MODE"
    echo ""

    if [ "$TRADING_MODE" = "live" ]; then
        echo ""
        echo "⚠️  ⚠️  ⚠️  WARNING ⚠️  ⚠️  ⚠️"
        echo "You have configured LIVE TRADING mode!"
        echo "This will use REAL MONEY!"
        echo "Make sure you understand the risks."
        echo "⚠️  ⚠️  ⚠️  WARNING ⚠️  ⚠️  ⚠️"
        echo ""
    fi

else
    echo "❌ Invalid choice. Exiting."
    return 1 2>/dev/null || exit 1
fi

# ------------------------------------------------------------------------------
# Optional: State Encryption
# ------------------------------------------------------------------------------

echo ""
read -p "Do you want to enable state encryption? (y/N): " enable_encryption

if [[ "$enable_encryption" =~ ^[Yy]$ ]]; then
    read -p "Enter TRADING_SECURITY_PASSWORD (min 16 chars): " security_password
    export TRADING_SECURITY_PASSWORD="$security_password"
    echo "✓ State encryption enabled"
else
    echo "ℹ️  State encryption disabled (optional for testing)"
fi

# ------------------------------------------------------------------------------
# Save to .env file (optional)
# ------------------------------------------------------------------------------

echo ""
read -p "Do you want to save these settings to .env file? (y/N): " save_to_file

if [[ "$save_to_file" =~ ^[Yy]$ ]]; then
    cat > .env << EOF
# Trading System Environment Configuration
# Generated: $(date)
# Mode: $([ "$setup_mode" = "1" ] && echo "Testing/Development" || echo "Production")

export DASHBOARD_API_KEY="$DASHBOARD_API_KEY"
export ZERODHA_API_KEY="$ZERODHA_API_KEY"
export ZERODHA_API_SECRET="$ZERODHA_API_SECRET"
export TRADING_MODE="$TRADING_MODE"
EOF

    if [ -n "$TRADING_SECURITY_PASSWORD" ]; then
        echo "export TRADING_SECURITY_PASSWORD=\"$TRADING_SECURITY_PASSWORD\"" >> .env
    fi

    echo "✓ Settings saved to .env"
    echo "  To load in future: source .env"
else
    echo "ℹ️  Settings NOT saved to file (only in current session)"
fi

# ------------------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------------------

echo ""
echo "=========================================="
echo "✓ Environment Configuration Complete!"
echo "=========================================="
echo ""
echo "Environment variables set:"
echo "  DASHBOARD_API_KEY: ${DASHBOARD_API_KEY:0:20}..."
echo "  ZERODHA_API_KEY: ${ZERODHA_API_KEY:0:15}..."
echo "  ZERODHA_API_SECRET: ${ZERODHA_API_SECRET:0:15}..."
echo "  TRADING_MODE: $TRADING_MODE"
[ -n "$TRADING_SECURITY_PASSWORD" ] && echo "  TRADING_SECURITY_PASSWORD: [SET]"
echo ""
echo "Next steps:"
echo "  1. Verify configuration: ./scripts/verify_env.sh"
echo "  2. Run critical tests: pytest tests/test_critical_fixes.py -v"
echo "  3. Run full test suite: pytest tests/ -v"
echo ""
echo "=========================================="
