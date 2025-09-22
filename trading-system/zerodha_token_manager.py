#!/usr/bin/env python3
"""
Zerodha Token Manager
Handles Zerodha API authentication with automatic token management
"""

import os
import json
import time
import webbrowser
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
from kiteconnect import KiteConnect

class ZerodhaTokenManager:
    def __init__(self, api_key, api_secret, token_file="zerodha_tokens.json"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.token_file = token_file
        self.kite = KiteConnect(api_key=api_key)
        self.access_token = None
        self.token_expiry = None
    
    def save_tokens(self, access_token, expires_at=None):
        """Save tokens to file"""
        if expires_at is None:
            # Zerodha tokens typically expire at end of trading day
            expires_at = datetime.now().replace(hour=15, minute=30, second=0, microsecond=0)
            if datetime.now() > expires_at:
                expires_at += timedelta(days=1)
        
        token_data = {
            'access_token': access_token,
            'expires_at': expires_at.isoformat(),
            'created_at': datetime.now().isoformat(),
            'api_key': self.api_key
        }
        
        try:
            with open(self.token_file, 'w') as f:
                json.dump(token_data, f, indent=2)
            print(f"✅ Tokens saved to {self.token_file}")
        except Exception as e:
            print(f"⚠️ Could not save tokens: {e}")
    
    def load_tokens(self):
        """Load tokens from file"""
        try:
            if not os.path.exists(self.token_file):
                return None
            
            with open(self.token_file, 'r') as f:
                token_data = json.load(f)
            
            # Check if token is for the same API key
            if token_data.get('api_key') != self.api_key:
                print("⚠️ Token file is for different API key")
                return None
            
            # Check if token has expired
            expires_at = datetime.fromisoformat(token_data['expires_at'])
            if datetime.now() >= expires_at:
                print("⚠️ Saved token has expired")
                return None
            
            self.access_token = token_data['access_token']
            self.token_expiry = expires_at
            
            print(f"✅ Loaded valid token (expires at {expires_at.strftime('%H:%M:%S')})")
            return token_data['access_token']
            
        except Exception as e:
            print(f"⚠️ Could not load tokens: {e}")
            return None
    
    def extract_request_token(self, url):
        """Extract request token from redirect URL"""
        try:
            parsed = urlparse(url.strip())
            
            # Check query parameters
            query_params = parse_qs(parsed.query)
            if 'request_token' in query_params:
                return query_params['request_token'][0]
            
            # Check fragment (after #)
            if parsed.fragment:
                fragment_params = parse_qs(parsed.fragment)
                if 'request_token' in fragment_params:
                    return fragment_params['request_token'][0]
            
            # Try to find token in the URL string
            if 'request_token=' in url:
                token_part = url.split('request_token=')[1]
                token = token_part.split('&')[0].split('#')[0]
                return token
            
            raise ValueError("Could not find request_token in URL")
            
        except Exception as e:
            raise ValueError(f"Invalid URL format: {e}")
    
    def get_new_token_interactive(self):
        """Get new token through interactive login"""
        print("\n" + "="*60)
        print("🔐 ZERODHA API AUTHENTICATION")
        print("="*60)
        
        login_url = self.kite.login_url()
        print(f"\n📱 Login URL:")
        print(f"   {login_url}")
        
        # Try to open browser automatically
        try:
            print("\n🌐 Opening login page in browser...")
            webbrowser.open(login_url)
            print("✅ Browser opened")
        except Exception:
            print("⚠️ Could not open browser automatically")
            print("   Please copy and paste the URL above into your browser")
        
        print("\n📋 Instructions:")
        print("1. Login to your Zerodha account in the browser")
        print("2. After login, you'll be redirected to a URL")
        print("3. Copy the COMPLETE redirect URL")
        print("4. Paste it below")
        print("\n⚠️ IMPORTANT: The token expires quickly, so do this fast!")
        
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                print(f"\n🔄 Attempt {attempt + 1}/{max_attempts}")
                redirect_url = input("📎 Paste the complete redirect URL here: ").strip()
                
                if not redirect_url:
                    print("❌ Empty URL provided")
                    continue
                
                print("🔍 Extracting request token...")
                request_token = self.extract_request_token(redirect_url)
                print(f"✅ Found request token: {request_token[:10]}...")
                
                print("🔑 Generating access token...")
                session_data = self.kite.generate_session(request_token, api_secret=self.api_secret)
                
                access_token = session_data.get('access_token')
                if not access_token:
                    raise Exception("No access token in response")
                
                print("✅ Access token generated successfully!")
                
                # Set the access token
                self.kite.set_access_token(access_token)
                self.access_token = access_token
                
                # Save tokens
                self.save_tokens(access_token)
                
                # Test the token
                print("🧪 Testing token...")
                profile = self.kite.profile()
                print(f"✅ Token works! Logged in as: {profile.get('user_name', 'Unknown')}")
                
                return access_token
                
            except Exception as e:
                error_msg = str(e).lower()
                if 'expired' in error_msg or 'invalid' in error_msg:
                    print(f"❌ Token expired or invalid: {e}")
                    print("💡 Try again quickly after getting a fresh URL")
                else:
                    print(f"❌ Error: {e}")
                
                if attempt < max_attempts - 1:
                    print("🔄 Let's try again...")
                    time.sleep(1)
        
        print("\n❌ Failed to get valid token after all attempts")
        return None
    
    def get_valid_token(self):
        """Get a valid access token (load from file or get new one)"""
        print("🔐 Zerodha Authentication Manager")
        print("-" * 40)
        
        # Try to load existing token
        existing_token = self.load_tokens()
        if existing_token:
            self.kite.set_access_token(existing_token)
            
            # Test if token still works
            try:
                profile = self.kite.profile()
                print(f"✅ Using existing token for: {profile.get('user_name', 'Unknown')}")
                return existing_token
            except Exception as e:
                print(f"⚠️ Existing token not working: {e}")
        
        # Get new token
        print("🔄 Getting new authentication token...")
        return self.get_new_token_interactive()
    
    def get_authenticated_kite(self):
        """Get authenticated KiteConnect instance"""
        token = self.get_valid_token()
        if token:
            return self.kite
        else:
            raise Exception("Could not authenticate with Zerodha")

def main():
    """Test the token manager"""
    print("🧪 Testing Zerodha Token Manager")
    print("="*50)
    
    # Your API credentials
    API_KEY = "b0umi99jeas93od0"
    API_SECRET = "8jyer3zt5stm0udso2ir6yqclefot475"
    
    try:
        # Create token manager
        token_manager = ZerodhaTokenManager(API_KEY, API_SECRET)
        
        # Get authenticated kite instance
        kite = token_manager.get_authenticated_kite()
        
        print("\n✅ Authentication successful!")
        
        # Test some API calls
        print("\n🧪 Testing API calls...")
        
        # Get profile
        profile = kite.profile()
        print(f"📋 Profile: {profile.get('user_name')} ({profile.get('email')})")
        
        # Get margins
        margins = kite.margins()
        print(f"💰 Available margin: ₹{margins.get('equity', {}).get('available', {}).get('cash', 0):,.2f}")
        
        # Get positions
        positions = kite.positions()
        print(f"📊 Open positions: {len(positions.get('day', []))}")
        
        print("\n🎉 All tests passed! Token is working correctly.")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())