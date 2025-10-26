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

        # Set dashboard URL
        self.base_url = base_url or os.environ.get('DASHBOARD_BASE_URL', 'https://localhost:8080')
        env['DASHBOARD_BASE_URL'] = self.base_url

        # Build command
        cmd = [sys.executable, self.dashboard_file]
        if use_https:
            cmd.append('--https')
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

            # Wait for startup
            time.sleep(3)

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

            response = requests.get(
                f"{self.base_url}/health",
                timeout=timeout,
                verify=verify_tls
            )
            return response.status_code == 200

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
