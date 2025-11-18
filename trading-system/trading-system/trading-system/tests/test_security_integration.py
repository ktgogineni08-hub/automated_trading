import json
from datetime import datetime
from pathlib import Path

import pytest

from core.security_context import SecurityContext
from utilities.state_managers import TradingStateManager


def _security_config(base_dir: Path) -> dict:
    return {
        "client_id": "TEST_CLIENT",
        "require_kyc": True,
        "enforce_aml": True,
        "kyc_data_dir": str(base_dir / "kyc"),
        "aml_data_dir": str(base_dir / "aml"),
        "protected_data_dir": str(base_dir / "protected"),
        "state_encryption": {
            "enabled": True,
            "password": "unit-test-password",
            "filename": "unit_state.enc",
        },
        "aml_alert_threshold": 90,
    }


def _register_verified_client(context: SecurityContext) -> None:
    client_payload = {
        "client_id": context.client_id,
        "name": "Test User",
        "pan_number": "ABCDE1234F",
        "date_of_birth": "1990-01-01",
        "address": "123 Test Street",
        "phone": "9876543210",
        "email": "user@example.com",
        "document_types": ["pan_card", "address_proof"],
    }
    ok, _ = context.kyc_manager.register_client(client_payload)
    if not ok:
        # Client may already exist from previous calls; proceed
        pass
    context.kyc_manager.verify_client_kyc(context.client_id, verified_by="tester")


def test_security_context_enforces_kyc(tmp_path):
    config = _security_config(tmp_path)
    context = SecurityContext(config)

    with pytest.raises(PermissionError):
        context.ensure_client_authorized()

    _register_verified_client(context)
    context.ensure_client_authorized()  # Should not raise


def test_security_context_records_aml_transactions(tmp_path):
    config = _security_config(tmp_path)
    context = SecurityContext(config)
    _register_verified_client(context)

    before = len(context.aml_monitor.transactions)
    context.record_trade_for_aml(
        {
            "timestamp": datetime.now().isoformat(),
            "symbol": "TESTSYMBOL",
            "side": "buy",
            "shares": 5,
            "price": 1234.5,
        }
    )

    assert len(context.aml_monitor.transactions) == before + 1


def test_trading_state_manager_encrypts_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = _security_config(tmp_path)
    config["require_kyc"] = False  # Skip KYC for persistence tests
    context = SecurityContext(config)

    manager = TradingStateManager(base_dir=tmp_path / "state", security_context=context)
    state = {
        "mode": "paper",
        "iteration": 10,
        "trading_day": "2024-01-01",
        "last_update": datetime.now().isoformat(),
        "portfolio": {
            "cash": 150000.0,
            "total_pnl": 1200.0,
            "trades_count": 3,
            "winning_trades": 2,
            "losing_trades": 1,
            "positions": {
                "ABC": {
                    "shares": 10,
                    "entry_price": 100.0,
                    "entry_time": datetime.now(),
                }
            },
        },
        "total_value": 151200.0,
    }

    manager.save_state(state)

    encrypted_path = tmp_path / "state" / "encrypted" / config["state_encryption"]["filename"]
    assert encrypted_path.exists()

    sanitized_path = tmp_path / "state" / "current_state.json"
    assert sanitized_path.exists()
    sanitized = json.loads(sanitized_path.read_text())
    assert "positions" not in sanitized.get("portfolio", {})
    assert sanitized["portfolio"]["positions_count"] == 1

    restored = manager.load_state()
    assert restored["portfolio"]["positions"]["ABC"]["shares"] == 10
