#!/usr/bin/env python3
"""
Comprehensive tests for secure_path_handler.py module
Tests SecurePathHandler for path security validation
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.secure_path_handler import (
    PathSecurityError,
    SecurePathHandler,
    get_secure_path_handler,
    validate_path,
    get_secure_token_path,
    get_state_path
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_base_dir(tmp_path):
    """Create temporary base directory with allowed subdirectories"""
    base = tmp_path / "trading_system"
    base.mkdir()

    # Create allowed directories
    (base / "logs").mkdir()
    (base / "state").mkdir()
    (base / "data").mkdir()
    (base / "kyc_data").mkdir()

    return base


@pytest.fixture
def handler(temp_base_dir):
    """Create SecurePathHandler with temp base directory"""
    return SecurePathHandler(base_dir=temp_base_dir)


# ============================================================================
# PathSecurityError Tests
# ============================================================================

class TestPathSecurityError:
    """Test PathSecurityError exception"""

    def test_pathsecurity_error_is_exception(self):
        """Test that PathSecurityError is an Exception"""
        assert issubclass(PathSecurityError, Exception)

    def test_pathsecurity_error_message(self):
        """Test PathSecurityError with message"""
        error = PathSecurityError("Test error message")
        assert str(error) == "Test error message"


# ============================================================================
# Initialization Tests
# ============================================================================

class TestInitialization:
    """Test SecurePathHandler initialization"""

    def test_initialization_default_base_dir(self):
        """Test initialization with default base directory"""
        handler = SecurePathHandler()

        assert handler.base_dir == Path.cwd()
        assert 'logs' in handler.allowed_dirs
        assert 'state' in handler.allowed_dirs

    def test_initialization_custom_base_dir(self, temp_base_dir):
        """Test initialization with custom base directory"""
        handler = SecurePathHandler(base_dir=temp_base_dir)

        assert handler.base_dir == temp_base_dir

    def test_initialization_custom_allowed_dirs(self):
        """Test initialization with custom allowed directories"""
        custom_dirs = ['my_logs', 'my_data']
        handler = SecurePathHandler(allowed_dirs=custom_dirs)

        assert handler.allowed_dirs == custom_dirs


# ============================================================================
# Path Validation Tests
# ============================================================================

class TestPathValidation:
    """Test path validation functionality"""

    def test_validate_valid_relative_path(self, handler, temp_base_dir):
        """Test validation of valid relative path"""
        result = handler.validate_path("logs/test.log")

        assert result.is_absolute()
        assert result.parent.name == "logs"

    def test_validate_valid_absolute_path(self, handler, temp_base_dir):
        """Test validation of valid absolute path"""
        test_path = temp_base_dir / "logs" / "test.log"

        result = handler.validate_path(test_path)

        assert result.is_absolute()

    def test_validate_path_string_input(self, handler):
        """Test validation with string path input"""
        result = handler.validate_path("logs/test.log")

        assert isinstance(result, Path)

    def test_validate_path_object_input(self, handler):
        """Test validation with Path object input"""
        path_obj = Path("logs/test.log")
        result = handler.validate_path(path_obj)

        assert isinstance(result, Path)

    def test_validate_null_byte_detection(self, handler):
        """Test detection of null byte in path"""
        with pytest.raises(PathSecurityError) as exc_info:
            handler.validate_path("logs/test\x00.log")

        assert "Null byte" in str(exc_info.value)

    def test_validate_path_traversal_detection(self, handler):
        """Test detection of path traversal (..)"""
        with pytest.raises(PathSecurityError) as exc_info:
            handler.validate_path("../../../etc/passwd")

        assert "Path traversal" in str(exc_info.value)

    def test_validate_must_exist_existing(self, handler, temp_base_dir):
        """Test must_exist with existing file"""
        test_file = temp_base_dir / "logs" / "existing.log"
        test_file.touch()

        result = handler.validate_path(test_file, must_exist=True)

        assert result.exists()

    def test_validate_must_exist_nonexistent(self, handler):
        """Test must_exist with nonexistent file"""
        with pytest.raises(PathSecurityError) as exc_info:
            handler.validate_path("logs/nonexistent.log", must_exist=True)

        assert "does not exist" in str(exc_info.value)

    def test_validate_allow_create_true(self, handler, temp_base_dir):
        """Test allow_create creates parent directories"""
        # Remove logs directory to test creation
        logs_dir = temp_base_dir / "logs"
        if logs_dir.exists():
            shutil.rmtree(logs_dir)

        result = handler.validate_path("logs/test.log", allow_create=True)

        assert result.parent.exists()

    def test_validate_disallowed_directory(self, handler):
        """Test rejection of disallowed directory"""
        with pytest.raises(PathSecurityError) as exc_info:
            handler.validate_path("invalid_dir/file.txt")

        assert "not in allowed directories" in str(exc_info.value)

    def test_validate_general_exception_handling(self, handler):
        """Test handling of general exceptions during validation"""
        # Use an invalid path type to trigger exception
        with pytest.raises(PathSecurityError) as exc_info:
            handler.validate_path(123)  # Invalid type

        assert "Path validation failed" in str(exc_info.value)


# ============================================================================
# Allowed Directory Validation Tests
# ============================================================================

class TestAllowedDirectoryValidation:
    """Test _validate_within_allowed_dirs"""

    def test_validate_within_base_dir(self, handler, temp_base_dir):
        """Test path within base_dir and allowed directory"""
        path = temp_base_dir / "logs" / "test.log"

        # Should not raise exception
        handler._validate_within_allowed_dirs(path)

    def test_validate_within_home_config(self, handler):
        """Test path within ~/.config/trading-system"""
        config_path = Path.home() / ".config" / "trading-system" / "token.json"

        # Should not raise exception
        handler._validate_within_allowed_dirs(config_path)

    def test_validate_outside_allowed_dirs(self, handler):
        """Test path outside allowed directories"""
        path = Path("/etc/passwd")

        with pytest.raises(PathSecurityError) as exc_info:
            handler._validate_within_allowed_dirs(path)

        assert "outside allowed directories" in str(exc_info.value)


# ============================================================================
# Directory Creation Tests
# ============================================================================

class TestDirectoryCreation:
    """Test _create_parent_dirs"""

    def test_create_parent_dirs(self, handler, temp_base_dir):
        """Test creating parent directories"""
        new_path = temp_base_dir / "logs" / "subdir" / "test.log"

        # Remove subdir if it exists
        subdir = temp_base_dir / "logs" / "subdir"
        if subdir.exists():
            shutil.rmtree(subdir)

        handler._create_parent_dirs(new_path)

        assert new_path.parent.exists()

    def test_create_parent_dirs_permissions(self, handler, temp_base_dir):
        """Test parent directories created with secure permissions"""
        new_path = temp_base_dir / "logs" / "secure_dir" / "test.log"

        handler._create_parent_dirs(new_path)

        # Check permissions (0o700 = owner-only)
        stat_info = new_path.parent.stat()
        permissions = stat_info.st_mode & 0o777
        assert permissions == 0o700

    def test_create_parent_dirs_already_exists(self, handler, temp_base_dir):
        """Test creating parent when directory already exists"""
        existing_path = temp_base_dir / "logs" / "test.log"

        # Should not raise exception
        handler._create_parent_dirs(existing_path)


# ============================================================================
# Secure Token Path Tests
# ============================================================================

class TestSecureTokenPath:
    """Test get_secure_token_path"""

    def test_get_secure_token_path(self, handler):
        """Test getting secure token path"""
        token_path = handler.get_secure_token_path()

        assert token_path.name == "zerodha_token.json"
        assert ".config" in token_path.parts
        assert "trading-system" in token_path.parts

    def test_get_secure_token_path_creates_directory(self, handler):
        """Test that getting token path creates config directory"""
        token_path = handler.get_secure_token_path()

        assert token_path.parent.exists()


# ============================================================================
# State File Path Tests
# ============================================================================

class TestStateFilePath:
    """Test get_state_file_path"""

    def test_get_state_file_path_default(self, handler, temp_base_dir):
        """Test getting state file path with default filename"""
        state_path = handler.get_state_file_path()

        assert state_path.name == "current_state.json"
        assert state_path.parent.name == "state"

    def test_get_state_file_path_custom_filename(self, handler, temp_base_dir):
        """Test getting state file path with custom filename"""
        state_path = handler.get_state_file_path("custom_state.json")

        assert state_path.name == "custom_state.json"


# ============================================================================
# Log File Path Tests
# ============================================================================

class TestLogFilePath:
    """Test get_log_file_path"""

    def test_get_log_file_path(self, handler, temp_base_dir):
        """Test getting log file path"""
        log_path = handler.get_log_file_path("trading.log")

        assert log_path.name == "trading.log"
        assert log_path.parent.name == "logs"


# ============================================================================
# Data File Path Tests
# ============================================================================

class TestDataFilePath:
    """Test get_data_file_path"""

    def test_get_data_file_path_no_subdir(self, handler, temp_base_dir):
        """Test getting data file path without subdirectory"""
        data_path = handler.get_data_file_path("prices.csv")

        assert data_path.name == "prices.csv"
        assert data_path.parent.name == "data"

    def test_get_data_file_path_with_subdir(self, handler, temp_base_dir):
        """Test getting data file path with subdirectory"""
        data_path = handler.get_data_file_path("prices.csv", subdir="historical")

        assert data_path.name == "prices.csv"
        assert "historical" in data_path.parts


# ============================================================================
# Predictable Path Detection Tests
# ============================================================================

class TestPredictablePathDetection:
    """Test is_predictable_path static method"""

    def test_is_predictable_path_home_token(self):
        """Test detection of token file in home directory"""
        path = Path.home() / "token.json"

        assert SecurePathHandler.is_predictable_path(path) is True

    def test_is_predictable_path_tmp_directory(self):
        """Test detection of /tmp directory"""
        path = Path("/tmp/token.json")

        assert SecurePathHandler.is_predictable_path(path) is True

    def test_is_predictable_path_desktop(self):
        """Test detection of Desktop directory"""
        path = Path.home() / "Desktop" / "token.json"

        assert SecurePathHandler.is_predictable_path(path) is True

    def test_is_predictable_path_secure_config(self):
        """Test that ~/.config subdirectory is not predictable"""
        path = Path.home() / ".config" / "trading-system" / "token.json"

        assert SecurePathHandler.is_predictable_path(path) is False

    def test_is_predictable_path_direct_in_home(self):
        """Test detection of file directly in home directory"""
        path = Path.home() / "api_key.txt"

        assert SecurePathHandler.is_predictable_path(path) is True


# ============================================================================
# Symlink Validation Tests
# ============================================================================

class TestSymlinkValidation:
    """Test validate_no_symlink_in_path"""

    def test_validate_no_symlink_in_path_no_symlinks(self, handler, temp_base_dir):
        """Test validation passes when no symlinks in path"""
        path = temp_base_dir / "logs" / "test.log"

        result = handler.validate_no_symlink_in_path(path)

        assert result is True

    @pytest.mark.skipif(sys.platform == "win32", reason="Symlink tests may fail on Windows")
    def test_validate_no_symlink_in_path_with_symlink(self, handler, temp_base_dir):
        """Test validation fails when symlink in path"""
        # Create a symlink
        real_dir = temp_base_dir / "logs"
        symlink_dir = temp_base_dir / "logs_link"

        try:
            symlink_dir.symlink_to(real_dir)

            path = symlink_dir / "test.log"

            with pytest.raises(PathSecurityError) as exc_info:
                handler.validate_no_symlink_in_path(path)

            assert "Symlink detected" in str(exc_info.value)

        finally:
            # Cleanup
            if symlink_dir.exists():
                symlink_dir.unlink()


# ============================================================================
# Singleton Pattern Tests
# ============================================================================

class TestSingletonPattern:
    """Test get_secure_path_handler singleton"""

    def test_get_secure_path_handler_creates_instance(self):
        """Test that get_secure_path_handler creates instance"""
        # Reset global instance
        import core.secure_path_handler as module
        module._secure_path_handler = None

        handler = get_secure_path_handler()

        assert handler is not None
        assert isinstance(handler, SecurePathHandler)

    def test_get_secure_path_handler_returns_same_instance(self):
        """Test that subsequent calls return same instance"""
        # Reset global instance
        import core.secure_path_handler as module
        module._secure_path_handler = None

        handler1 = get_secure_path_handler()
        handler2 = get_secure_path_handler()

        assert handler1 is handler2


# ============================================================================
# Convenience Functions Tests
# ============================================================================

class TestConvenienceFunctions:
    """Test convenience functions"""

    def test_validate_path_convenience(self):
        """Test validate_path convenience function"""
        # Reset global instance
        import core.secure_path_handler as module
        module._secure_path_handler = None

        result = validate_path("logs/test.log")

        assert isinstance(result, Path)

    def test_get_secure_token_path_convenience(self):
        """Test get_secure_token_path convenience function"""
        # Reset global instance
        import core.secure_path_handler as module
        module._secure_path_handler = None

        token_path = get_secure_token_path()

        assert token_path.name == "zerodha_token.json"

    def test_get_state_path_convenience(self):
        """Test get_state_path convenience function"""
        # Reset global instance
        import core.secure_path_handler as module
        module._secure_path_handler = None

        state_path = get_state_path()

        assert state_path.name == "current_state.json"

    def test_get_state_path_custom_filename(self):
        """Test get_state_path with custom filename"""
        # Reset global instance
        import core.secure_path_handler as module
        module._secure_path_handler = None

        state_path = get_state_path("my_state.json")

        assert state_path.name == "my_state.json"


# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_validate_path_with_spaces(self, handler):
        """Test path with spaces in name"""
        result = handler.validate_path("logs/my test file.log")

        assert "my test file.log" in str(result)

    def test_validate_path_with_unicode(self, handler):
        """Test path with unicode characters"""
        result = handler.validate_path("logs/файл.log")

        assert "файл.log" in str(result)

    def test_create_parent_dirs_permission_error(self, handler, temp_base_dir):
        """Test handling of permission error during directory creation"""
        # Mock mkdir to raise PermissionError
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            mock_mkdir.side_effect = PermissionError("Permission denied")

            path = temp_base_dir / "logs" / "subdir" / "file.txt"

            with pytest.raises(PathSecurityError) as exc_info:
                handler._create_parent_dirs(path)

            assert "Cannot create directory" in str(exc_info.value)

    def test_validate_very_long_path(self, handler):
        """Test validation of very long path"""
        # Create path with many nested directories
        long_path = "logs/" + "/".join(["subdir"] * 50) + "/test.log"

        # Should handle long paths without error
        result = handler.validate_path(long_path)

        assert isinstance(result, Path)


if __name__ == "__main__":
    # Run tests with: pytest test_secure_path_handler.py -v
    pytest.main([__file__, "-v", "--tb=short"])
