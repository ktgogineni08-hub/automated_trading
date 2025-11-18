#!/usr/bin/env python3
"""
Anti-Money Laundering (AML) Monitoring Module
SEBI Compliance: Anti-money laundering compliance requirements
"""

import logging
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger('trading_system.aml_monitor')


class AMLAlertLevel(Enum):
    """AML alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AMLTransaction:
    """AML transaction record"""
    transaction_id: str
    client_id: str
    amount: float
    transaction_type: str  # 'deposit', 'withdrawal', 'trade'
    timestamp: str
    counterparty: Optional[str] = None
    description: Optional[str] = None


@dataclass
class AMLAlert:
    """AML alert record"""
    alert_id: str
    client_id: str
    alert_type: str
    severity: AMLAlertLevel
    description: str
    timestamp: str
    amount_involved: float
    suspicious_patterns: List[str]
    status: str = "active"  # 'active', 'investigating', 'resolved', 'false_positive'


class AMLMonitor:
    """
    Anti-Money Laundering monitoring system per SEBI guidelines

    SEBI Requirements:
    - Monitor suspicious trading patterns
    - Large transaction reporting
    - Client behavior analysis
    - Regulatory reporting obligations
    """

    def __init__(self, data_dir: str = "aml_data"):
        self.data_dir = data_dir
        self.transactions: List[AMLTransaction] = []
        self.alerts: List[AMLAlert] = []
        self.client_profiles: Dict[str, Dict] = {}
        self.suspicious_patterns: Dict[str, List] = {}

        # SEBI thresholds
        self.large_transaction_threshold = 1000000  # ₹10 lakh
        self.suspicious_volume_threshold = 10000000  # ₹1 crore daily
        self.unusual_pattern_threshold = 5  # Number of suspicious indicators

        self._load_data()

    def record_transaction(self, transaction: AMLTransaction) -> None:
        """
        Record transaction for AML monitoring

        Args:
            transaction: AMLTransaction object
        """
        self.transactions.append(transaction)

        # Check for immediate suspicious patterns
        self._analyze_transaction(transaction)

        # Keep only last 90 days of transactions
        cutoff_date = datetime.now() - timedelta(days=90)
        self.transactions = [
            t for t in self.transactions
            if datetime.fromisoformat(t.timestamp) > cutoff_date
        ]

        self._save_data()

    def _analyze_transaction(self, transaction: AMLTransaction) -> None:
        """Analyze transaction for suspicious patterns"""
        suspicious_indicators = []

        # Large transaction check
        if transaction.amount >= self.large_transaction_threshold:
            suspicious_indicators.append("large_transaction")

        # Unusual timing check (outside market hours)
        try:
            tx_time = datetime.fromisoformat(transaction.timestamp)
            if tx_time.hour < 9 or tx_time.hour > 15:
                suspicious_indicators.append("unusual_timing")
        except:
            pass

        # Round amount check (potential structuring)
        if transaction.amount > 0 and (transaction.amount % 100000) == 0:
            suspicious_indicators.append("round_amount")

        # High frequency check
        recent_transactions = [
            t for t in self.transactions
            if t.client_id == transaction.client_id and
            datetime.fromisoformat(t.timestamp) > datetime.now() - timedelta(hours=1)
        ]
        if len(recent_transactions) > 10:
            suspicious_indicators.append("high_frequency")

        # Layering pattern check (rapid movement through accounts)
        if self._check_layering_pattern(transaction):
            suspicious_indicators.append("layering_pattern")

        # Generate alert if suspicious indicators exceed threshold
        if len(suspicious_indicators) >= self.unusual_pattern_threshold:
            self._generate_aml_alert(
                client_id=transaction.client_id,
                alert_type="suspicious_activity",
                severity=self._assess_severity(suspicious_indicators),
                description=f"Suspicious transaction pattern detected: {', '.join(suspicious_indicators)}",
                amount_involved=transaction.amount,
                suspicious_patterns=suspicious_indicators
            )

    def _check_layering_pattern(self, transaction: AMLTransaction) -> bool:
        """Check for layering patterns (breaking up large amounts)"""
        # Look for multiple transactions of similar amounts within short time
        recent_same_amount = [
            t for t in self.transactions
            if (t.client_id == transaction.client_id and
                t.transaction_type == transaction.transaction_type and
                abs(t.amount - transaction.amount) / transaction.amount < 0.1 and  # Within 10%
                datetime.fromisoformat(t.timestamp) > datetime.now() - timedelta(days=7))
        ]

        return len(recent_same_amount) >= 3

    def _assess_severity(self, suspicious_indicators: List[str]) -> AMLAlertLevel:
        """Assess alert severity based on suspicious indicators"""
        high_risk_indicators = ["layering_pattern", "large_transaction", "high_frequency"]

        high_risk_count = sum(1 for indicator in suspicious_indicators if indicator in high_risk_indicators)

        if high_risk_count >= 2:
            return AMLAlertLevel.CRITICAL
        elif high_risk_count >= 1:
            return AMLAlertLevel.HIGH
        elif len(suspicious_indicators) >= 3:
            return AMLAlertLevel.MEDIUM
        else:
            return AMLAlertLevel.LOW

    def _generate_aml_alert(self, client_id: str, alert_type: str, severity: AMLAlertLevel,
                           description: str, amount_involved: float, suspicious_patterns: List[str]) -> None:
        """Generate AML alert"""
        alert = AMLAlert(
            alert_id=f"AML_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{client_id}",
            client_id=client_id,
            alert_type=alert_type,
            severity=severity,
            description=description,
            timestamp=datetime.now().isoformat(),
            amount_involved=amount_involved,
            suspicious_patterns=suspicious_patterns
        )

        self.alerts.append(alert)

        # Log alert based on severity
        log_message = f"🚨 AML ALERT [{severity.value.upper()}] - Client {client_id}: {description}"
        if severity == AMLAlertLevel.CRITICAL:
            logger.critical(log_message)
        elif severity == AMLAlertLevel.HIGH:
            logger.error(log_message)
        else:
            logger.warning(log_message)

    def get_client_risk_score(self, client_id: str) -> float:
        """
        Calculate AML risk score for client (0-100)

        Args:
            client_id: Client identifier

        Returns:
            Risk score (0 = low risk, 100 = high risk)
        """
        risk_score = 0.0

        # Analyze recent transactions
        client_transactions = [
            t for t in self.transactions
            if t.client_id == client_id
        ]

        if not client_transactions:
            return 0.0

        # Volume analysis
        total_volume = sum(abs(t.amount) for t in client_transactions)
        if total_volume > self.suspicious_volume_threshold:
            risk_score += 30

        # Transaction frequency
        recent_count = len([
            t for t in client_transactions
            if datetime.fromisoformat(t.timestamp) > datetime.now() - timedelta(days=7)
        ])
        if recent_count > 50:
            risk_score += 25

        # Pattern analysis
        suspicious_count = len([
            t for t in client_transactions
            if len(self._analyze_transaction_patterns(t)) > 0
        ])
        risk_score += min(suspicious_count * 5, 30)

        # Alert history
        client_alerts = [a for a in self.alerts if a.client_id == client_id]
        risk_score += min(len(client_alerts) * 10, 15)

        return min(risk_score, 100.0)

    def _analyze_transaction_patterns(self, transaction: AMLTransaction) -> List[str]:
        """Analyze individual transaction for suspicious patterns"""
        patterns = []

        # Large cash transactions
        if transaction.transaction_type in ['deposit', 'withdrawal'] and transaction.amount >= 1000000:
            patterns.append("large_cash_transaction")

        # Round amounts (structuring)
        if transaction.amount > 0 and (transaction.amount % 100000) == 0:
            patterns.append("structuring_suspicion")

        return patterns

    def generate_suspicious_activity_report(self) -> Dict:
        """
        Generate SAR (Suspicious Activity Report) for regulatory submission

        Returns:
            SAR data structure for SEBI submission
        """
        # Get high-risk clients
        high_risk_clients = []
        for client_id in set(t.client_id for t in self.transactions):
            risk_score = self.get_client_risk_score(client_id)
            if risk_score >= 70:  # High risk threshold
                high_risk_clients.append({
                    'client_id': client_id,
                    'risk_score': risk_score,
                    'transaction_count': len([t for t in self.transactions if t.client_id == client_id]),
                    'total_volume': sum(abs(t.amount) for t in self.transactions if t.client_id == client_id)
                })

        # Get recent alerts
        recent_alerts = [
            alert for alert in self.alerts
            if datetime.fromisoformat(alert.timestamp) > datetime.now() - timedelta(days=30)
        ]

        return {
            'report_date': datetime.now().isoformat(),
            'reporting_period': '30_days',
            'high_risk_clients': high_risk_clients,
            'total_alerts': len(recent_alerts),
            'critical_alerts': len([a for a in recent_alerts if a.severity == AMLAlertLevel.CRITICAL]),
            'pending_investigations': len([a for a in self.alerts if a.status == 'investigating']),
            'summary': {
                'total_transactions_monitored': len(self.transactions),
                'unique_clients': len(set(t.client_id for t in self.transactions)),
                'large_transactions': len([t for t in self.transactions if t.amount >= self.large_transaction_threshold])
            }
        }

    def _load_data(self):
        """Load AML data from files"""
        try:
            import os
            os.makedirs(self.data_dir, exist_ok=True)

            # Load transactions
            tx_file = f"{self.data_dir}/aml_transactions.json"
            if os.path.exists(tx_file):
                with open(tx_file, 'r') as f:
                    tx_data = json.load(f)
                self.transactions = [AMLTransaction(**tx) for tx in tx_data]

            # Load alerts
            alert_file = f"{self.data_dir}/aml_alerts.json"
            if os.path.exists(alert_file):
                with open(alert_file, 'r') as f:
                    alert_data = json.load(f)
                self.alerts = [AMLAlert(**alert) for alert in alert_data]

            logger.info(f"✅ Loaded AML data: {len(self.transactions)} transactions, {len(self.alerts)} alerts")

        except Exception as e:
            logger.error(f"Error loading AML data: {e}")

    def _save_data(self):
        """Save AML data to files"""
        try:
            import os
            os.makedirs(self.data_dir, exist_ok=True)

            # Save transactions
            tx_file = f"{self.data_dir}/aml_transactions.json"
            with open(tx_file, 'w') as f:
                json.dump([tx.__dict__ for tx in self.transactions], f, indent=2)

            # Save alerts
            alert_file = f"{self.data_dir}/aml_alerts.json"
            with open(alert_file, 'w') as f:
                json.dump([alert.__dict__ for alert in self.alerts], f, indent=2)

        except Exception as e:
            logger.error(f"Error saving AML data: {e}")