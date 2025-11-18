import ipaddress
import json
import socketserver
import ssl
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import requests
import urllib3
from cryptography import x509
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from enhanced_dashboard_server import SecureDashboardHandler
from zerodha_token_manager import ZerodhaTokenManager

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _generate_dev_certificate(base_dir: Path) -> tuple[Path, Path]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(x509.NameOID.COUNTRY_NAME, "IN"),
            x509.NameAttribute(x509.NameOID.STATE_OR_PROVINCE_NAME, "Karnataka"),
            x509.NameAttribute(x509.NameOID.LOCALITY_NAME, "Bengaluru"),
            x509.NameAttribute(x509.NameOID.ORGANIZATION_NAME, "Trading System Tests"),
            x509.NameAttribute(x509.NameOID.COMMON_NAME, "localhost"),
        ]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    cert_path = base_dir / "test_cert.pem"
    key_path = base_dir / "test_key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


def test_dashboard_https_healthcheck(tmp_path):
    cert_path, key_path = _generate_dev_certificate(tmp_path)

    handler = SecureDashboardHandler
    handler.API_KEY = "test-key"

    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    try:
        port = httpd.server_address[1]
        response = requests.get(
            f"https://127.0.0.1:{port}/health",
            headers={"X-API-Key": "test-key"},
            verify=False,
            timeout=5,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    finally:
        httpd.shutdown()
        thread.join(timeout=2)


class StubKite:
    def __init__(self, api_key):
        self.api_key = api_key
        self.access_token = None
        self.profile_calls = 0

    def set_access_token(self, token):
        self.access_token = token

    def profile(self):
        self.profile_calls += 1
        if not self.access_token:
            raise Exception("Not authenticated")
        return {"user_name": "Stub Trader"}

    def login_url(self):
        return "https://kite.zerodha.com/login"

    def generate_session(self, request_token, api_secret=None):
        return {"access_token": "fresh-token"}


@pytest.fixture(autouse=True)
def patch_kite(monkeypatch):
    monkeypatch.setattr("zerodha_token_manager.KiteConnect", StubKite)


def test_token_manager_lifecycle(tmp_path, monkeypatch):
    encryption_key = Fernet.generate_key().decode()
    monkeypatch.setenv("ZERODHA_TOKEN_KEY", encryption_key)

    token_file = tmp_path / "zerodha_token.json"
    manager = ZerodhaTokenManager("api-key", "api-secret", token_file=str(token_file))

    manager.save_tokens("valid-token", expires_at=datetime.now() + timedelta(hours=1))
    raw_json = token_file.read_text()
    assert "valid-token" not in raw_json  # Token must be encrypted

    loaded = manager.load_tokens()
    assert loaded == "valid-token"
    assert manager.access_token == "valid-token"
    manager.kite.set_access_token(loaded)
    assert manager.kite.profile() == {"user_name": "Stub Trader"}

    calls = []

    def fake_new_token():
        calls.append("new")
        return "fresh-token"

    manager.get_new_token_interactive = fake_new_token
    token = manager.get_valid_token(auto_use_existing=True)  # Use auto mode for testing
    assert token == "valid-token"
    assert calls == []  # Cached token used

    # Write expired token and ensure it is rejected
    manager.save_tokens("expired-token", expires_at=datetime.now() - timedelta(minutes=1))
    assert manager.load_tokens() is None
