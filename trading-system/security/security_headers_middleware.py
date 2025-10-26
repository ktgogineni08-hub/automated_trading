"""
Security Headers Middleware

Implements comprehensive HTTP security headers to protect against:
- XSS attacks
- Clickjacking
- MIME-type sniffing
- Information disclosure
- Cross-origin attacks

Addresses penetration test findings:
- Missing X-Content-Type-Options
- Missing X-Frame-Options
- Missing Content-Security-Policy
- Information disclosure in headers
"""

from typing import Callable, Dict
from flask import Flask, Response, request
import secrets


class SecurityHeadersMiddleware:
    """
    Flask middleware to add security headers to all responses

    Features:
    - Content Security Policy (CSP)
    - XSS Protection
    - Clickjacking Protection
    - MIME-type Sniffing Protection
    - HSTS (HTTP Strict Transport Security)
    - Referrer Policy
    - Permissions Policy
    - Server header removal
    """

    def __init__(self, app: Flask = None, config: Dict = None):
        self.app = app
        self.config = config or self.get_default_config()

        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask):
        """Initialize middleware with Flask app"""
        app.after_request(self.add_security_headers)
        app.before_request(self.validate_request_headers)

    @staticmethod
    def get_default_config() -> Dict:
        """Get default security headers configuration"""
        return {
            # Content Security Policy
            "CSP": {
                "default-src": ["'self'"],
                "script-src": ["'self'", "'unsafe-inline'"],  # Adjust based on needs
                "style-src": ["'self'", "'unsafe-inline'"],
                "img-src": ["'self'", "data:", "https:"],
                "font-src": ["'self'", "data:"],
                "connect-src": ["'self'"],
                "frame-ancestors": ["'none'"],
                "base-uri": ["'self'"],
                "form-action": ["'self'"]
            },

            # HSTS Configuration
            "HSTS": {
                "max-age": 31536000,  # 1 year
                "includeSubDomains": True,
                "preload": True
            },

            # Feature Policy / Permissions Policy
            "Permissions-Policy": {
                "geolocation": [],
                "microphone": [],
                "camera": [],
                "payment": [],
                "usb": [],
                "magnetometer": [],
                "gyroscope": [],
                "accelerometer": []
            },

            # Referrer Policy
            "Referrer-Policy": "strict-origin-when-cross-origin",

            # X-Frame-Options
            "X-Frame-Options": "DENY",

            # X-Content-Type-Options
            "X-Content-Type-Options": "nosniff",

            # X-XSS-Protection (legacy, but still useful)
            "X-XSS-Protection": "1; mode=block",

            # Remove server header
            "Remove-Server-Header": True,

            # Cross-Origin Policies
            "Cross-Origin-Embedder-Policy": "require-corp",
            "Cross-Origin-Opener-Policy": "same-origin",
            "Cross-Origin-Resource-Policy": "same-origin"
        }

    def build_csp_header(self) -> str:
        """Build Content-Security-Policy header value"""
        csp_config = self.config.get("CSP", {})

        directives = []
        for directive, sources in csp_config.items():
            if sources:
                sources_str = " ".join(sources)
                directives.append(f"{directive} {sources_str}")

        return "; ".join(directives)

    def build_hsts_header(self) -> str:
        """Build Strict-Transport-Security header value"""
        hsts_config = self.config.get("HSTS", {})

        parts = [f"max-age={hsts_config.get('max-age', 31536000)}"]

        if hsts_config.get("includeSubDomains"):
            parts.append("includeSubDomains")

        if hsts_config.get("preload"):
            parts.append("preload")

        return "; ".join(parts)

    def build_permissions_policy_header(self) -> str:
        """Build Permissions-Policy header value"""
        permissions_config = self.config.get("Permissions-Policy", {})

        directives = []
        for feature, allowlist in permissions_config.items():
            if not allowlist:
                directives.append(f"{feature}=()")
            else:
                origins = " ".join(allowlist)
                directives.append(f"{feature}=({origins})")

        return ", ".join(directives)

    def add_security_headers(self, response: Response) -> Response:
        """
        Add security headers to response

        This method is called after each request
        """

        # 1. Content-Security-Policy
        csp = self.build_csp_header()
        if csp:
            response.headers["Content-Security-Policy"] = csp

        # 2. Strict-Transport-Security (HSTS)
        # Only add for HTTPS requests
        if request.is_secure:
            response.headers["Strict-Transport-Security"] = self.build_hsts_header()

        # 3. X-Frame-Options (Clickjacking Protection)
        x_frame_options = self.config.get("X-Frame-Options")
        if x_frame_options:
            response.headers["X-Frame-Options"] = x_frame_options

        # 4. X-Content-Type-Options (MIME-sniffing Protection)
        x_content_type = self.config.get("X-Content-Type-Options")
        if x_content_type:
            response.headers["X-Content-Type-Options"] = x_content_type

        # 5. X-XSS-Protection (Legacy XSS Protection)
        x_xss = self.config.get("X-XSS-Protection")
        if x_xss:
            response.headers["X-XSS-Protection"] = x_xss

        # 6. Referrer-Policy
        referrer_policy = self.config.get("Referrer-Policy")
        if referrer_policy:
            response.headers["Referrer-Policy"] = referrer_policy

        # 7. Permissions-Policy (Feature Policy)
        permissions_policy = self.build_permissions_policy_header()
        if permissions_policy:
            response.headers["Permissions-Policy"] = permissions_policy

        # 8. Cross-Origin Policies
        coep = self.config.get("Cross-Origin-Embedder-Policy")
        if coep:
            response.headers["Cross-Origin-Embedder-Policy"] = coep

        coop = self.config.get("Cross-Origin-Opener-Policy")
        if coop:
            response.headers["Cross-Origin-Opener-Policy"] = coop

        corp = self.config.get("Cross-Origin-Resource-Policy")
        if corp:
            response.headers["Cross-Origin-Resource-Policy"] = corp

        # 9. Remove Server header (information disclosure)
        if self.config.get("Remove-Server-Header"):
            response.headers.pop("Server", None)

        # 10. Cache-Control for sensitive endpoints
        if self._is_sensitive_endpoint(request.path):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        return response

    def validate_request_headers(self):
        """
        Validate incoming request headers

        Reject requests with suspicious headers
        """

        # Check for suspicious User-Agent
        user_agent = request.headers.get("User-Agent", "")
        if self._is_suspicious_user_agent(user_agent):
            return Response(
                "Suspicious request detected",
                status=403,
                headers={"Content-Type": "application/json"}
            )

        # Check for host header injection
        host = request.headers.get("Host", "")
        if not self._is_valid_host(host):
            return Response(
                "Invalid host header",
                status=400,
                headers={"Content-Type": "application/json"}
            )

    @staticmethod
    def _is_sensitive_endpoint(path: str) -> bool:
        """Check if endpoint contains sensitive data"""
        sensitive_paths = [
            "/api/v1/auth/",
            "/api/v1/admin/",
            "/api/v1/orders/",
            "/api/v1/portfolio/",
            "/api/v1/account/"
        ]

        return any(path.startswith(sensitive) for sensitive in sensitive_paths)

    @staticmethod
    def _is_suspicious_user_agent(user_agent: str) -> bool:
        """Detect suspicious user agents"""
        suspicious_patterns = [
            "sqlmap",
            "nikto",
            "nmap",
            "masscan",
            "python-requests/0",  # Default python-requests (often automated)
            "curl/0",
            "wget/0",
            "<script>"  # XSS attempt in user agent
        ]

        user_agent_lower = user_agent.lower()
        return any(pattern in user_agent_lower for pattern in suspicious_patterns)

    @staticmethod
    def _is_valid_host(host: str) -> bool:
        """Validate Host header"""
        if not host:
            return False

        # Allow only expected hosts
        allowed_hosts = [
            "localhost",
            "127.0.0.1",
            "api.trading.example.com",
            "dashboard.trading.example.com"
        ]

        # Extract hostname (remove port if present)
        hostname = host.split(":")[0]

        return hostname in allowed_hosts or hostname.endswith(".trading.example.com")


class CSPNonce:
    """
    Content Security Policy Nonce Generator

    For use with inline scripts/styles that need CSP exception
    """

    def __init__(self):
        self.nonce = None

    def generate(self) -> str:
        """Generate a new nonce for this request"""
        self.nonce = secrets.token_urlsafe(16)
        return self.nonce

    def get_script_tag(self) -> str:
        """Get nonce attribute for script tag"""
        return f'nonce="{self.nonce}"'

    def get_style_tag(self) -> str:
        """Get nonce attribute for style tag"""
        return f'nonce="{self.nonce}"'


# Flask integration helpers
def init_security_headers(app: Flask, config: Dict = None):
    """
    Initialize security headers middleware for Flask app

    Usage:
        from flask import Flask
        from security_headers_middleware import init_security_headers

        app = Flask(__name__)
        init_security_headers(app)
    """
    SecurityHeadersMiddleware(app, config)


def get_production_config() -> Dict:
    """
    Get production-grade security headers configuration

    Stricter than default
    """
    return {
        "CSP": {
            "default-src": ["'none'"],
            "script-src": ["'self'"],
            "style-src": ["'self'"],
            "img-src": ["'self'", "data:"],
            "font-src": ["'self'"],
            "connect-src": ["'self'"],
            "frame-ancestors": ["'none'"],
            "base-uri": ["'self'"],
            "form-action": ["'self'"],
            "upgrade-insecure-requests": []
        },
        "HSTS": {
            "max-age": 63072000,  # 2 years
            "includeSubDomains": True,
            "preload": True
        },
        "Permissions-Policy": {
            "geolocation": [],
            "microphone": [],
            "camera": [],
            "payment": [],
            "usb": [],
            "magnetometer": [],
            "gyroscope": [],
            "accelerometer": [],
            "autoplay": [],
            "encrypted-media": [],
            "fullscreen": [],
            "picture-in-picture": []
        },
        "Referrer-Policy": "no-referrer",
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "X-XSS-Protection": "1; mode=block",
        "Remove-Server-Header": True,
        "Cross-Origin-Embedder-Policy": "require-corp",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Resource-Policy": "same-origin"
    }


# Example usage
if __name__ == "__main__":
    from flask import Flask, jsonify

    app = Flask(__name__)

    # Initialize security headers with production config
    init_security_headers(app, get_production_config())

    @app.route("/health")
    def health():
        return jsonify({"status": "healthy"})

    @app.route("/api/v1/market/quote/<symbol>")
    def get_quote(symbol):
        return jsonify({
            "symbol": symbol,
            "price": 1234.56,
            "timestamp": "2025-10-26T10:00:00Z"
        })

    # Run server
    print("Security headers middleware active")
    print("Testing endpoints:")
    print("  - http://localhost:5000/health")
    print("  - http://localhost:5000/api/v1/market/quote/SBIN")
    print("\nCheck response headers to verify security headers")

    app.run(debug=True, port=5000)
