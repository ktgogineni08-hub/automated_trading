#!/bin/bash

# Trading System - Secure Credential Setup Script
# This script helps you configure API credentials securely

echo "🔐 Trading System - Secure Credential Setup"
echo "==========================================="
echo ""

# Check if credentials are already set
if [ -n "$ZERODHA_API_KEY" ] && [ -n "$ZERODHA_API_SECRET" ]; then
    echo "✅ Credentials already set in environment"
    echo "   API Key: ${ZERODHA_API_KEY:0:10}..."
    echo ""
    read -p "Do you want to update them? (y/N): " update
    if [ "$update" != "y" ] && [ "$update" != "Y" ]; then
        echo "Keeping existing credentials"
        exit 0
    fi
fi

echo ""
echo "⚠️  IMPORTANT SECURITY NOTES:"
echo "   1. NEVER commit credentials to git"
echo "   2. Get your API credentials from https://kite.zerodha.com/connect/login"
echo "   3. Keep your credentials secure and never share them"
echo ""

# Get API credentials
read -p "Enter your Zerodha API Key: " api_key
read -sp "Enter your Zerodha API Secret: " api_secret
echo ""

# Validate inputs
if [ -z "$api_key" ] || [ -z "$api_secret" ]; then
    echo "❌ Error: Both API Key and Secret are required"
    exit 1
fi

# Detect shell type
if [ -n "$ZSH_VERSION" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -n "$BASH_VERSION" ]; then
    SHELL_RC="$HOME/.bashrc"
else
    SHELL_RC="$HOME/.profile"
fi

echo ""
echo "📝 Configuration Options:"
echo "   1. Current session only (temporary)"
echo "   2. Add to $SHELL_RC (permanent)"
echo ""
read -p "Choose option (1 or 2): " option

case $option in
    1)
        # Set for current session only
        export ZERODHA_API_KEY="$api_key"
        export ZERODHA_API_SECRET="$api_secret"
        echo ""
        echo "✅ Credentials set for current session"
        echo ""
        echo "⚠️  These will be lost when you close the terminal"
        echo "   To make permanent, run this script again and choose option 2"
        ;;
    2)
        # Add to shell RC file
        echo "" >> "$SHELL_RC"
        echo "# Zerodha API Credentials (added by setup_credentials.sh)" >> "$SHELL_RC"
        echo "export ZERODHA_API_KEY=\"$api_key\"" >> "$SHELL_RC"
        echo "export ZERODHA_API_SECRET=\"$api_secret\"" >> "$SHELL_RC"

        # Also set for current session
        export ZERODHA_API_KEY="$api_key"
        export ZERODHA_API_SECRET="$api_secret"

        echo ""
        echo "✅ Credentials added to $SHELL_RC"
        echo "✅ Credentials set for current session"
        echo ""
        echo "🔄 For new terminal sessions, run:"
        echo "   source $SHELL_RC"
        ;;
    *)
        echo "❌ Invalid option"
        exit 1
        ;;
esac

echo ""
echo "🧪 Testing credentials..."
export ZERODHA_API_KEY="$api_key"
export ZERODHA_API_SECRET="$api_secret"

# Verify environment variables are set
if [ -n "$ZERODHA_API_KEY" ] && [ -n "$ZERODHA_API_SECRET" ]; then
    echo "✅ Environment variables verified:"
    echo "   ZERODHA_API_KEY: ${ZERODHA_API_KEY:0:10}...${ZERODHA_API_KEY: -3}"
    echo "   ZERODHA_API_SECRET: ${ZERODHA_API_SECRET:0:10}...***"
else
    echo "❌ Failed to set environment variables"
    exit 1
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Next Steps:"
echo "   1. Delete old token file if it exists: rm -f zerodha_tokens.json"
echo "   2. Ensure secure storage: set ZERODHA_TOKEN_KEY and rerun the token manager"
echo "   3. Test the system: python3 enhanced_trading_system_complete.py --mode paper"
echo "   4. Token cache path: ${ZERODHA_TOKEN_DIR:-$HOME/.config/trading-system}/zerodha_token.json"
echo ""
echo "🔒 Security Reminders:"
echo "   • Never share your API credentials"
echo "   • Rotate keys if you suspect they're compromised"
echo "   • Token cache (~/.config/trading-system/zerodha_token.json) should remain chmod 600"
echo ""
