#!/usr/bin/env python3
"""
KYC (Know Your Customer) Management Module
SEBI Compliance: Client identification and verification requirements
"""

import logging
import hashlib
import json
from typing import Dict, Optional, Tuple, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import re

logger = logging.getLogger('trading_system.kyc_manager')


class KYCStatus(Enum):
    """KYC verification status"""
    NOT_VERIFIED = "not_verified"
    PENDING = "pending"
    VERIFIED = "verified"
    EXPIRED = "expired"
    REJECTED = "rejected"


class ClientRiskCategory(Enum):
    """Client risk categorization per SEBI guidelines"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ClientKYCData:
    """Client KYC information structure"""
    client_id: str
    name: str
    pan_number: str
    aadhaar_number: str
    date_of_birth: str
    address: str
    phone: str
    email: str

    # Verification details
    kyc_status: KYCStatus
    verification_date: Optional[str]
    verified_by: Optional[str]
    risk_category: ClientRiskCategory

    # Documents
    document_types: List[str]
    last_updated: str


class KYCManager:
    """
    Manages client KYC compliance per SEBI regulations

    SEBI Requirements:
    - Client identification and verification (SEBI Circular CIR/MIRSD/16/2011)
    - KYC documentation requirements
    - Risk categorization of clients
    - Periodic KYC updates
    """

    def __init__(self, data_dir: str = "kyc_data"):
        self.data_dir = data_dir
        self.client_data: Dict[str, ClientKYCData] = {}
        self._load_client_data()

    def register_client(self, client_data: Dict) -> Tuple[bool, str]:
        """
        Register new client with KYC verification

        Args:
            client_data: Client information dictionary

        Returns:
            (success: bool, message: str)
        """
        try:
            # Validate required fields
            required_fields = ['client_id', 'name', 'pan_number', 'date_of_birth', 'address', 'phone']
            for field in required_fields:
                if field not in client_data:
                    return False, f"Missing required field: {field}"

            client_id = client_data['client_id']

            # Check if client already exists
            if client_id in self.client_data:
                return False, f"Client {client_id} already registered"

            # Validate PAN format (SEBI requirement)
            pan_pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$'
            if not re.match(pan_pattern, client_data['pan_number']):
                return False, "Invalid PAN format"

            # Validate phone number
            phone_pattern = r'^[6-9]\d{9}$'
            if not re.match(phone_pattern, client_data['phone']):
                return False, "Invalid phone number format"

            # Create KYC data structure
            kyc_data = ClientKYCData(
                client_id=client_id,
                name=client_data['name'],
                pan_number=client_data['pan_number'],
                aadhaar_number=client_data.get('aadhaar_number', ''),
                date_of_birth=client_data['date_of_birth'],
                address=client_data['address'],
                phone=client_data['phone'],
                email=client_data.get('email', ''),
                kyc_status=KYCStatus.PENDING,
                verification_date=None,
                verified_by=None,
                risk_category=ClientRiskCategory.MEDIUM,  # Default
                document_types=client_data.get('document_types', []),
                last_updated=datetime.now().isoformat()
            )

            # Assess risk category
            kyc_data.risk_category = self._assess_risk_category(kyc_data)

            self.client_data[client_id] = kyc_data
            self._save_client_data()

            logger.info(f"✅ Client {client_id} registered for KYC verification")
            return True, f"Client registered successfully. KYC Status: {kyc_data.kyc_status.value}"

        except Exception as e:
            logger.error(f"Error registering client: {e}")
            return False, f"Registration failed: {str(e)}"

    def verify_client_kyc(self, client_id: str, verified_by: str, document_check: bool = True) -> Tuple[bool, str]:
        """
        Verify client KYC documents and information

        Args:
            client_id: Client identifier
            verified_by: Name/ID of verifying authority
            document_check: Whether documents have been verified

        Returns:
            (success: bool, message: str)
        """
        if client_id not in self.client_data:
            return False, f"Client {client_id} not found"

        client = self.client_data[client_id]

        if client.kyc_status == KYCStatus.VERIFIED:
            return False, f"Client {client_id} already verified"

        # Perform verification checks
        if document_check:
            # Validate document authenticity (mock implementation)
            if not self._validate_documents(client):
                client.kyc_status = KYCStatus.REJECTED
                self._save_client_data()
                return False, "Document verification failed"

        # Update verification status
        client.kyc_status = KYCStatus.VERIFIED
        client.verification_date = datetime.now().isoformat()
        client.verified_by = verified_by
        client.last_updated = datetime.now().isoformat()

        self._save_client_data()

        logger.info(f"✅ KYC verified for client {client_id} by {verified_by}")
        return True, "KYC verification completed successfully"

    def check_kyc_compliance(self, client_id: str) -> Tuple[bool, str]:
        """
        Check if client KYC is compliant for trading

        Args:
            client_id: Client identifier

        Returns:
            (is_compliant: bool, reason: str)
        """
        if client_id not in self.client_data:
            return False, "Client not registered"

        client = self.client_data[client_id]

        if client.kyc_status != KYCStatus.VERIFIED:
            return False, f"KYC not verified (Status: {client.kyc_status.value})"

        # Check if KYC has expired (SEBI requires periodic updates)
        if self._is_kyc_expired(client):
            client.kyc_status = KYCStatus.EXPIRED
            self._save_client_data()
            return False, "KYC verification expired"

        return True, "KYC compliant"

    def _assess_risk_category(self, client: ClientKYCData) -> ClientRiskCategory:
        """Assess client risk category based on profile"""
        # Simple risk assessment logic
        risk_score = 0

        # Age factor
        try:
            birth_date = datetime.fromisoformat(client.date_of_birth)
            age = (datetime.now() - birth_date).days / 365
            if age < 25 or age > 70:
                risk_score += 1
        except:
            pass

        # Document completeness
        if not client.aadhaar_number:
            risk_score += 1
        if not client.email:
            risk_score += 1

        # Determine risk category
        if risk_score >= 2:
            return ClientRiskCategory.HIGH
        elif risk_score >= 1:
            return ClientRiskCategory.MEDIUM
        else:
            return ClientRiskCategory.LOW

    def _validate_documents(self, client: ClientKYCData) -> bool:
        """Validate client documents (mock implementation)"""
        # In real implementation, this would:
        # 1. Verify PAN with Income Tax Department
        # 2. Verify Aadhaar with UIDAI
        # 3. Check address proof documents
        # 4. Validate bank account details

        # Mock validation - accept if all required docs present
        required_docs = ['pan_card', 'address_proof']
        return all(doc in client.document_types for doc in required_docs)

    def _is_kyc_expired(self, client: ClientKYCData) -> bool:
        """Check if KYC verification has expired"""
        if not client.verification_date:
            return True

        try:
            verification_date = datetime.fromisoformat(client.verification_date)
            # SEBI requires KYC updates every 2 years for normal clients
            expiry_date = verification_date + timedelta(days=730)  # 2 years
            return datetime.now() > expiry_date
        except:
            return True

    def _load_client_data(self):
        """Load client KYC data from file"""
        try:
            import os
            os.makedirs(self.data_dir, exist_ok=True)
            filepath = f"{self.data_dir}/kyc_clients.json"

            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    data = json.load(f)

                for client_data in data.values():
                    try:
                        if isinstance(client_data.get('kyc_status'), str):
                            client_data['kyc_status'] = KYCStatus(client_data['kyc_status'])
                        if isinstance(client_data.get('risk_category'), str):
                            client_data['risk_category'] = ClientRiskCategory(client_data['risk_category'])
                    except Exception as conv_exc:
                        logger.warning(f"Invalid KYC enum values during load: {conv_exc}")
                    client = ClientKYCData(**client_data)
                    self.client_data[client.client_id] = client

                logger.info(f"✅ Loaded KYC data for {len(self.client_data)} clients")
        except Exception as e:
            logger.error(f"Error loading KYC data: {e}")

    def _save_client_data(self):
        """Save client KYC data to file"""
        try:
            import os
            os.makedirs(self.data_dir, exist_ok=True)
            filepath = f"{self.data_dir}/kyc_clients.json"

            # Convert to serializable format
            data = {}
            for client_id, client in self.client_data.items():
                data[client_id] = {
                    'client_id': client.client_id,
                    'name': client.name,
                    'pan_number': client.pan_number,
                    'aadhaar_number': client.aadhaar_number,
                    'date_of_birth': client.date_of_birth,
                    'address': client.address,
                    'phone': client.phone,
                    'email': client.email,
                    'kyc_status': client.kyc_status.value,
                    'verification_date': client.verification_date,
                    'verified_by': client.verified_by,
                    'risk_category': client.risk_category.value,
                    'document_types': client.document_types,
                    'last_updated': client.last_updated
                }

            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Error saving KYC data: {e}")

    def get_client_risk_category(self, client_id: str) -> Optional[ClientRiskCategory]:
        """Get client risk category"""
        if client_id in self.client_data:
            return self.client_data[client_id].risk_category
        return None
