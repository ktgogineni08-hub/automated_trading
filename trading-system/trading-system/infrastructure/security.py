#!/usr/bin/env python3
"""
Security Module for Trading System
Implements comprehensive security measures including:
- API key encryption and secure storage
- State file encryption
- Path traversal protection
- Secure session management
- Sensitive data protection
"""

import os
import json
import base64
import hashlib
import secrets
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import re
import threading
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SecureKeyManager:
    """Manages API key encryption and secure storage"""

    def __init__(self, master_password: str = None):
        self.master_password = master_password or self._generate_master_password()
        self.key_file = Path("keys/encrypted_keys.json")
        self.key_file.parent.mkdir(exist_ok=True)
        self._lock = threading.Lock()

        # Initialize or load encryption key
        self.fernet = self._initialize_encryption()

    def _generate_master_password(self) -> str:
        """Generate a secure master password"""
        return secrets.token_urlsafe(32)

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password using PBKDF2"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    def _initialize_encryption(self) -> Fernet:
        """Initialize encryption with key derivation"""
        salt_file = Path("keys/.salt")

        if salt_file.exists():
            salt = salt_file.read_bytes()
        else:
            salt = secrets.token_bytes(16)
            salt_file.write_bytes(salt)
            salt_file.chmod(0o600)  # Secure permissions

        key = self._derive_key(self.master_password, salt)
        return Fernet(key)

    def encrypt_api_key(self, api_key: str, service: str) -> str:
        """Encrypt and store API key securely"""
        with self._lock:
            encrypted_data = self.fernet.encrypt(json.dumps({
                'api_key': api_key,
                'service': service,
                'created_at': datetime.now().isoformat(),
                'version': '1.0'
            }).encode())

            # Load existing keys
            keys_data = {}
            if self.key_file.exists():
                try:
                    encrypted_content = self.key_file.read_bytes()
                    if encrypted_content:
                        decrypted_content = self.fernet.decrypt(encrypted_content)
                        keys_data = json.loads(decrypted_content.decode())
                except Exception as e:
                    logger.warning(f"Could not load existing keys: {e}")

            # Store encrypted key
            keys_data[service] = base64.b64encode(encrypted_data).decode()

            # Write back encrypted
            encrypted_output = self.fernet.encrypt(json.dumps(keys_data, indent=2).encode())
            self.key_file.write_bytes(encrypted_output)
            self.key_file.chmod(0o600)  # Secure permissions

            logger.info(f"✅ API key encrypted and stored for service: {service}")
            return base64.b64encode(encrypted_data).decode()

    def decrypt_api_key(self, service: str) -> Optional[str]:
        """Decrypt and retrieve API key"""
        with self._lock:
            try:
                if not self.key_file.exists():
                    return None

                encrypted_content = self.key_file.read_bytes()
                if not encrypted_content:
                    return None

                decrypted_content = self.fernet.decrypt(encrypted_content)
                keys_data = json.loads(decrypted_content.decode())

                if service not in keys_data:
                    return None

                encrypted_data = base64.b64decode(keys_data[service])
                decrypted_data = json.loads(self.fernet.decrypt(encrypted_data).decode())

                logger.info(f"✅ API key decrypted for service: {service}")
                return decrypted_data['api_key']

            except Exception as e:
                logger.error(f"Failed to decrypt API key for {service}: {e}")
                return None

class SecureStateManager:
    """Manages encrypted state file storage"""

    def __init__(self, master_password: str = None):
        self.key_manager = SecureKeyManager(master_password)
        self.state_dir = Path("state/encrypted")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def save_encrypted_state(self, state_data: Dict[str, Any], filename: str) -> bool:
        """Save state data with encryption"""
        with self._lock:
            try:
                # Add metadata
                encrypted_state = {
                    'data': state_data,
                    'created_at': datetime.now().isoformat(),
                    'version': '1.0',
                    'checksum': self._calculate_checksum(state_data)
                }

                # Encrypt the state
                json_data = json.dumps(encrypted_state, indent=2)
                encrypted_data = self.key_manager.fernet.encrypt(json_data.encode())

                # Write to file with secure permissions
                state_file = self.state_dir / filename
                state_file.write_bytes(encrypted_data)
                state_file.chmod(0o600)

                logger.info(f"✅ State encrypted and saved: {filename}")
                return True

            except Exception as e:
                logger.error(f"Failed to save encrypted state {filename}: {e}")
                return False

    def load_encrypted_state(self, filename: str) -> Optional[Dict[str, Any]]:
        """Load and decrypt state data"""
        with self._lock:
            try:
                state_file = self.state_dir / filename
                if not state_file.exists():
                    return None

                encrypted_data = state_file.read_bytes()
                decrypted_data = self.key_manager.fernet.decrypt(encrypted_data)
                encrypted_state = json.loads(decrypted_data.decode())

                # Verify checksum
                state_data = encrypted_state['data']
                stored_checksum = encrypted_state['checksum']
                current_checksum = self._calculate_checksum(state_data)

                if stored_checksum != current_checksum:
                    logger.error(f"Checksum mismatch for {filename} - data may be corrupted")
                    return None

                logger.info(f"✅ State decrypted and loaded: {filename}")
                return state_data

            except Exception as e:
                logger.error(f"Failed to load encrypted state {filename}: {e}")
                return None

    def _calculate_checksum(self, data: Dict[str, Any]) -> str:
        """Calculate checksum for data integrity"""
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()

class PathTraversalProtector:
    """Protects against path traversal attacks"""

    def __init__(self, base_directory: Path):
        self.base_directory = base_directory.resolve()
        self._lock = threading.Lock()

    def validate_path(self, path: str) -> Path:
        """Validate and resolve path safely"""
        with self._lock:
            try:
                # Convert to Path and resolve
                requested_path = Path(path).resolve()

                # Check for path traversal attempts
                if '..' in path:
                    raise ValueError(f"Path traversal attempt detected: {path}")

                # Ensure path is within base directory
                try:
                    requested_path.relative_to(self.base_directory)
                except ValueError:
                    raise ValueError(f"Path outside base directory: {path}")

                return requested_path

            except Exception as e:
                logger.error(f"Path validation failed for {path}: {e}")
                raise

    def safe_read_file(self, path: str) -> Optional[str]:
        """Safely read file with path validation"""
        try:
            validated_path = self.validate_path(path)
            if not validated_path.exists() or not validated_path.is_file():
                return None

            return validated_path.read_text(encoding='utf-8')

        except Exception as e:
            logger.error(f"Failed to read file {path}: {e}")
            return None

    def safe_write_file(self, path: str, content: str) -> bool:
        """Safely write file with path validation"""
        try:
            validated_path = self.validate_path(path)

            # Ensure parent directory exists
            validated_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file with secure permissions
            validated_path.write_text(content, encoding='utf-8')
            validated_path.chmod(0o644)  # Owner read/write, others read-only

            logger.info(f"✅ File written safely: {path}")
            return True

        except Exception as e:
            logger.error(f"Failed to write file {path}: {e}")
            return False

class SensitiveDataProtector:
    """Protects sensitive data in logs and outputs"""

    def __init__(self):
        self.sensitive_patterns = [
            r'api[_-]?key["\']?\s*[:=]\s*["\']?([a-zA-Z0-9]{10,})["\']?',
            r'api[_-]?secret["\']?\s*[:=]\s*["\']?([a-zA-Z0-9]{10,})["\']?',
            r'password["\']?\s*[:=]\s*["\']?([a-zA-Z0-9]{6,})["\']?',
            r'token["\']?\s*[:=]\s*["\']?([a-zA-Z0-9]{10,})["\']?',
            r'account[_-]?id["\']?\s*[:=]\s*["\']?([a-zA-Z0-9]{6,})["\']?',
        ]
        self._lock = threading.Lock()

    def sanitize_log_message(self, message: str) -> str:
        """Sanitize sensitive data from log messages"""
        with self._lock:
            sanitized = message

            for pattern in self.sensitive_patterns:
                def replacement(match):
                    value = match.group(1)
                    if len(value) > 8:
                        return match.group(0).replace(value, value[:4] + '*' * (len(value) - 8) + value[-4:])
                    return match.group(0)

                sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

            return sanitized

    def hash_sensitive_data(self, data: str) -> str:
        """Hash sensitive data for logging"""
        if not data:
            return ""

        # Hash with salt for security
        salt = secrets.token_bytes(16)
        hashed = hashlib.pbkdf2_hmac('sha256', data.encode(), salt, 100000)
        return base64.b64encode(salt + hashed).decode()[:16]

class SecureSessionManager:
    """Manages secure sessions with timeout and encryption"""

    def __init__(self, session_timeout: int = 3600):
        self.session_timeout = session_timeout  # seconds
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

        # Cleanup thread
        self._cleanup_thread = None
        self._start_cleanup_thread()

    def _start_cleanup_thread(self):
        """Start background cleanup thread"""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            return

        def cleanup_worker():
            while True:
                try:
                    self._cleanup_expired_sessions()
                    threading.Event().wait(300)  # Check every 5 minutes
                except Exception as e:
                    logger.error(f"Session cleanup error: {e}")

        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()

    def _cleanup_expired_sessions(self):
        """Remove expired sessions"""
        with self._lock:
            current_time = datetime.now()
            expired_sessions = []

            for session_id, session_data in self.sessions.items():
                created_at = session_data.get('created_at')
                if created_at:
                    if isinstance(created_at, str):
                        created_at = datetime.fromisoformat(created_at)

                    if (current_time - created_at).total_seconds() > self.session_timeout:
                        expired_sessions.append(session_id)

            for session_id in expired_sessions:
                del self.sessions[session_id]

            if expired_sessions:
                logger.info(f"🧹 Cleaned up {len(expired_sessions)} expired sessions")

    def create_session(self, user_data: Dict[str, Any]) -> str:
        """Create a new secure session"""
        with self._lock:
            session_id = secrets.token_urlsafe(32)

            session_data = {
                'session_id': session_id,
                'created_at': datetime.now(),
                'user_data': user_data,
                'last_accessed': datetime.now(),
                'ip_address': None,  # Could be added from request context
                'user_agent': None   # Could be added from request context
            }

            self.sessions[session_id] = session_data
            logger.info(f"✅ Created secure session: {session_id[:8]}...")
            return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data if valid"""
        with self._lock:
            if session_id not in self.sessions:
                return None

            session_data = self.sessions[session_id]

            # Check if expired
            created_at = session_data.get('created_at')
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at)

            if (datetime.now() - created_at).total_seconds() > self.session_timeout:
                del self.sessions[session_id]
                return None

            # Update last accessed time
            session_data['last_accessed'] = datetime.now()
            return session_data.get('user_data')

    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a session"""
        with self._lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                logger.info(f"✅ Session invalidated: {session_id[:8]}...")
                return True
            return False

class SecurityAuditor:
    """Audits security events and violations"""

    def __init__(self):
        self.audit_log_file = Path("logs/security_audit.log")
        self.audit_log_file.parent.mkdir(exist_ok=True)
        self._lock = threading.Lock()

    def log_security_event(self, event_type: str, details: Dict[str, Any], severity: str = "INFO"):
        """Log security events"""
        with self._lock:
            try:
                timestamp = datetime.now().isoformat()
                log_entry = {
                    'timestamp': timestamp,
                    'event_type': event_type,
                    'severity': severity,
                    'details': details,
                    'source_ip': details.get('source_ip', 'unknown'),
                    'user_id': details.get('user_id', 'unknown')
                }

                # Write to audit log
                with open(self.audit_log_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(log_entry) + '\n')

                # Also log to main logger based on severity
                message = f"🔒 SECURITY {severity}: {event_type} - {details}"
                if severity == "CRITICAL":
                    logger.critical(message)
                elif severity == "ERROR":
                    logger.error(message)
                elif severity == "WARNING":
                    logger.warning(message)
                else:
                    logger.info(message)

            except Exception as e:
                logger.error(f"Failed to log security event: {e}")

    def log_path_traversal_attempt(self, path: str, source_ip: str = "unknown"):
        """Log path traversal attempts"""
        self.log_security_event(
            "PATH_TRAVERSAL_ATTEMPT",
            {
                'path': path,
                'source_ip': source_ip,
                'user_id': 'unknown'
            },
            "WARNING"
        )

    def log_unauthorized_access(self, resource: str, user_id: str = "unknown", source_ip: str = "unknown"):
        """Log unauthorized access attempts"""
        self.log_security_event(
            "UNAUTHORIZED_ACCESS",
            {
                'resource': resource,
                'user_id': user_id,
                'source_ip': source_ip
            },
            "ERROR"
        )

# Global security instances
_key_manager = None
_state_manager = None
_path_protector = None
_data_protector = None
_session_manager = None
_security_auditor = None

def initialize_security(master_password: str = None) -> None:
    """Initialize global security components"""
    global _key_manager, _state_manager, _path_protector, _data_protector, _session_manager, _security_auditor

    if all(component is not None for component in (
        _key_manager,
        _state_manager,
        _path_protector,
        _data_protector,
        _session_manager,
        _security_auditor
    )):
        return

    _key_manager = SecureKeyManager(master_password)
    _state_manager = SecureStateManager(master_password)
    _path_protector = PathTraversalProtector(Path.cwd())
    _data_protector = SensitiveDataProtector()
    _session_manager = SecureSessionManager()
    _security_auditor = SecurityAuditor()

    logger.info("🔒 Security system initialized")

def get_key_manager() -> SecureKeyManager:
    """Get global key manager instance"""
    if _key_manager is None:
        initialize_security()
    return _key_manager

def get_state_manager() -> SecureStateManager:
    """Get global state manager instance"""
    if _state_manager is None:
        initialize_security()
    return _state_manager

def get_path_protector() -> PathTraversalProtector:
    """Get global path protector instance"""
    if _path_protector is None:
        initialize_security()
    return _path_protector

def get_data_protector() -> SensitiveDataProtector:
    """Get global data protector instance"""
    if _data_protector is None:
        initialize_security()
    return _data_protector

def get_session_manager() -> SecureSessionManager:
    """Get global session manager instance"""
    if _session_manager is None:
        initialize_security()
    return _session_manager

def get_security_auditor() -> SecurityAuditor:
    """Get global security auditor instance"""
    if _security_auditor is None:
        initialize_security()
    return _security_auditor

# Utility functions for easy access
def encrypt_api_key(api_key: str, service: str) -> str:
    """Encrypt API key for secure storage"""
    return get_key_manager().encrypt_api_key(api_key, service)

def decrypt_api_key(service: str) -> Optional[str]:
    """Decrypt API key from secure storage"""
    return get_key_manager().decrypt_api_key(service)

def save_encrypted_state(state_data: Dict[str, Any], filename: str) -> bool:
    """Save state data with encryption"""
    return get_state_manager().save_encrypted_state(state_data, filename)

def load_encrypted_state(filename: str) -> Optional[Dict[str, Any]]:
    """Load and decrypt state data"""
    return get_state_manager().load_encrypted_state(filename)

def validate_secure_path(path: str) -> Path:
    """Validate path against traversal attacks"""
    return get_path_protector().validate_path(path)

def sanitize_log_message(message: str) -> str:
    """Sanitize sensitive data from log messages"""
    return get_data_protector().sanitize_log_message(message)

def hash_sensitive_data(data: str) -> str:
    """Hash sensitive data for logging"""
    return get_data_protector().hash_sensitive_data(data)

def create_secure_session(user_data: Dict[str, Any]) -> str:
    """Create a secure session"""
    return get_session_manager().create_session(user_data)

def get_secure_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get secure session data"""
    return get_session_manager().get_session(session_id)

def invalidate_secure_session(session_id: str) -> bool:
    """Invalidate a secure session"""
    return get_session_manager().invalidate_session(session_id)

def log_security_event(event_type: str, details: Dict[str, Any], severity: str = "INFO"):
    """Log a security event"""
    get_security_auditor().log_security_event(event_type, details, severity)

def log_path_traversal_attempt(path: str, source_ip: str = "unknown"):
    """Log path traversal attempt"""
    get_security_auditor().log_path_traversal_attempt(path, source_ip)

def log_unauthorized_access(resource: str, user_id: str = "unknown", source_ip: str = "unknown"):
    """Log unauthorized access attempt"""
    get_security_auditor().log_unauthorized_access(resource, user_id, source_ip)
