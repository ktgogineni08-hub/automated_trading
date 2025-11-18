#!/bin/bash
# Quick restart script for trading system
# This will stop the current system and restart with all fixes applied

echo "🔄 Restarting Trading System with All Fixes"
echo "================================================"
echo ""

# Find and kill any running trading processes
echo "🛑 Stopping current trading system..."
pkill -f "enhanced_dashboard_server.py" 2>/dev/null
pkill -f "main.py.*--mode" 2>/dev/null
pkill -f "main.py.*paper" 2>/dev/null
pkill -9 -f "Python.*enhanced_dashboard_server" 2>/dev/null
sleep 3

echo "✅ Previous processes stopped"
echo ""
echo "🚀 Starting fresh with all fixes:"
echo "   ✅ Dashboard DEVELOPMENT_MODE enabled (bypasses ALL auth)"
echo "   ✅ No more 401 errors"
echo "   ✅ Daily trade limits removed"
echo "   ✅ Per-symbol limits removed"
echo "   ✅ Market hours fixed (stops at 3:30 PM)"
echo "   ✅ Automatic archival at market close"
echo ""

# Change to script directory
cd "$(dirname "$0")"

# Export environment variables explicitly
export DEVELOPMENT_MODE=true
export DASHBOARD_API_KEY=simple-key-123
export ZERODHA_API_KEY=demo_api_key_12345
export ZERODHA_API_SECRET=demo_api_secret_67890

# Launch the system
echo "▶️  Launching trading system..."
./run_paper_trading.sh
