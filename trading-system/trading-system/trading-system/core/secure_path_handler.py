#!/usr/bin/env python3
"""
Secure Path Handler
Addresses Critical Issue #9: Hardcoded Security Paths

CRITICAL FIXES:
- Validates all file paths before use
- Prevents path traversal attacks
- Ensures paths are within allowed directories
- Validates path existence and permissions
- Provides secure defaults for token and state files
"""

import os
from pathlib import Path
from typing import Optional, List, Union
import logging

logger = logging.getLogger('trading_system.secure_path_handler')


class PathSecurityError(Exception):
    """Raised when path security validation fails"""
    pass


class SecurePathHandler:
    """
    Secure path handling with validation

    Features:
    - Path traversal prevention
    - Whitelist-based path validation
    - Automatic directory creation with permissions
    - Symlink resolution and validation
    - Predictable path detection
    """

    def __init__(self, base_dir: Optional[Path] = None, allowed_dirs: Optional[List[str]] = None):
        """
        Initialize secure path handler

        Args:
            base_dir: Base directory for relative paths (default: current working directory)
            allowed_dirs: List of allowed directory names (default: common trading system dirs)
        """
        self.base_dir = base_dir or Path.cwd()

        # Default allowed directories for trading system
        self.allowed_dirs = allowed_dirs or [
            'logs',
            'state',
            'data',
            'backtest_results',
            'kyc_data',
            'aml_data',
            'protected_data',
            '.config/trading-system',  # User config directory
        ]

        logger.debug(f"SecurePathHandler initialized with base_dir: {self.base_dir}")

    def validate_path(
        self,
        path: Union[str, Path],
        must_exist: bool = False,
        allow_create: bool = True,
        resolve_symlinks: bool = True
    ) -> Path:
        """
        Validate and sanitize file path

        Args:
            path: Path to validate
            must_exist: Path must already exist
            allow_create: Allow creating parent directories
            resolve_symlinks: Resolve symbolic links

        Returns:
            Validated Path object

        Raises:
            PathSecurityError: If path validation fails
        """
        try:
            # Convert to Path object
            if isinstance(path, str):
                path_obj = Path(path)
            else:
                path_obj = path

            # Check for null bytes (can bypass security checks)
            if '\x00' in str(path_obj):
                raise PathSecurityError(f"Null byte detected in path: {path}")

            # Check for path traversal attempts
            if '..' in path_obj.parts:
                raise PathSecurityError(f"Path traversal detected: {path}")

            # Resolve symlinks if requested
            if resolve_symlinks and path_obj.exists():
                path_obj = path_obj.resolve()

            # For relative paths, make absolute relative to base_dir
            if not path_obj.is_absolute():
                path_obj = (self.base_dir / path_obj).resolve()

            # Validate path is within allowed directories
            self._validate_within_allowed_dirs(path_obj)

            # Check existence requirements
            if must_exist and not path_obj.exists():
                raise PathSecurityError(f"Path does not exist: {path_obj}")

            # Create parent directories if needed and allowed
            if allow_create and not path_obj.exists():
                self._create_parent_dirs(path_obj)

            logger.debug(f"Path validated: {path_obj}")
            return path_obj

        except PathSecurityError:
            raise
        except Exception as e:
            raise PathSecurityError(f"Path validation failed for '{path}': {e}")

    def _validate_within_allowed_dirs(self, path: Path):
        """
        Validate path is within allowed directories

        Args:
            path: Path to validate

        Raises:
            PathSecurityError: If path is not in allowed directories
        """
        path_resolved = path.resolve()
        path_str = str(path_resolved)

        # Check if path is within base_dir or home config (all resolved for Mac symlink compatibility)
        base_resolved = self.base_dir.resolve()
        base_str = str(base_resolved)
        home_config = str((Path.home() / '.config' / 'trading-system').resolve())

        # Allow paths under base_dir
        if path_str.startswith(base_str):
            # Extract relative part
            try:
                rel_path = path_resolved.relative_to(base_resolved)
                first_part = rel_path.parts[0] if rel_path.parts else ''

                # Check if first directory is in allowed list
                if first_part and first_part not in self.allowed_dirs:
                    raise PathSecurityError(
                        f"Path not in allowed directories: {path}\n"
                        f"Allowed: {', '.join(self.allowed_dirs)}"
                    )
                return  # Valid
            except ValueError:
                pass  # Not relative to base_dir, check other conditions

        # Allow paths under ~/.config/trading-system
        if path_str.startswith(home_config):
            return  # Valid

        # If we get here, path is not in allowed locations
        raise PathSecurityError(
            f"Path outside allowed directories: {path}\n"
            f"Allowed base directories:\n"
            f"  - {self.base_dir}\n"
            f"  - {home_config}"
        )

    def _create_parent_dirs(self, path: Path):
        """
        Create parent directories with secure permissions

        Args:
            path: Path whose parents to create
        """
        parent = path.parent

        if not parent.exists():
            try:
                # Create with restrictive permissions (owner only)
                parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                logger.info(f"Created directory: {parent} (mode: 0o700)")
            except PermissionError as e:
                raise PathSecurityError(f"Cannot create directory {parent}: {e}")

    def get_secure_token_path(self) -> Path:
        """
        Get secure path for API token storage

        Returns:
            Path: Secure token file path in ~/.config/trading-system/

        This replaces hardcoded Path.home() usage
        """
        # Use XDG config directory standard
        config_dir = Path.home() / '.config' / 'trading-system'
        token_path = config_dir / 'zerodha_token.json'

        # Validate the path
        validated_path = self.validate_path(
            token_path,
            must_exist=False,
            allow_create=True,
            resolve_symlinks=True
        )

        # Ensure config directory has secure permissions
        if config_dir.exists():
            try:
                config_dir.chmod(0o700)  # Owner-only access
                logger.debug(f"Token directory permissions set to 0o700: {config_dir}")
            except Exception as e:
                logger.warning(f"Could not set directory permissions: {e}")

        return validated_path

    def get_state_file_path(self, filename: str = 'current_state.json') -> Path:
        """
        Get secure path for state file

        Args:
            filename: State filename

        Returns:
            Path: Validated state file path
        """
        state_dir = self.base_dir / 'state'
        state_path = state_dir / filename

        return self.validate_path(
            state_path,
            must_exist=False,
            allow_create=True,
            resolve_symlinks=True
        )

    def get_log_file_path(self, filename: str) -> Path:
        """
        Get secure path for log file

        Args:
            filename: Log filename

        Returns:
            Path: Validated log file path
        """
        log_dir = self.base_dir / 'logs'
        log_path = log_dir / filename

        return self.validate_path(
            log_path,
            must_exist=False,
            allow_create=True,
            resolve_symlinks=True
        )

    def get_data_file_path(self, filename: str, subdir: Optional[str] = None) -> Path:
        """
        Get secure path for data file

        Args:
            filename: Data filename
            subdir: Optional subdirectory within data/

        Returns:
            Path: Validated data file path
        """
        if subdir:
            data_path = self.base_dir / 'data' / subdir / filename
        else:
            data_path = self.base_dir / 'data' / filename

        return self.validate_path(
            data_path,
            must_exist=False,
            allow_create=True,
            resolve_symlinks=True
        )

    @staticmethod
    def is_predictable_path(path: Path) -> bool:
        """
        Check if path is in a predictable location (security risk)

        Predictable paths are easier for attackers to find:
        - Home directory root
        - /tmp directory
        - Current directory
        - Desktop

        Args:
            path: Path to check

        Returns:
            True if path is in predictable location
        """
        path_str = str(path.resolve())
        home_str = str(Path.home())

        # Check for predictable locations
        predictable_patterns = [
            home_str + '/token',
            home_str + '/api_key',
            home_str + '/Desktop',
            '/tmp/',
            './token',
            './api_key',
        ]

        for pattern in predictable_patterns:
            if pattern in path_str:
                return True

        # Check if directly in home directory (not in subdirectory)
        try:
            relative = path.relative_to(Path.home())
            if len(relative.parts) == 1:  # Directly in home dir
                return True
        except ValueError:
            pass

        return False

    def validate_no_symlink_in_path(self, path: Path) -> bool:
        """
        Validate that no part of path is a symlink (TOCTOU prevention)

        Args:
            path: Path to check

        Returns:
            True if no symlinks in path

        Raises:
            PathSecurityError: If symlink found in path
        """
        # Check each part of the path for symlinks
        # IMPORTANT: Don't resolve() the path first - we need to detect symlinks!
        path_to_check = path.absolute()  # Make absolute but don't follow symlinks
        current = Path(path_to_check.anchor)  # Start from root

        for part in path_to_check.parts[1:]:  # Skip root /
            current = current / part
            if current.exists() and current.is_symlink():
                raise PathSecurityError(
                    f"Symlink detected in path: {current}\n"
                    f"Full path: {path}"
                )

        return True


# Global instance
_secure_path_handler: Optional[SecurePathHandler] = None


def get_secure_path_handler(base_dir: Optional[Path] = None) -> SecurePathHandler:
    """
    Get global SecurePathHandler instance (singleton)

    Args:
        base_dir: Base directory (only used on first call)

    Returns:
        SecurePathHandler instance
    """
    global _secure_path_handler

    if _secure_path_handler is None:
        _secure_path_handler = SecurePathHandler(base_dir=base_dir)

    return _secure_path_handler


# Convenience functions
def validate_path(path: Union[str, Path], **kwargs) -> Path:
    """Convenience function for path validation"""
    handler = get_secure_path_handler()
    return handler.validate_path(path, **kwargs)


def get_secure_token_path() -> Path:
    """Convenience function for secure token path"""
    handler = get_secure_path_handler()
    return handler.get_secure_token_path()


def get_state_path(filename: str = 'current_state.json') -> Path:
    """Convenience function for state path"""
    handler = get_secure_path_handler()
    return handler.get_state_file_path(filename)


if __name__ == "__main__":
    # Test suite
    print("🧪 Testing Secure Path Handler\n")

    handler = SecurePathHandler()

    # Test 1: Valid relative path
    print("1. Valid Relative Path:")
    try:
        valid_path = handler.validate_path("logs/trading.log")
        print(f"   ✅ Validated: {valid_path}")
    except PathSecurityError as e:
        print(f"   ❌ Error: {e}")

    # Test 2: Path traversal attempt
    print("\n2. Path Traversal Detection:")
    try:
        handler.validate_path("../../../etc/passwd")
        print("   ❌ FAILED: Should have blocked path traversal")
    except PathSecurityError as e:
        print(f"   ✅ Blocked: {str(e)[:60]}...")

    # Test 3: Secure token path
    print("\n3. Secure Token Path:")
    token_path = handler.get_secure_token_path()
    print(f"   ✅ Token path: {token_path}")
    print(f"   Predictable: {handler.is_predictable_path(token_path)}")

    # Test 4: Predictable path detection
    print("\n4. Predictable Path Detection:")
    test_paths = [
        Path.home() / "token.json",
        Path.home() / ".config" / "trading-system" / "token.json",
        Path("/tmp/token.json"),
    ]
    for test_path in test_paths:
        is_pred = handler.is_predictable_path(test_path)
        status = "⚠️ Predictable" if is_pred else "✅ Secure"
        print(f"   {status}: {test_path}")

    # Test 5: Invalid directory
    print("\n5. Invalid Directory Detection:")
    try:
        handler.validate_path("invalid_dir/file.txt")
        print("   ❌ FAILED: Should have blocked invalid directory")
    except PathSecurityError as e:
        print(f"   ✅ Blocked: {str(e)[:60]}...")

    # Test 6: Null byte detection
    print("\n6. Null Byte Detection:")
    try:
        handler.validate_path("logs/file\x00.txt")
        print("   ❌ FAILED: Should have blocked null byte")
    except PathSecurityError as e:
        print(f"   ✅ Blocked: {str(e)[:60]}...")

    print("\n✅ All tests completed!")
