#!/usr/bin/env python3
"""
Zerodha Token Manager
Handles Zerodha API authentication with automatic token management
"""

import os
import json
import time
import webbrowser
import stat
import hashlib
import getpass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

from cryptography.fernet import Fernet, InvalidToken
from kiteconnect import KiteConnect
from utilities.structured_logger import get_logger, log_function_call

class ZerodhaTokenManager:
    def __init__(self, api_key: str, api_secret: str, token_file: Optional[str] = None):
        if not api_key or not api_secret:
            raise ValueError("API key and secret are required to initialize ZerodhaTokenManager")
        self.api_key = api_key
        self.api_secret = api_secret
        self.token_file = self._resolve_token_path(token_file)
        self.kite = KiteConnect(api_key=api_key)
        self.access_token = None
        self.token_expiry = None
        self.encryption_key = os.getenv("ZERODHA_TOKEN_KEY")
        self.fernet = self._build_encrypter(self.encryption_key)

    def _resolve_token_path(self, token_file: Optional[str]) -> Path:
        default_dir = Path(os.getenv("ZERODHA_TOKEN_DIR", Path.home() / ".config" / "trading-system"))
        if token_file:
            candidate = Path(token_file).expanduser()
            if not candidate.is_absolute():
                candidate = default_dir / candidate
        else:
            candidate = default_dir / "zerodha_token.json"
        candidate.parent.mkdir(parents=True, exist_ok=True)
        return candidate

    def _build_encrypter(self, key: Optional[str]) -> Optional[Fernet]:
        if not key:
            print("⚠️  ZERODHA_TOKEN_KEY not set – tokens will not be cached on disk.")
            return None
        try:
            key_bytes = key.encode("utf-8")
            return Fernet(key_bytes)
        except Exception as exc:
            print(f"⚠️  Invalid ZERODHA_TOKEN_KEY ({exc}). Token caching disabled.")
            return None

    def _encrypt_token(self, token: str) -> str:
        """Encrypt token using Fernet symmetric encryption"""
        if not self.fernet:
            raise RuntimeError("Encryption key unavailable; cannot encrypt token")
        return self.fernet.encrypt(token.encode()).decode()

    def _decrypt_token(self, encrypted: str) -> str:
        """Decrypt token using Fernet symmetric encryption"""
        if not self.fernet:
            raise RuntimeError("Encryption key unavailable; cannot decrypt token")
        try:
            return self.fernet.decrypt(encrypted.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Encrypted token cannot be decrypted with provided key") from exc

    def save_tokens(self, access_token, expires_at=None):
        """Save tokens to file with encryption and restrictive permissions"""
        if not self.fernet:
            print("⚠️  Skipping token cache: set ZERODHA_TOKEN_KEY to enable encrypted storage.")
            return

        if expires_at is None:
            # Zerodha tokens typically expire at end of trading day
            expires_at = datetime.now().replace(hour=15, minute=30, second=0, microsecond=0)
            if datetime.now() > expires_at:
                expires_at += timedelta(days=1)

        # SECURITY FIX: Encrypt the access token
        encrypted_token = self._encrypt_token(access_token)

        token_data = {
            'encrypted_token': encrypted_token,
            'expires_at': expires_at.isoformat(),
            'created_at': datetime.now().isoformat(),
            'api_key_hash': hashlib.sha256(self.api_key.encode()).hexdigest()
        }

        try:
            # Write to file
            with open(self.token_file, 'w') as f:
                json.dump(token_data, f, indent=2)

            # SECURITY FIX: Set restrictive file permissions (owner read/write only)
            os.chmod(self.token_file, stat.S_IRUSR | stat.S_IWUSR)  # 0o600

            print(f"✅ Tokens saved securely to {self.token_file} (encrypted, permissions: 0600)")
        except Exception as e:
            print(f"⚠️ Could not save tokens: {e}")
    
    def load_tokens(self):
        """Load and decrypt tokens from file"""
        if not self.fernet:
            return None
        try:
            if not self.token_file.exists():
                return None

            # SECURITY CHECK: Verify file permissions
            file_stat = os.stat(self.token_file)
            file_mode = stat.filemode(file_stat.st_mode)
            if file_stat.st_mode & (stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH):
                print(f"⚠️ WARNING: Token file has unsafe permissions ({file_mode}). Should be 0600.")
                print(f"   Run: chmod 600 {self.token_file}")

            with open(self.token_file, 'r') as f:
                token_data = json.load(f)

            # Check if token is for the same API key (compare hashes)
            stored_hash = token_data.get('api_key_hash')
            current_hash = hashlib.sha256(self.api_key.encode()).hexdigest()

            # Support legacy format (plaintext api_key)
            if 'api_key' in token_data:
                if token_data.get('api_key') != self.api_key:
                    print("⚠️ Token file is for different API key")
                    return None
                # Decrypt legacy format
                access_token = token_data.get('access_token')
            elif stored_hash != current_hash:
                print("⚠️ Token file is for different API key")
                return None
            else:
                # SECURITY FIX: Decrypt the token
                encrypted_token = token_data.get('encrypted_token')
                access_token = self._decrypt_token(encrypted_token)

            # Check if token has expired
            expires_at = datetime.fromisoformat(token_data['expires_at'])
            if datetime.now() >= expires_at:
                print("⚠️ Saved token has expired")
                return None

            self.access_token = access_token
            self.token_expiry = expires_at

            print(f"✅ Loaded valid token (expires at {expires_at.strftime('%H:%M:%S')})")
            return access_token

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
    
    def get_valid_token(self, auto_use_existing: bool = False):
        """
        Get a valid access token (load from file or get new one)

        Args:
            auto_use_existing: If True, automatically use existing token without prompting (for testing)

        Returns:
            Valid access token
        """
        print("🔐 Zerodha Authentication Manager")
        print("-" * 40)

        # Try to load existing token
        existing_token = self.load_tokens()
        if existing_token:
            # In auto mode (testing), use existing token automatically
            if auto_use_existing:
                choice = "y"
            else:
                choice = input("🔁 Use existing token? (y/n, default=y): ").strip().lower()

            if choice not in {"n", "no"}:
                self.kite.set_access_token(existing_token)

                # Test if token still works
                try:
                    profile = self.kite.profile()
                    print(f"✅ Using existing token for: {profile.get('user_name', 'Unknown')}")
                    return existing_token
                except Exception as e:
                    print(f"⚠️ Existing token not working: {e}")
            else:
                print("♻️ Existing token ignored — generating a new one.")

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


    # Use correlation context for tracking requests
    # with logger.correlation_context() as corr_id:
    #     logger.info("Processing request", request_id=corr_id)

def main():
    """Test the token manager"""
    print("🧪 Testing Zerodha Token Manager")
    print("="*50)

    # SECURITY FIX: Load credentials from environment variables
    # NEVER hardcode API credentials in source code
    API_KEY = os.environ.get('ZERODHA_API_KEY')
    API_SECRET = os.environ.get('ZERODHA_API_SECRET')

    if not API_KEY or not API_SECRET:
        # CRITICAL SECURITY FIX: Never accept credentials via input() - requires environment variables
        print("❌ ERROR: API credentials not found in environment variables")
        print("\n📋 REQUIRED: Set credentials using environment variables:")
        print("   export ZERODHA_API_KEY='your_api_key'")
        print("   export ZERODHA_API_SECRET='your_api_secret'")
        print("\n💡 For permanent setup, add to ~/.bashrc or ~/.zshrc:")
        print("   echo 'export ZERODHA_API_KEY=\"your_api_key\"' >> ~/.bashrc")
        print("   echo 'export ZERODHA_API_SECRET=\"your_api_secret\"' >> ~/.bashrc")
        print("   source ~/.bashrc")
        print("\n🔒 Security Note: Interactive credential input has been disabled to prevent")
        print("   credentials from appearing in terminal history or process listings.")
        print("\n📄 Alternative: Use the setup_credentials.sh script for guided setup.")
        return 1

    if not os.getenv("ZERODHA_TOKEN_KEY"):
        print("\nℹ️  Optional: set ZERODHA_TOKEN_KEY (Fernet key) to enable encrypted token caching.")
        print("   Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'")
    
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
