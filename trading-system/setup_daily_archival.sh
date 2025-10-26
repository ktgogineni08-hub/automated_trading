#!/bin/bash
# Setup Automatic Daily Trade Archival
# This script sets up a cron job to archive trades daily at 3:31 PM IST

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARCHIVE_SCRIPT="$SCRIPT_DIR/archive_daily_trades.py"
PYTHON_BIN=$(which python3)

echo "=========================================="
echo "Daily Trade Archival Setup"
echo "=========================================="
echo ""
echo "This will setup automatic archival of trades at 3:31 PM IST daily"
echo ""

# Check if script exists
if [ ! -f "$ARCHIVE_SCRIPT" ]; then
    echo "❌ Error: Archive script not found at: $ARCHIVE_SCRIPT"
    exit 1
fi

# Make script executable
chmod +x "$ARCHIVE_SCRIPT"
echo "✅ Archive script is executable"

# Create cron entry
CRON_ENTRY="31 15 * * 1-5 cd $SCRIPT_DIR && $PYTHON_BIN $ARCHIVE_SCRIPT >> $SCRIPT_DIR/logs/archival.log 2>&1"

echo ""
echo "Cron job to be added:"
echo "---"
echo "$CRON_ENTRY"
echo "---"
echo ""
echo "This will run:"
echo "  • Every weekday (Monday-Friday)"
echo "  • At 3:31 PM IST (1 minute after market close)"
echo "  • Log output to: $SCRIPT_DIR/logs/archival.log"
echo ""

# Check if cron job already exists
EXISTING_CRON=$(crontab -l 2>/dev/null | grep -F "archive_daily_trades.py" || true)

if [ ! -z "$EXISTING_CRON" ]; then
    echo "⚠️  Cron job already exists:"
    echo "$EXISTING_CRON"
    echo ""
    read -p "Do you want to update it? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 0
    fi
    # Remove existing entry
    crontab -l 2>/dev/null | grep -vF "archive_daily_trades.py" | crontab -
    echo "✅ Removed old cron entry"
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

echo "✅ Cron job added successfully!"
echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "📅 Trades will be automatically archived daily at 3:31 PM IST"
echo ""
echo "To verify:"
echo "  crontab -l | grep archive_daily_trades"
echo ""
echo "To test manually:"
echo "  python3 archive_daily_trades.py"
echo ""
echo "To view logs:"
echo "  tail -f logs/archival.log"
echo ""
echo "To remove:"
echo "  crontab -e  (then delete the archive_daily_trades line)"
echo ""
