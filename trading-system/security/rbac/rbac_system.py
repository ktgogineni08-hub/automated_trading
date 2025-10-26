"""
Role-Based Access Control (RBAC) System
Production-Grade Authorization Framework

Features:
- Hierarchical role management
- Fine-grained permission control
- Multi-tenancy support
- Audit logging
- Session-based access control
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
from functools import wraps

logger = logging.getLogger(__name__)


class Permission(Enum):
    """System-wide permissions"""
    # Trading permissions
    TRADE_VIEW = "trade:view"
    TRADE_CREATE = "trade:create"
    TRADE_MODIFY = "trade:modify"
    TRADE_CANCEL = "trade:cancel"
    TRADE_EXECUTE = "trade:execute"

    # Portfolio permissions
    PORTFOLIO_VIEW = "portfolio:view"
    PORTFOLIO_MANAGE = "portfolio:manage"

    # Market data permissions
    MARKET_DATA_VIEW = "market:view"
    MARKET_DATA_REALTIME = "market:realtime"
    MARKET_DATA_HISTORICAL = "market:historical"

    # Strategy permissions
    STRATEGY_VIEW = "strategy:view"
    STRATEGY_CREATE = "strategy:create"
    STRATEGY_MODIFY = "strategy:modify"
    STRATEGY_DELETE = "strategy:delete"
    STRATEGY_ACTIVATE = "strategy:activate"
    STRATEGY_DEACTIVATE = "strategy:deactivate"

    # Risk management permissions
    RISK_VIEW = "risk:view"
    RISK_CONFIGURE = "risk:configure"
    RISK_OVERRIDE = "risk:override"

    # System administration
    ADMIN_VIEW_USERS = "admin:users:view"
    ADMIN_MANAGE_USERS = "admin:users:manage"
    ADMIN_VIEW_LOGS = "admin:logs:view"
    ADMIN_SYSTEM_CONFIG = "admin:config"
    ADMIN_KILL_SWITCH = "admin:killswitch"

    # Compliance permissions
    COMPLIANCE_VIEW = "compliance:view"
    COMPLIANCE_AUDIT = "compliance:audit"
    COMPLIANCE_REPORT = "compliance:report"

    # Data access
    DATA_EXPORT = "data:export"
    DATA_DELETE = "data:delete"


class Role(Enum):
    """Predefined system roles"""
    # Admin roles
    SUPER_ADMIN = "super_admin"
    SYSTEM_ADMIN = "system_admin"

    # Trading roles
    TRADER = "trader"
    SENIOR_TRADER = "senior_trader"
    PORTFOLIO_MANAGER = "portfolio_manager"

    # Compliance roles
    COMPLIANCE_OFFICER = "compliance_officer"
    RISK_MANAGER = "risk_manager"

    # Read-only roles
    ANALYST = "analyst"
    VIEWER = "viewer"


@dataclass
class User:
    """User entity with authentication and authorization"""
    user_id: str
    username: str
    email: str
    password_hash: str
    roles: Set[Role] = field(default_factory=set)
    custom_permissions: Set[Permission] = field(default_factory=set)
    is_active: bool = True
    is_locked: bool = False
    failed_login_attempts: int = 0
    last_login: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict = field(default_factory=dict)

    def has_role(self, role: Role) -> bool:
        """Check if user has a specific role"""
        return role in self.roles

    def add_role(self, role: Role):
        """Add role to user"""
        self.roles.add(role)
        logger.info(f"Role {role.value} added to user {self.username}")

    def remove_role(self, role: Role):
        """Remove role from user"""
        self.roles.discard(role)
        logger.info(f"Role {role.value} removed from user {self.username}")


@dataclass
class Session:
    """User session with expiration"""
    session_id: str
    user_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(hours=8))
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_active: bool = True

    def is_expired(self) -> bool:
        """Check if session is expired"""
        return datetime.utcnow() > self.expires_at

    def extend(self, hours: int = 1):
        """Extend session expiration"""
        self.expires_at = datetime.utcnow() + timedelta(hours=hours)


class RBACSystem:
    """
    Role-Based Access Control System

    Features:
    - User management
    - Role management
    - Permission checking
    - Session management
    - Audit logging
    """

    # Role to permissions mapping
    ROLE_PERMISSIONS = {
        Role.SUPER_ADMIN: set(Permission),  # All permissions

        Role.SYSTEM_ADMIN: {
            Permission.ADMIN_VIEW_USERS,
            Permission.ADMIN_MANAGE_USERS,
            Permission.ADMIN_VIEW_LOGS,
            Permission.ADMIN_SYSTEM_CONFIG,
            Permission.ADMIN_KILL_SWITCH,
            Permission.COMPLIANCE_VIEW,
            Permission.COMPLIANCE_AUDIT,
            Permission.RISK_VIEW,
            Permission.RISK_CONFIGURE,
        },

        Role.PORTFOLIO_MANAGER: {
            Permission.TRADE_VIEW,
            Permission.TRADE_CREATE,
            Permission.TRADE_MODIFY,
            Permission.TRADE_CANCEL,
            Permission.TRADE_EXECUTE,
            Permission.PORTFOLIO_VIEW,
            Permission.PORTFOLIO_MANAGE,
            Permission.MARKET_DATA_VIEW,
            Permission.MARKET_DATA_REALTIME,
            Permission.MARKET_DATA_HISTORICAL,
            Permission.STRATEGY_VIEW,
            Permission.STRATEGY_CREATE,
            Permission.STRATEGY_MODIFY,
            Permission.STRATEGY_ACTIVATE,
            Permission.STRATEGY_DEACTIVATE,
            Permission.RISK_VIEW,
        },

        Role.SENIOR_TRADER: {
            Permission.TRADE_VIEW,
            Permission.TRADE_CREATE,
            Permission.TRADE_MODIFY,
            Permission.TRADE_CANCEL,
            Permission.TRADE_EXECUTE,
            Permission.PORTFOLIO_VIEW,
            Permission.MARKET_DATA_VIEW,
            Permission.MARKET_DATA_REALTIME,
            Permission.MARKET_DATA_HISTORICAL,
            Permission.STRATEGY_VIEW,
            Permission.STRATEGY_ACTIVATE,
            Permission.STRATEGY_DEACTIVATE,
            Permission.RISK_VIEW,
        },

        Role.TRADER: {
            Permission.TRADE_VIEW,
            Permission.TRADE_CREATE,
            Permission.TRADE_CANCEL,
            Permission.PORTFOLIO_VIEW,
            Permission.MARKET_DATA_VIEW,
            Permission.MARKET_DATA_REALTIME,
            Permission.STRATEGY_VIEW,
            Permission.RISK_VIEW,
        },

        Role.COMPLIANCE_OFFICER: {
            Permission.COMPLIANCE_VIEW,
            Permission.COMPLIANCE_AUDIT,
            Permission.COMPLIANCE_REPORT,
            Permission.TRADE_VIEW,
            Permission.PORTFOLIO_VIEW,
            Permission.ADMIN_VIEW_LOGS,
            Permission.DATA_EXPORT,
        },

        Role.RISK_MANAGER: {
            Permission.RISK_VIEW,
            Permission.RISK_CONFIGURE,
            Permission.TRADE_VIEW,
            Permission.PORTFOLIO_VIEW,
            Permission.COMPLIANCE_VIEW,
            Permission.ADMIN_VIEW_LOGS,
        },

        Role.ANALYST: {
            Permission.MARKET_DATA_VIEW,
            Permission.MARKET_DATA_HISTORICAL,
            Permission.TRADE_VIEW,
            Permission.PORTFOLIO_VIEW,
            Permission.STRATEGY_VIEW,
            Permission.DATA_EXPORT,
        },

        Role.VIEWER: {
            Permission.MARKET_DATA_VIEW,
            Permission.TRADE_VIEW,
            Permission.PORTFOLIO_VIEW,
        },
    }

    def __init__(self):
        self.users: Dict[str, User] = {}
        self.sessions: Dict[str, Session] = {}
        self.audit_log: List[Dict] = []

    def _hash_password(self, password: str) -> str:
        """Hash password using SHA-256"""
        salt = secrets.token_hex(16)
        hashed = hashlib.sha256(f"{password}{salt}".encode()).hexdigest()
        return f"{salt}${hashed}"

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        try:
            salt, hashed = password_hash.split('$')
            return hashlib.sha256(f"{password}{salt}".encode()).hexdigest() == hashed
        except Exception:
            return False

    def create_user(self, username: str, email: str, password: str,
                    roles: Optional[List[Role]] = None) -> User:
        """Create a new user"""
        user_id = secrets.token_urlsafe(16)
        password_hash = self._hash_password(password)

        user = User(
            user_id=user_id,
            username=username,
            email=email,
            password_hash=password_hash,
            roles=set(roles or [Role.VIEWER])
        )

        self.users[user_id] = user
        self._audit("user_created", user_id, {"username": username, "roles": [r.value for r in user.roles]})
        logger.info(f"User created: {username} (ID: {user_id})")

        return user

    def authenticate(self, username: str, password: str,
                     ip_address: Optional[str] = None,
                     user_agent: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Authenticate user and create session

        Returns:
            (success, session_id or error_message)
        """
        # Find user by username
        user = next((u for u in self.users.values() if u.username == username), None)

        if not user:
            self._audit("login_failed", None, {"username": username, "reason": "user_not_found"})
            return False, "Invalid credentials"

        # Check if account is locked
        if user.is_locked:
            self._audit("login_failed", user.user_id, {"reason": "account_locked"})
            return False, "Account is locked"

        # Check if account is active
        if not user.is_active:
            self._audit("login_failed", user.user_id, {"reason": "account_inactive"})
            return False, "Account is inactive"

        # Verify password
        if not self._verify_password(password, user.password_hash):
            user.failed_login_attempts += 1

            # Lock account after 5 failed attempts
            if user.failed_login_attempts >= 5:
                user.is_locked = True
                self._audit("account_locked", user.user_id, {"reason": "too_many_failed_attempts"})
                logger.warning(f"Account locked due to failed login attempts: {username}")

            self._audit("login_failed", user.user_id, {"reason": "invalid_password"})
            return False, "Invalid credentials"

        # Reset failed attempts on successful login
        user.failed_login_attempts = 0
        user.last_login = datetime.utcnow()

        # Create session
        session_id = secrets.token_urlsafe(32)
        session = Session(
            session_id=session_id,
            user_id=user.user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )

        self.sessions[session_id] = session
        self._audit("login_success", user.user_id, {"session_id": session_id})
        logger.info(f"User authenticated: {username}")

        return True, session_id

    def logout(self, session_id: str) -> bool:
        """Logout user and invalidate session"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.is_active = False
            self._audit("logout", session.user_id, {"session_id": session_id})
            del self.sessions[session_id]
            return True
        return False

    def get_user_from_session(self, session_id: str) -> Optional[User]:
        """Get user from session ID"""
        session = self.sessions.get(session_id)

        if not session:
            return None

        if session.is_expired() or not session.is_active:
            self.logout(session_id)
            return None

        return self.users.get(session.user_id)

    def get_user_permissions(self, user: User) -> Set[Permission]:
        """Get all permissions for a user (from roles + custom)"""
        permissions = set(user.custom_permissions)

        for role in user.roles:
            permissions.update(self.ROLE_PERMISSIONS.get(role, set()))

        return permissions

    def has_permission(self, user: User, permission: Permission) -> bool:
        """Check if user has a specific permission"""
        user_permissions = self.get_user_permissions(user)
        return permission in user_permissions

    def require_permission(self, session_id: str, permission: Permission) -> Tuple[bool, Optional[User]]:
        """
        Check if session has permission

        Returns:
            (has_permission, user)
        """
        user = self.get_user_from_session(session_id)

        if not user:
            return False, None

        has_perm = self.has_permission(user, permission)

        if not has_perm:
            self._audit("permission_denied", user.user_id, {
                "permission": permission.value,
                "session_id": session_id
            })

        return has_perm, user

    def _audit(self, event: str, user_id: Optional[str], metadata: Dict):
        """Log audit event"""
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": event,
            "user_id": user_id,
            "metadata": metadata
        }
        self.audit_log.append(audit_entry)
        logger.info(f"Audit: {event} - User: {user_id} - {metadata}")

    def grant_permission(self, user_id: str, permission: Permission):
        """Grant custom permission to user"""
        user = self.users.get(user_id)
        if user:
            user.custom_permissions.add(permission)
            self._audit("permission_granted", user_id, {"permission": permission.value})

    def revoke_permission(self, user_id: str, permission: Permission):
        """Revoke custom permission from user"""
        user = self.users.get(user_id)
        if user:
            user.custom_permissions.discard(permission)
            self._audit("permission_revoked", user_id, {"permission": permission.value})

    def get_audit_log(self, user_id: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get audit log entries"""
        logs = self.audit_log

        if user_id:
            logs = [log for log in logs if log["user_id"] == user_id]

        return logs[-limit:]


# Singleton instance
_rbac_system = None

def get_rbac_system() -> RBACSystem:
    """Get or create RBAC system singleton"""
    global _rbac_system
    if _rbac_system is None:
        _rbac_system = RBACSystem()
    return _rbac_system


# Decorator for permission checking
def require_permission(permission: Permission):
    """
    Decorator to require permission for a function

    Usage:
        @require_permission(Permission.TRADE_CREATE)
        def create_trade(session_id: str, ...):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(session_id: str, *args, **kwargs):
            rbac = get_rbac_system()
            has_perm, user = rbac.require_permission(session_id, permission)

            if not has_perm:
                raise PermissionError(f"Permission required: {permission.value}")

            # Add user to kwargs for function to use
            kwargs['_user'] = user

            return func(session_id, *args, **kwargs)

        return wrapper
    return decorator


# Example usage functions
def initialize_default_users():
    """Initialize system with default users"""
    rbac = get_rbac_system()

    # Create super admin
    admin = rbac.create_user(
        username="admin",
        email="admin@trading.example.com",
        password="ChangeMe123!",  # Should be changed immediately
        roles=[Role.SUPER_ADMIN]
    )

    # Create sample trader
    trader = rbac.create_user(
        username="trader1",
        email="trader1@trading.example.com",
        password="TraderPass123!",
        roles=[Role.TRADER]
    )

    # Create compliance officer
    compliance = rbac.create_user(
        username="compliance",
        email="compliance@trading.example.com",
        password="CompliancePass123!",
        roles=[Role.COMPLIANCE_OFFICER]
    )

    logger.info("Default users initialized")
    return {"admin": admin, "trader": trader, "compliance": compliance}


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    # Initialize RBAC system
    rbac = get_rbac_system()

    # Create users
    users = initialize_default_users()

    # Authenticate trader
    success, session_id = rbac.authenticate("trader1", "TraderPass123!")

    if success:
        print(f"Login successful! Session: {session_id}")

        # Check permissions
        user = rbac.get_user_from_session(session_id)
        print(f"\nUser: {user.username}")
        print(f"Roles: {[r.value for r in user.roles]}")
        print(f"\nPermissions:")
        for perm in rbac.get_user_permissions(user):
            print(f"  - {perm.value}")

        # Test permission check
        can_create_trade = rbac.has_permission(user, Permission.TRADE_CREATE)
        print(f"\nCan create trade: {can_create_trade}")

        can_admin = rbac.has_permission(user, Permission.ADMIN_SYSTEM_CONFIG)
        print(f"Can admin system: {can_admin}")

        # Logout
        rbac.logout(session_id)
        print("\nLogged out successfully")

    # View audit log
    print("\n=== Audit Log ===")
    for entry in rbac.get_audit_log(limit=10):
        print(f"{entry['timestamp']} - {entry['event']} - User: {entry['user_id']}")
