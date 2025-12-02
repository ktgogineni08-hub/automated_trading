#!/usr/bin/env python3
"""
Client Data Protection Module
SEBI Compliance: Client data privacy and protection requirements
"""

import logging
import json
import hashlib
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from cryptography.fernet import Fernet
import os
import re

logger = logging.getLogger('trading_system.client_data_protection')


@dataclass
class DataAccessLog:
    """Data access log entry"""
    timestamp: str
    user_id: str
    action: str  # 'read', 'write', 'delete', 'export'
    data_type: str  # 'kyc', 'transaction', 'portfolio'
    record_id: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    purpose: Optional[str] = None


class ClientDataProtection:
    """
    Client data protection and privacy management per SEBI regulations

    SEBI Requirements:
    - Data encryption at rest and in transit
    - Access logging and audit trails
    - Data retention policies
    - Client consent management
    - Right to data portability
    """

    def __init__(self, encryption_key: Optional[str] = None, data_dir: str = "protected_data"):
        self.data_dir = data_dir
        self.access_logs: list = []
        self.encryption_key = encryption_key or self._generate_encryption_key()
        self.fernet = Fernet(self.encryption_key)
        self._load_access_logs()

    def _generate_encryption_key(self) -> bytes:
        """Generate encryption key for data protection"""
        # In production, this should be from secure key management
        key = os.environ.get('DATA_ENCRYPTION_KEY')
        if key:
            return key.encode()

        # Generate new key if not exists
        return Fernet.generate_key()

    def encrypt_sensitive_data(self, data: str) -> str:
        """
        Encrypt sensitive client data

        Args:
            data: Plain text data to encrypt

        Returns:
            Encrypted data as string
        """
        encrypted_bytes = self.fernet.encrypt(data.encode())
        return encrypted_bytes.decode()

    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """
        Decrypt sensitive client data

        Args:
            encrypted_data: Encrypted data string

        Returns:
            Decrypted plain text
        """
        try:
            decrypted_bytes = self.fernet.decrypt(encrypted_data.encode())
            return decrypted_bytes.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt data: {e}")
            raise ValueError("Data decryption failed")

    def log_data_access(self, user_id: str, action: str, data_type: str,
                       record_id: str, ip_address: str = None,
                       user_agent: str = None, purpose: str = None) -> None:
        """
        Log data access for audit trail

        Args:
            user_id: User performing the action
            action: Type of action ('read', 'write', 'delete', 'export')
            data_type: Type of data ('kyc', 'transaction', 'portfolio')
            record_id: ID of the record accessed
            ip_address: Client IP address
            user_agent: Client user agent
            purpose: Purpose of access
        """
        log_entry = DataAccessLog(
            timestamp=datetime.now().isoformat(),
            user_id=user_id,
            action=action,
            data_type=data_type,
            record_id=record_id,
            ip_address=ip_address,
            user_agent=user_agent,
            purpose=purpose
        )

        self.access_logs.append(log_entry)

        # Keep only last 30 days of logs
        cutoff_date = datetime.now() - timedelta(days=30)
        self.access_logs = [
            log for log in self.access_logs
            if datetime.fromisoformat(log.timestamp) > cutoff_date
        ]

        self._save_access_logs()

        logger.info(f"📋 Data access logged: {user_id} {action} {data_type} {record_id}")

    def validate_data_access_permission(self, user_id: str, data_type: str,
                                      record_id: str, action: str) -> bool:
        """
        Validate if user has permission to access data

        Args:
            user_id: User requesting access
            data_type: Type of data
            record_id: Record identifier
            action: Requested action

        Returns:
            True if access is permitted
        """
        # In real implementation, this would check:
        # 1. User roles and permissions
        # 2. Data classification level
        # 3. Need-to-know basis
        # 4. Regulatory restrictions

        # For now, implement basic validation
        if action == 'delete' and data_type == 'kyc':
            # KYC data should not be deleted (regulatory requirement)
            logger.warning(f"❌ Delete access denied for KYC data: {record_id}")
            return False

        # Log the access attempt
        self.log_data_access(
            user_id=user_id,
            action=action,
            data_type=data_type,
            record_id=record_id,
            purpose="access_validation"
        )

        return True

    def anonymize_client_data(self, client_data: Dict, anonymization_level: str = "standard") -> Dict:
        """
        Anonymize client data for analysis while maintaining utility

        Args:
            client_data: Original client data
            anonymization_level: Level of anonymization ('minimal', 'standard', 'maximum')

        Returns:
            Anonymized data dictionary
        """
        anonymized = {}

        if anonymization_level == "minimal":
            # Only hash personally identifiable information
            anonymized = client_data.copy()
            if 'pan_number' in anonymized:
                anonymized['pan_number'] = hashlib.sha256(anonymized['pan_number'].encode()).hexdigest()[:16]
            if 'aadhaar_number' in anonymized:
                anonymized['aadhaar_number'] = hashlib.sha256(anonymized['aadhaar_number'].encode()).hexdigest()[:16]

        elif anonymization_level == "standard":
            # Remove direct identifiers
            anonymized = {
                'client_category': self._categorize_client(client_data),
                'age_group': self._get_age_group(client_data),
                'region': self._get_region_from_address(client_data),
                'risk_category': client_data.get('risk_category', 'unknown'),
                'account_type': 'individual',  # Default
                'registration_date': client_data.get('registration_date', ''),
                'last_activity': client_data.get('last_activity', '')
            }

        elif anonymization_level == "maximum":
            # Only keep statistical information
            anonymized = {
                'client_category': 'anonymous',
                'region': 'unknown',
                'risk_category': 'unknown',
                'account_type': 'individual'
            }

        return anonymized

    def _categorize_client(self, client_data: Dict) -> str:
        """Categorize client for anonymized analysis"""
        # Simple categorization logic
        age = self._calculate_age(client_data)
        if age < 30:
            return "young_investor"
        elif age > 60:
            return "senior_investor"
        else:
            return "middle_age_investor"

    def _calculate_age(self, client_data: Dict) -> int:
        """Calculate client age from date of birth"""
        try:
            dob = client_data.get('date_of_birth', '')
            if dob:
                birth_date = datetime.fromisoformat(dob)
                return (datetime.now() - birth_date).days // 365
        except:
            pass
        return 0

    def _get_age_group(self, client_data: Dict) -> str:
        """Get age group for anonymization"""
        age = self._calculate_age(client_data)
        if age < 25:
            return "18-24"
        elif age < 35:
            return "25-34"
        elif age < 45:
            return "35-44"
        elif age < 55:
            return "45-54"
        elif age < 65:
            return "55-64"
        else:
            return "65+"

    def _get_region_from_address(self, client_data: Dict) -> str:
        """Extract region from address for anonymization"""
        address = client_data.get('address', '').lower()

        # Simple region detection
        if any(city in address for city in ['mumbai', 'thane', 'navimumbai']):
            return "maharashtra_west"
        elif any(city in address for city in ['delhi', 'noida', 'gurgaon', 'ghaziabad']):
            return "delhi_ncr"
        elif any(city in address for city in ['bangalore', 'bengaluru']):
            return "karnataka"
        elif any(city in address for city in ['chennai', 'madras']):
            return "tamil_nadu"
        elif any(city in address for city in ['hyderabad']):
            return "telangana"
        elif any(city in address for city in ['pune']):
            return "maharashtra_east"
        elif any(city in address for city in ['kolkata']):
            return "west_bengal"
        elif any(city in address for city in ['ahmedabad']):
            return "gujarat"
        else:
            return "other"

    def generate_data_retention_report(self) -> Dict:
        """
        Generate data retention compliance report

        Returns:
            Report on data retention compliance
        """
        # Analyze access logs for retention compliance
        retention_analysis = {
            'total_access_logs': len(self.access_logs),
            'logs_by_data_type': {},
            'logs_by_action': {},
            'compliance_status': 'compliant',
            'recommendations': []
        }

        # Analyze by data type
        for log in self.access_logs:
            data_type = log.data_type
            action = log.action

            if data_type not in retention_analysis['logs_by_data_type']:
                retention_analysis['logs_by_data_type'][data_type] = 0
            retention_analysis['logs_by_data_type'][data_type] += 1

            if action not in retention_analysis['logs_by_action']:
                retention_analysis['logs_by_action'][action] = 0
            retention_analysis['logs_by_action'][action] += 1

        # Check retention compliance
        old_logs = [
            log for log in self.access_logs
            if datetime.fromisoformat(log.timestamp) < datetime.now() - timedelta(days=30)
        ]

        if len(old_logs) > 0:
            retention_analysis['compliance_status'] = 'non_compliant'
            retention_analysis['recommendations'].append(
                f"Remove {len(old_logs)} access logs older than 30 days"
            )

        return retention_analysis

    def _load_access_logs(self):
        """Load access logs from file"""
        try:
            import os
            os.makedirs(self.data_dir, exist_ok=True)
            filepath = f"{self.data_dir}/data_access_logs.json"

            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    log_data = json.load(f)
                self.access_logs = [DataAccessLog(**log) for log in log_data]

                logger.info(f"✅ Loaded {len(self.access_logs)} data access logs")

        except Exception as e:
            logger.error(f"Error loading access logs: {e}")

    def _save_access_logs(self):
        """Save access logs to file"""
        try:
            import os
            os.makedirs(self.data_dir, exist_ok=True)
            filepath = f"{self.data_dir}/data_access_logs.json"

            with open(filepath, 'w') as f:
                json.dump([log.__dict__ for log in self.access_logs], f, indent=2)

        except Exception as e:
            logger.error(f"Error saving access logs: {e}")