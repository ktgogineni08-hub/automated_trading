"""
HMAC Authentication - API Request Signing

Implements HMAC-based request signing for secure API communication.
Prevents request tampering and replay attacks.

Features:
- HMAC-SHA256 request signing
- Timestamp-based replay protection
- Nonce support
- API key rotation support
- Request validation

Author: Trading System Security Team
Date: November 2025
"""

import hmac
import hashlib
import time
import secrets
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify

logger = logging.getLogger(__name__)


class HMACAuthenticator:
    """
    HMAC-based request authentication
    """

    def __init__(
        self,
        secret_key: str,
        timestamp_tolerance: int = 300,  # 5 minutes
        enable_nonce: bool = True,
        nonce_store=None
    ):
        """
        Initialize HMAC authenticator

        Args:
            secret_key: Secret key for HMAC signing
            timestamp_tolerance: Maximum age of request in seconds
            enable_nonce: Enable nonce-based replay protection
            nonce_store: Storage for used nonces (Redis recommended)
        """
        self.secret_key = secret_key.encode('utf-8')
        self.timestamp_tolerance = timestamp_tolerance
        self.enable_nonce = enable_nonce
        self.nonce_store = nonce_store or set()  # In-memory fallback

    def sign_request(
        self,
        method: str,
        path: str,
        body: str = "",
        timestamp: Optional[int] = None,
        nonce: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Sign an API request

        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path
            body: Request body (for POST/PUT)
            timestamp: Unix timestamp (if None, uses current time)
            nonce: Unique request identifier (if None, generates one)

        Returns:
            Dict with signature headers
        """
        if timestamp is None:
            timestamp = int(time.time())

        if nonce is None and self.enable_nonce:
            nonce = secrets.token_hex(16)

        # Build signature string
        signature_string = self._build_signature_string(
            method, path, body, timestamp, nonce
        )

        # Generate HMAC signature
        signature = hmac.new(
            self.secret_key,
            signature_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # Return headers
        headers = {
            'X-Signature': signature,
            'X-Timestamp': str(timestamp)
        }

        if self.enable_nonce:
            headers['X-Nonce'] = nonce

        return headers

    def verify_request(
        self,
        method: str,
        path: str,
        body: str = "",
        signature: str = "",
        timestamp: str = "",
        nonce: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify a signed request

        Args:
            method: HTTP method
            path: Request path
            body: Request body
            signature: Provided signature
            timestamp: Provided timestamp
            nonce: Provided nonce

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate timestamp
        try:
            request_time = int(timestamp)
        except (ValueError, TypeError):
            return False, "Invalid timestamp format"

        current_time = int(time.time())
        time_diff = abs(current_time - request_time)

        if time_diff > self.timestamp_tolerance:
            logger.warning(
                f"Request timestamp outside tolerance: "
                f"{time_diff}s (max: {self.timestamp_tolerance}s)"
            )
            return False, f"Request timestamp too old ({time_diff}s)"

        # Validate nonce (prevent replay attacks)
        if self.enable_nonce:
            if not nonce:
                return False, "Nonce required but not provided"

            if self._is_nonce_used(nonce):
                logger.warning(f"Replay attack detected: nonce {nonce} already used")
                return False, "Request nonce already used (replay attack?)"

            # Mark nonce as used
            self._mark_nonce_used(nonce, ttl=self.timestamp_tolerance)

        # Build expected signature string
        signature_string = self._build_signature_string(
            method, path, body, request_time, nonce
        )

        # Calculate expected signature
        expected_signature = hmac.new(
            self.secret_key,
            signature_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # Constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(signature, expected_signature):
            logger.warning(f"Invalid signature for {method} {path}")
            return False, "Invalid signature"

        return True, None

    def _build_signature_string(
        self,
        method: str,
        path: str,
        body: str,
        timestamp: int,
        nonce: Optional[str]
    ) -> str:
        """
        Build the canonical string to sign

        Args:
            method: HTTP method
            path: Request path
            body: Request body
            timestamp: Unix timestamp
            nonce: Request nonce

        Returns:
            Canonical signature string
        """
        components = [
            method.upper(),
            path,
            str(timestamp)
        ]

        if body:
            # Hash body to keep signature string length consistent
            body_hash = hashlib.sha256(body.encode('utf-8')).hexdigest()
            components.append(body_hash)

        if self.enable_nonce and nonce:
            components.append(nonce)

        return "\n".join(components)

    def _is_nonce_used(self, nonce: str) -> bool:
        """
        Check if nonce has been used

        Args:
            nonce: Nonce to check

        Returns:
            True if nonce was already used
        """
        if hasattr(self.nonce_store, 'exists'):
            # Redis-like interface
            return bool(self.nonce_store.exists(f"nonce:{nonce}"))
        else:
            # In-memory set
            return nonce in self.nonce_store

    def _mark_nonce_used(self, nonce: str, ttl: int):
        """
        Mark nonce as used

        Args:
            nonce: Nonce to mark
            ttl: Time to live in seconds
        """
        if hasattr(self.nonce_store, 'setex'):
            # Redis-like interface
            self.nonce_store.setex(f"nonce:{nonce}", ttl, "1")
        else:
            # In-memory set (no TTL support)
            self.nonce_store.add(nonce)


class HMACFlaskMiddleware:
    """
    Flask middleware for HMAC authentication
    """

    def __init__(self, app=None, authenticator: HMACAuthenticator = None):
        """
        Initialize middleware

        Args:
            app: Flask app instance
            authenticator: HMAC authenticator instance
        """
        self.authenticator = authenticator
        if app:
            self.init_app(app)

    def init_app(self, app):
        """
        Initialize Flask app with HMAC middleware

        Args:
            app: Flask app instance
        """
        app.before_request(self.verify_signature)

    def verify_signature(self):
        """Flask before_request handler to verify HMAC signature"""
        # Skip verification for certain endpoints
        if self._should_skip_verification():
            return None

        # Extract signature headers
        signature = request.headers.get('X-Signature', '')
        timestamp = request.headers.get('X-Timestamp', '')
        nonce = request.headers.get('X-Nonce')

        # Get request details
        method = request.method
        path = request.path
        body = request.get_data(as_text=True)

        # Verify signature
        is_valid, error = self.authenticator.verify_request(
            method=method,
            path=path,
            body=body,
            signature=signature,
            timestamp=timestamp,
            nonce=nonce
        )

        if not is_valid:
            logger.warning(
                f"HMAC verification failed for {method} {path}: {error}"
            )
            return jsonify({
                'error': 'UNAUTHORIZED',
                'message': 'Invalid request signature',
                'details': error
            }), 401

        return None

    def _should_skip_verification(self) -> bool:
        """
        Determine if verification should be skipped for this request

        Returns:
            True if should skip
        """
        # Skip for health check endpoints
        if request.path in ['/health', '/ready', '/metrics']:
            return True

        # Skip for public endpoints
        if request.path.startswith('/public/'):
            return True

        # Skip for login endpoint (uses different auth)
        if request.path == '/api/v1/auth/login':
            return True

        return False


def hmac_required(authenticator: HMACAuthenticator):
    """
    Decorator for protecting individual endpoints with HMAC authentication

    Args:
        authenticator: HMAC authenticator instance

    Returns:
        Decorator function
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Extract headers
            signature = request.headers.get('X-Signature', '')
            timestamp = request.headers.get('X-Timestamp', '')
            nonce = request.headers.get('X-Nonce')

            # Verify signature
            is_valid, error = authenticator.verify_request(
                method=request.method,
                path=request.path,
                body=request.get_data(as_text=True),
                signature=signature,
                timestamp=timestamp,
                nonce=nonce
            )

            if not is_valid:
                return jsonify({
                    'error': 'UNAUTHORIZED',
                    'message': 'Invalid request signature',
                    'details': error
                }), 401

            return f(*args, **kwargs)

        return decorated_function
    return decorator


# API Key Management
class APIKeyManager:
    """
    Manage API keys and their rotation
    """

    def __init__(self, key_store):
        """
        Initialize API key manager

        Args:
            key_store: Storage for API keys (database or Redis)
        """
        self.key_store = key_store

    def generate_api_key(self, user_id: str) -> Tuple[str, str]:
        """
        Generate new API key and secret

        Args:
            user_id: User identifier

        Returns:
            Tuple of (api_key, api_secret)
        """
        api_key = f"ak_{secrets.token_urlsafe(32)}"
        api_secret = secrets.token_urlsafe(48)

        # Store key
        self.key_store.set(
            f"api_key:{api_key}",
            {
                'user_id': user_id,
                'secret': api_secret,
                'created_at': datetime.now().isoformat(),
                'status': 'active'
            }
        )

        logger.info(f"Generated API key for user {user_id}: {api_key}")
        return api_key, api_secret

    def rotate_api_key(self, old_api_key: str) -> Tuple[str, str]:
        """
        Rotate API key (generate new, deprecate old)

        Args:
            old_api_key: Old API key to rotate

        Returns:
            Tuple of (new_api_key, new_api_secret)
        """
        # Get old key info
        old_key_info = self.key_store.get(f"api_key:{old_api_key}")
        if not old_key_info:
            raise ValueError("API key not found")

        user_id = old_key_info['user_id']

        # Generate new key
        new_api_key, new_api_secret = self.generate_api_key(user_id)

        # Mark old key as deprecated (allow grace period)
        old_key_info['status'] = 'deprecated'
        old_key_info['deprecated_at'] = datetime.now().isoformat()
        old_key_info['expires_at'] = (
            datetime.now() + timedelta(days=7)
        ).isoformat()

        self.key_store.set(f"api_key:{old_api_key}", old_key_info)

        logger.info(f"Rotated API key for user {user_id}: {old_api_key} -> {new_api_key}")
        return new_api_key, new_api_secret

    def revoke_api_key(self, api_key: str):
        """
        Immediately revoke an API key

        Args:
            api_key: API key to revoke
        """
        key_info = self.key_store.get(f"api_key:{api_key}")
        if key_info:
            key_info['status'] = 'revoked'
            key_info['revoked_at'] = datetime.now().isoformat()
            self.key_store.set(f"api_key:{api_key}", key_info)
            logger.info(f"Revoked API key: {api_key}")


# Example usage
if __name__ == "__main__":
    # Initialize authenticator
    authenticator = HMACAuthenticator(
        secret_key="your-secret-key-here",
        timestamp_tolerance=300,
        enable_nonce=True
    )

    # Sign a request
    headers = authenticator.sign_request(
        method="POST",
        path="/api/v1/orders",
        body='{"symbol": "RELIANCE", "quantity": 100}'
    )

    print("Request Headers:")
    for key, value in headers.items():
        print(f"  {key}: {value}")

    # Verify the request
    is_valid, error = authenticator.verify_request(
        method="POST",
        path="/api/v1/orders",
        body='{"symbol": "RELIANCE", "quantity": 100}',
        signature=headers['X-Signature'],
        timestamp=headers['X-Timestamp'],
        nonce=headers.get('X-Nonce')
    )

    print(f"\nVerification Result: {is_valid}")
    if error:
        print(f"Error: {error}")
