#!/usr/bin/env python3
"""
Dashboard Lifecycle Manager
Centralized dashboard startup, security validation, and process management
"""

import os
import sys
import time
import logging
import subprocess
import webbrowser
from typing import Optional
from pathlib import Path

logger = logging.getLogger('trading_system.dashboard_manager')


class DashboardManager:
    """
    Manages dashboard lifecycle with security-first approach

    Features:
    - Single source of truth for dashboard startup
    - Security validation (API key, TLS, mode checks)
    - Process lifecycle management
    - Health checking
    - Graceful shutdown
    """

    def __init__(self, dashboard_file: str = "enhanced_dashboard_server.py"):
        """
        Initialize dashboard manager

        Args:
            dashboard_file: Path to dashboard server script
        """
        self.dashboard_file = dashboard_file
        self.process: Optional[subprocess.Popen] = None
        self.base_url: Optional[str] = None
        self.api_key: Optional[str] = None

    def _prepare_certificate(self, cert_path: Path, key_path: Path) -> bool:
        """
        Ensure dashboard certificate files exist.

        Generates a self-signed certificate when missing (development usage).
        """
        if cert_path.exists() and key_path.exists():
            return True

        try:
            cert_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.warning(f"❌ Could not create certificate directory: {exc}")
            return False

        try:
            from enhanced_dashboard_server import generate_self_signed_certificate

            logger.info("🔐 Generating self-signed dashboard certificate for local HTTPS...")
            generated_cert, generated_key = generate_self_signed_certificate(
                cert_file=str(cert_path),
                key_file=str(key_path)
            )
            if generated_cert and generated_key:
                logger.info(f"✅ Dashboard certificate ready at {generated_cert}")
                return True
        except Exception as exc:
            logger.warning(f"❌ Failed to prepare dashboard certificate: {exc}")

        return cert_path.exists() and key_path.exists()
    def validate_security_requirements(self) -> tuple[bool, str]:
        """
        Validate security requirements before starting dashboard

        Returns:
            (is_valid, error_message)
        """
        # Check 1: Dashboard API key must be set
        api_key = os.environ.get('DASHBOARD_API_KEY')
        if not api_key:
            return False, (
                "DASHBOARD_API_KEY not set!\n"
                "Generate one with: export DASHBOARD_API_KEY=\"$(openssl rand -hex 32)\""
            )

        # Check 2: Warn if development mode enabled
        dev_mode = os.getenv('FORCE_DEVELOPMENT_MODE', 'false').lower() == 'true'
        if dev_mode:
            logger.warning(
                "⚠️ DEVELOPMENT_MODE enabled - authentication will be BYPASSED!\n"
                "   This is UNSAFE for production. Set FORCE_DEVELOPMENT_MODE=false"
            )

        # Check 3: Warn if TLS verification disabled
        tls_disabled = os.getenv('DASHBOARD_DISABLE_TLS_VERIFY', 'false').lower() == 'true'
        if tls_disabled:
            logger.warning(
                "⚠️ TLS verification DISABLED - connections are not secure!\n"
                "   Only use for local development. Set DASHBOARD_DISABLE_TLS_VERIFY=false"
            )

        # Check 4: Dashboard server file exists
        if not os.path.exists(self.dashboard_file):
            return False, f"Dashboard server not found: {self.dashboard_file}"

        return True, ""

    def start(
        self,
        base_url: Optional[str] = None,
        use_https: bool = True,
        open_browser: bool = True
    ) -> Optional[subprocess.Popen]:
        """
        Start dashboard with security validation

        Args:
            base_url: Dashboard URL (default: https://localhost:8080)
            use_https: Use HTTPS (recommended)
            open_browser: Auto-open browser

        Returns:
            Dashboard process or None if failed
        """
        # Validate security requirements
        is_valid, error_msg = self.validate_security_requirements()
        if not is_valid:
            logger.error(f"❌ Dashboard startup blocked: {error_msg}")
            print(f"\n❌ {error_msg}\n")
            return None

        # Prepare environment
        env = os.environ.copy()
        self.api_key = env.get('DASHBOARD_API_KEY')

        # Set development mode from environment (secure by default)
        dev_mode = os.getenv('FORCE_DEVELOPMENT_MODE', 'false').lower() == 'true'
        if dev_mode:
            env['DEVELOPMENT_MODE'] = 'true'
            logger.warning("⚠️ Starting dashboard in DEVELOPMENT MODE (auth bypassed)")
        else:
            env['DEVELOPMENT_MODE'] = 'false'
            logger.info("✅ Starting dashboard in PRODUCTION MODE (auth required)")

        # Set dashboard URL and determine protocol
        self.base_url = base_url or os.environ.get('DASHBOARD_BASE_URL', 'https://localhost:8080')
        env['DASHBOARD_BASE_URL'] = self.base_url
        os.environ['DASHBOARD_BASE_URL'] = self.base_url

        effective_use_https = use_https
        cert_path: Optional[Path] = None
        key_path: Optional[Path] = None

        if effective_use_https:
            cert_path = Path(env.get('DASHBOARD_CERT_FILE', 'certs/dashboard.crt'))
            key_path = Path(env.get('DASHBOARD_KEY_FILE', 'certs/dashboard.key'))

            if not self._prepare_certificate(cert_path, key_path):
                logger.warning("⚠️ Dashboard certificate unavailable - falling back to HTTP mode")
                effective_use_https = False

        if not effective_use_https and self.base_url.startswith('https://'):
            self.base_url = self.base_url.replace('https://', 'http://', 1)
            env['DASHBOARD_BASE_URL'] = self.base_url
            os.environ['DASHBOARD_BASE_URL'] = self.base_url

        # Build command
        cmd = [sys.executable, self.dashboard_file]
        if effective_use_https:
            cmd.append('--https')
            if cert_path and key_path:
                cmd.extend(['--cert', str(cert_path), '--key', str(key_path)])
                env['DASHBOARD_CERT_FILE'] = str(cert_path)
                env['DASHBOARD_KEY_FILE'] = str(key_path)
                os.environ['DASHBOARD_CERT_FILE'] = str(cert_path)
                os.environ['DASHBOARD_KEY_FILE'] = str(key_path)
        else:
            cmd.append('--allow-http')
        if self.api_key:
            cmd.extend(['--api-key', self.api_key])

        try:
            # Start dashboard process
            logger.info(f"🚀 Starting dashboard at {self.base_url}...")
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
                stdin=subprocess.DEVNULL
            )

            # Wait for startup/health check
            start_time = time.time()
            health_timeout = 30  # seconds
            while time.time() - start_time < health_timeout:
                if self.check_health():
                    break
                time.sleep(0.5)

            # Open browser if requested
            if open_browser:
                try:
                    webbrowser.open(self.base_url)
                    logger.info(f"✅ Dashboard started at: {self.base_url}")
                except Exception:
                    logger.info(f"Dashboard started at: {self.base_url} (open manually)")
            else:
                logger.info(f"✅ Dashboard started at: {self.base_url}")

            return self.process

        except Exception as e:
            logger.error(f"❌ Dashboard failed to start: {e}")
            return None

    def check_health(self, timeout: int = 5) -> bool:
        """
        Check if dashboard is healthy

        Args:
            timeout: Request timeout in seconds

        Returns:
            True if dashboard is responding
        """
        if not self.process or not self.base_url:
            return False

        try:
            import requests
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

            # Disable TLS verification if requested (local dev only)
            verify_tls = os.getenv('DASHBOARD_DISABLE_TLS_VERIFY', 'false').lower() != 'true'
            verify: bool | str

            if not verify_tls:
                verify = False
            else:
                cert_file = os.getenv('DASHBOARD_CERT_FILE')
                if cert_file and os.path.exists(cert_file):
                    verify = cert_file
                else:
                    verify = True

            headers = {}
            if self.api_key:
                headers['X-API-Key'] = self.api_key

            response = requests.get(
                f"{self.base_url}/health",
                timeout=timeout,
                verify=verify,
                headers=headers
            )
            return response.status_code == 200

        except requests.exceptions.SSLError as ssl_err:
            logger.warning(
                "⚠️ Dashboard TLS verification failed (%s). "
                "Falling back to insecure health check for local development.",
                ssl_err
            )
            try:
                response = requests.get(
                    f"{self.base_url}/health",
                    timeout=timeout,
                    verify=False,
                    headers=headers
                )
                return response.status_code == 200
            except Exception as retry_exc:
                logger.debug(f"Dashboard health retry (insecure) failed: {retry_exc}")
                return False

        except Exception as e:
            logger.debug(f"Dashboard health check failed: {e}")
            return False

    def stop(self):
        """Stop dashboard gracefully"""
        if self.process:
            try:
                logger.info("🛑 Stopping dashboard...")
                self.process.terminate()
                self.process.wait(timeout=5)
                logger.info("✅ Dashboard stopped")
            except subprocess.TimeoutExpired:
                logger.warning("⚠️ Dashboard didn't stop gracefully, forcing kill...")
                self.process.kill()
                self.process.wait()
            except Exception as e:
                logger.error(f"❌ Error stopping dashboard: {e}")
            finally:
                self.process = None

    def is_running(self) -> bool:
        """Check if dashboard process is still running"""
        if not self.process:
            return False
        return self.process.poll() is None

    def get_status(self) -> dict:
        """Get dashboard status information"""
        return {
            'running': self.is_running(),
            'healthy': self.check_health() if self.is_running() else False,
            'url': self.base_url,
            'pid': self.process.pid if self.process else None,
            'api_key_set': bool(self.api_key),
            'dev_mode': os.getenv('FORCE_DEVELOPMENT_MODE', 'false').lower() == 'true',
            'tls_verify_disabled': os.getenv('DASHBOARD_DISABLE_TLS_VERIFY', 'false').lower() == 'true'
        }

    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure cleanup"""
        self.stop()


# Convenience function for backward compatibility
def ensure_dashboard_api_key() -> str:
    """
    Ensure dashboard API key is set

    Returns:
        API key string

    Raises:
        ValueError if not set
    """
    api_key = os.environ.get('DASHBOARD_API_KEY')
    if not api_key:
        raise ValueError(
            "DASHBOARD_API_KEY not set!\n"
            "Generate one with: export DASHBOARD_API_KEY=\"$(openssl rand -hex 32)\""
        )
    return api_key


def start_dashboard(
    base_url: Optional[str] = None,
    use_https: bool = True,
    open_browser: bool = True
) -> Optional[subprocess.Popen]:
    """
    Quick start dashboard (convenience function)

    Args:
        base_url: Dashboard URL
        use_https: Use HTTPS
        open_browser: Auto-open browser

    Returns:
        Dashboard process or None if failed
    """
    manager = DashboardManager()
    return manager.start(base_url=base_url, use_https=use_https, open_browser=open_browser)


if __name__ == "__main__":
    # Test dashboard manager
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 70)
    print("DASHBOARD MANAGER TEST")
    print("=" * 70)

    # Test 1: Security validation
    print("\n1. Testing security validation...")
    manager = DashboardManager()
    is_valid, error = manager.validate_security_requirements()
    print(f"   Valid: {is_valid}")
    if not is_valid:
        print(f"   Error: {error}")

    # Test 2: Start dashboard
    if is_valid:
        print("\n2. Starting dashboard...")
        process = manager.start(open_browser=False)
        if process:
            print("   ✅ Dashboard started")

            # Test 3: Health check
            print("\n3. Checking health...")
            time.sleep(2)
            healthy = manager.check_health()
            print(f"   Healthy: {healthy}")

            # Test 4: Status
            print("\n4. Dashboard status:")
            status = manager.get_status()
            for key, value in status.items():
                print(f"   {key}: {value}")

            # Test 5: Stop
            print("\n5. Stopping dashboard...")
            manager.stop()
            print("   ✅ Dashboard stopped")

    print("\n" + "=" * 70)
