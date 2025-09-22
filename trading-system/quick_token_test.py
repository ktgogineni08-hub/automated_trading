#!/usr/bin/env python3
"""
Quick Token Test
Fast way to test and get Zerodha authentication working
"""

import webbrowser
import time
from zerodha_token_manager import ZerodhaTokenManager

def main():
    print("⚡ QUICK ZERODHA TOKEN TEST")
    print("="*40)
    
    # Your API credentials
    API_KEY = "b0umi99jeas93od0"
    API_SECRET = "8jyer3zt5stm0udso2ir6yqclefot475"
    
    print("🔐 Testing Zerodha authentication...")
    print("💡 This will help you get authenticated quickly")
    
    try:
        # Create token manager
        token_manager = ZerodhaTokenManager(API_KEY, API_SECRET)
        
        # Get authenticated kite instance
        kite = token_manager.get_authenticated_kite()
        
        if kite:
            print("\n🎉 SUCCESS! Authentication working!")
            
            # Quick test
            profile = kite.profile()
            print(f"✅ Logged in as: {profile.get('user_name')}")
            print(f"✅ Email: {profile.get('email')}")
            
            # Check margins
            try:
                margins = kite.margins()
                cash = margins.get('equity', {}).get('available', {}).get('cash', 0)
                print(f"✅ Available cash: ₹{cash:,.2f}")
            except Exception as e:
                print(f"⚠️ Could not fetch margins: {e}")
            
            print("\n🚀 Ready to run trading system!")
            print("   Use: python improved_trading_system.py")
            
        else:
            print("\n❌ Authentication failed")
            print("💡 Tips:")
            print("   - Make sure you're logged into Zerodha Kite")
            print("   - Get the redirect URL quickly (token expires fast)")
            print("   - Copy the COMPLETE URL after login")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())