#!/usr/bin/env python3
"""
Security Context for Trading System
Coordinates KYC verification, AML monitoring, and data protection.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from aml_monitor import AMLMonitor, AMLTransaction
from client_data_protection import ClientDataProtection
from kyc_manager import KYCManager

logger = logging.getLogger("trading_system.security")


class SecurityContext:
    """Central coordinator for security and compliance modules."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}

        self.client_id: str = config.get("client_id") or os.getenv("TRADING_CLIENT_ID", "CLIENT_001")
        self.require_kyc: bool = bool(config.get("require_kyc", True))
        self.enforce_aml: bool = bool(config.get("enforce_aml", True))
        self.aml_alert_threshold: float = float(config.get("aml_alert_threshold", 75))

        kyc_dir = config.get("kyc_data_dir", "kyc_data")
        aml_dir = config.get("aml_data_dir", "aml_data")
        protected_data_dir = config.get("protected_data_dir", "protected_data")

        os.makedirs(kyc_dir, exist_ok=True)
        os.makedirs(aml_dir, exist_ok=True)
        os.makedirs(protected_data_dir, exist_ok=True)

        self.kyc_manager = KYCManager(data_dir=kyc_dir)
        self.aml_monitor = AMLMonitor(data_dir=aml_dir)
        self.data_protection = ClientDataProtection(
            encryption_key=self._resolve_data_encryption_key(config),
            data_dir=protected_data_dir
        )

        self.state_encryption_config = config.get("state_encryption", {})

    def _resolve_data_encryption_key(self, config: Dict[str, Any]) -> Optional[bytes]:
        """Resolve encryption key for client data protection."""
        explicit_key = config.get("data_encryption_key")
        if explicit_key:
            return explicit_key.encode() if isinstance(explicit_key, str) else explicit_key

        env_var = config.get("data_encryption_env", "DATA_ENCRYPTION_KEY")
        if env_var:
            env_value = os.getenv(env_var)
            if env_value:
                return env_value.encode()

        fallback = os.getenv("DATA_ENCRYPTION_KEY")
        if fallback:
            return fallback.encode()

        logger.warning(
            "Data encryption key not configured; generating ephemeral key for ClientDataProtection."
        )
        return None

    # ------------------------------------------------------------------ KYC --
    def ensure_client_authorized(self) -> None:
        """Raise if client has not passed KYC verification."""
        if not self.require_kyc:
            return
        compliant, reason = self.kyc_manager.check_kyc_compliance(self.client_id)
        if not compliant:
            raise PermissionError(f"KYC compliance failed for {self.client_id}: {reason}")

    # ------------------------------------------------------------------ AML --
    def record_trade_for_aml(self, trade: Dict[str, Any]) -> None:
        """Send executed trade to AML monitor."""
        if not self.enforce_aml:
            return

        timestamp = trade.get("timestamp")
        if isinstance(timestamp, datetime):
            timestamp_iso = timestamp.isoformat()
        else:
            timestamp_iso = str(timestamp or datetime.now().isoformat())

        amount = abs(float(trade.get("price", 0.0))) * abs(float(trade.get("shares", 0)))
        transaction = AMLTransaction(
            transaction_id=f"TRADE_{uuid.uuid4().hex}",
            client_id=self.client_id,
            amount=float(amount),
            transaction_type="trade",
            timestamp=timestamp_iso,
            counterparty=trade.get("counterparty", "market"),
            description=f"{trade.get('side', 'hold').upper()} {trade.get('shares', 0)} {trade.get('symbol', '')}"
        )

        self.aml_monitor.record_transaction(transaction)

        risk_score = self.aml_monitor.get_client_risk_score(self.client_id)
        if risk_score >= self.aml_alert_threshold:
            logger.error(
                "🚨 AML risk score %.1f exceeds threshold %.1f for client %s",
                risk_score,
                self.aml_alert_threshold,
                self.client_id
            )
        elif risk_score >= (self.aml_alert_threshold * 0.8):
            logger.warning(
                "⚠️ AML risk score %.1f approaching threshold %.1f for client %s",
                risk_score,
                self.aml_alert_threshold,
                self.client_id
            )

    # --------------------------------------------------------- Data Logging --
    def log_state_access(self, action: str, record_id: str = "trading_state") -> None:
        """Record access attempts for state data."""
        try:
            self.data_protection.log_data_access(
                user_id=self.client_id,
                action=action,
                data_type="portfolio",
                record_id=record_id,
                purpose="state_persistence"
            )
        except Exception as exc:
            logger.debug(f"Failed to log state access: {exc}")

    # ----------------------------------------------------------- Utilities --
    def get_state_encryption_settings(self) -> Dict[str, Any]:
        """Return configuration dict for state encryption."""
        return dict(self.state_encryption_config or {})
