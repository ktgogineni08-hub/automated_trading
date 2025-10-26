#!/bin/bash
# Quick launcher for F&O Paper Trading
# All fixes applied: dashboard auth, market hours, sector limits, archival

cd "$(dirname "$0")"

echo "🚀 Starting Enhanced F&O Trading System"
echo "📝 Mode: Paper Trading"
echo "🔧 All fixes applied:"
echo "   ✅ Dashboard authentication fixed"
echo "   ✅ Market hours: stops at 3:30 PM"
echo "   ✅ Sector limits: per-index (6 each)"
echo "   ✅ Confidence threshold: 0.70"
echo "   ✅ Automatic archival at market close"
echo ""

# Activate virtual environment
source /Users/gogineni/Python/zerodha-env/bin/activate

# Load environment variables
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Export required variables explicitly
export DASHBOARD_API_KEY=dev-default-key
export DEVELOPMENT_MODE=true
export ZERODHA_API_KEY=demo_api_key_12345
export ZERODHA_API_SECRET=demo_api_secret_67890

# Run trading system
/Users/gogineni/Python/zerodha-env/bin/python main.py --mode paper --skip-auth

echo ""
echo "👋 Trading session ended"
