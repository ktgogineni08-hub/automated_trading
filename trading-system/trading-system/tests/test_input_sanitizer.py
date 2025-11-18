#!/usr/bin/env python3
"""
Comprehensive tests for input_sanitizer.py module
Tests InputSanitizer for security vulnerabilities and sanitization
"""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.input_sanitizer import (
    SanitizationContext,
    InputSanitizer,
    sanitize_log,
    sanitize_symbol,
    sanitize_path
)


# ============================================================================
# SanitizationContext Tests
# ============================================================================

class TestSanitizationContext:
    """Test SanitizationContext enum"""

    def test_context_values(self):
        """Test all context values exist"""
        assert SanitizationContext.LOG_MESSAGE.value == "log_message"
        assert SanitizationContext.FILE_PATH.value == "file_path"
        assert SanitizationContext.SYMBOL_NAME.value == "symbol_name"
        assert SanitizationContext.API_KEY.value == "api_key"
        assert SanitizationContext.HTML_CONTENT.value == "html_content"
        assert SanitizationContext.JSON_STRING.value == "json_string"
        assert SanitizationContext.SQL_STRING.value == "sql_string"
        assert SanitizationContext.SHELL_COMMAND.value == "shell_command"
        assert SanitizationContext.GENERAL.value == "general"


# ============================================================================
# Log Sanitization Tests
# ============================================================================

class TestLogSanitization:
    """Test sanitize_for_logging method"""

    def test_sanitize_normal_message(self):
        """Test sanitization of normal log message"""
        message = "Trading system started successfully"
        result = InputSanitizer.sanitize_for_logging(message)
        assert result == message

    def test_sanitize_newline_injection(self):
        """Test prevention of newline log injection"""
        malicious = "Normal message\nFAKE LOG: Unauthorized access granted"
        result = InputSanitizer.sanitize_for_logging(malicious)

        # Should escape newlines
        assert '\n' not in result
        assert '\\n' in result

    def test_sanitize_carriage_return(self):
        """Test removal of carriage returns"""
        message = "Message\rOverwrite"
        result = InputSanitizer.sanitize_for_logging(message)

        assert '\r' not in result
        assert '\\r' in result

    def test_sanitize_ansi_escape_codes(self):
        """Test removal of ANSI escape codes"""
        malicious = "Normal\x1b[31mRED TEXT\x1b[0m"
        result = InputSanitizer.sanitize_for_logging(malicious)

        assert '\x1b' not in result
        assert 'NormalRED TEXT' in result

    def test_sanitize_null_bytes(self):
        """Test removal of null bytes"""
        message = "Message\x00with null"
        result = InputSanitizer.sanitize_for_logging(message)

        assert '\x00' not in result

    def test_sanitize_control_characters(self):
        """Test removal of control characters (except tab)"""
        message = "Message\x01\x02\x03with controls"
        result = InputSanitizer.sanitize_for_logging(message)

        # Control characters should be removed
        assert '\x01' not in result
        assert '\x02' not in result

    def test_sanitize_tab_preserved(self):
        """Test that tab character is preserved"""
        message = "Column1\tColumn2"
        result = InputSanitizer.sanitize_for_logging(message)

        assert '\t' in result

    def test_sanitize_max_length_truncation(self):
        """Test truncation of long messages"""
        long_message = "A" * 2000
        result = InputSanitizer.sanitize_for_logging(long_message, max_length=100)

        assert len(result) <= 115  # 100 + "... (truncated)"
        assert result.endswith("... (truncated)")

    def test_sanitize_non_string_input(self):
        """Test sanitization of non-string input"""
        result = InputSanitizer.sanitize_for_logging(12345)
        assert result == "12345"

    def test_sanitize_crlf_injection(self):
        """Test prevention of CRLF injection"""
        message = "Message\r\nFAKE: Error"
        result = InputSanitizer.sanitize_for_logging(message)

        assert '\r\n' not in result
        assert '\\r\\n' in result


# ============================================================================
# Symbol Sanitization Tests
# ============================================================================

class TestSymbolSanitization:
    """Test sanitize_symbol_name method"""

    def test_sanitize_simple_symbol(self):
        """Test sanitization of simple symbol"""
        result = InputSanitizer.sanitize_symbol_name("RELIANCE")
        assert result == "RELIANCE"

    def test_sanitize_lowercase_symbol(self):
        """Test conversion to uppercase"""
        result = InputSanitizer.sanitize_symbol_name("reliance")
        assert result == "RELIANCE"

    def test_sanitize_symbol_with_spaces(self):
        """Test removal of spaces"""
        result = InputSanitizer.sanitize_symbol_name("  TCS  ")
        assert result == "TCS"

    def test_sanitize_symbol_with_special_chars_allowed(self):
        """Test symbol with special characters (allowed)"""
        result = InputSanitizer.sanitize_symbol_name("M&M", allow_special=True)
        assert result == "M&M"

    def test_sanitize_symbol_with_special_chars_not_allowed(self):
        """Test symbol with special characters (not allowed)"""
        result = InputSanitizer.sanitize_symbol_name("M&M", allow_special=False)
        assert result == "MM"  # & removed

    def test_sanitize_symbol_with_hyphen(self):
        """Test symbol with hyphen"""
        result = InputSanitizer.sanitize_symbol_name("BAJAJ-AUTO", allow_special=True)
        assert result == "BAJAJ-AUTO"

    def test_sanitize_symbol_with_invalid_chars(self):
        """Test removal of invalid characters"""
        result = InputSanitizer.sanitize_symbol_name("INVALID!@#", allow_special=False)
        assert result == "INVALID"

    def test_sanitize_symbol_too_long(self):
        """Test rejection of too long symbols"""
        long_symbol = "A" * 25

        with pytest.raises(ValueError) as exc_info:
            InputSanitizer.sanitize_symbol_name(long_symbol)

        assert "too long" in str(exc_info.value)

    def test_sanitize_empty_symbol(self):
        """Test rejection of empty symbol"""
        with pytest.raises(ValueError) as exc_info:
            InputSanitizer.sanitize_symbol_name("   ")

        assert "cannot be empty" in str(exc_info.value)

    def test_sanitize_non_string_symbol(self):
        """Test rejection of non-string symbol"""
        with pytest.raises(ValueError) as exc_info:
            InputSanitizer.sanitize_symbol_name(12345)

        assert "must be a string" in str(exc_info.value)

    def test_sanitize_symbol_with_numbers(self):
        """Test symbol with numbers"""
        result = InputSanitizer.sanitize_symbol_name("STOCK123")
        assert result == "STOCK123"


# ============================================================================
# File Path Sanitization Tests
# ============================================================================

class TestFilePathSanitization:
    """Test sanitize_file_path method"""

    def test_sanitize_valid_relative_path(self):
        """Test sanitization of valid relative path"""
        result = InputSanitizer.sanitize_file_path("logs/trading.log")
        assert result == "logs/trading.log"

    def test_sanitize_path_traversal_detected(self):
        """Test detection of path traversal"""
        with pytest.raises(ValueError) as exc_info:
            InputSanitizer.sanitize_file_path("../../../etc/passwd")

        assert "Path traversal detected" in str(exc_info.value)

    def test_sanitize_home_directory_not_allowed(self):
        """Test rejection of home directory expansion"""
        with pytest.raises(ValueError) as exc_info:
            InputSanitizer.sanitize_file_path("~/sensitive_data")

        assert "Home directory expansion not allowed" in str(exc_info.value)

    def test_sanitize_home_directory_allowed(self):
        """Test home directory expansion when allowed"""
        result = InputSanitizer.sanitize_file_path("~/data.csv", allow_absolute=True)
        assert result == "~/data.csv"

    def test_sanitize_variable_expansion(self):
        """Test detection of variable expansion"""
        with pytest.raises(ValueError) as exc_info:
            InputSanitizer.sanitize_file_path("${HOME}/data")

        assert "Variable expansion detected" in str(exc_info.value)

    def test_sanitize_command_substitution(self):
        """Test detection of command substitution"""
        with pytest.raises(ValueError) as exc_info:
            InputSanitizer.sanitize_file_path("$(whoami)/data")

        assert "Variable expansion detected" in str(exc_info.value)

    def test_sanitize_absolute_path_not_allowed(self):
        """Test rejection of absolute paths"""
        with pytest.raises(ValueError) as exc_info:
            InputSanitizer.sanitize_file_path("/etc/passwd")

        assert "Absolute paths not allowed" in str(exc_info.value)

    def test_sanitize_absolute_path_allowed(self):
        """Test absolute path when allowed"""
        result = InputSanitizer.sanitize_file_path("/var/log/trading.log", allow_absolute=True)
        assert result == "/var/log/trading.log"

    def test_sanitize_null_bytes_in_path(self):
        """Test removal of null bytes from path"""
        result = InputSanitizer.sanitize_file_path("logs/file\x00.txt")
        assert '\x00' not in result

    def test_sanitize_backslash_normalization(self):
        """Test normalization of backslashes to forward slashes"""
        result = InputSanitizer.sanitize_file_path("logs\\trading\\data.csv")
        assert result == "logs/trading/data.csv"

    def test_sanitize_multiple_slashes(self):
        """Test removal of multiple consecutive slashes"""
        result = InputSanitizer.sanitize_file_path("logs///trading///data.csv")
        assert result == "logs/trading/data.csv"

    def test_sanitize_non_string_path(self):
        """Test rejection of non-string path"""
        with pytest.raises(ValueError) as exc_info:
            InputSanitizer.sanitize_file_path(12345)

        assert "must be a string" in str(exc_info.value)


# ============================================================================
# HTML Sanitization Tests
# ============================================================================

class TestHTMLSanitization:
    """Test sanitize_html method"""

    def test_sanitize_normal_text(self):
        """Test sanitization of normal text"""
        result = InputSanitizer.sanitize_html("Hello World")
        assert result == "Hello World"

    def test_sanitize_html_tags(self):
        """Test escaping of HTML tags"""
        html = "<script>alert('XSS')</script>"
        result = InputSanitizer.sanitize_html(html)

        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_sanitize_html_quotes(self):
        """Test escaping of quotes"""
        html = '<img src="x" onerror="alert(1)">'
        result = InputSanitizer.sanitize_html(html)

        assert '"' not in result
        assert '&quot;' in result

    def test_sanitize_html_ampersand(self):
        """Test escaping of ampersand"""
        result = InputSanitizer.sanitize_html("AT&T")
        assert "&amp;" in result

    def test_sanitize_html_non_string(self):
        """Test sanitization of non-string HTML"""
        result = InputSanitizer.sanitize_html(12345)
        assert result == "12345"


# ============================================================================
# API Sanitization Tests
# ============================================================================

class TestAPISanitization:
    """Test sanitize_for_api method"""

    def test_sanitize_none_value(self):
        """Test sanitization of None value"""
        result = InputSanitizer.sanitize_for_api(None)
        assert result is None

    def test_sanitize_boolean_value(self):
        """Test sanitization of boolean value"""
        assert InputSanitizer.sanitize_for_api(True) is True
        assert InputSanitizer.sanitize_for_api(False) is False

    def test_sanitize_integer_value(self):
        """Test sanitization of integer value"""
        result = InputSanitizer.sanitize_for_api(12345)
        assert result == 12345

    def test_sanitize_float_value(self):
        """Test sanitization of float value"""
        result = InputSanitizer.sanitize_for_api(123.45)
        assert result == 123.45

    def test_sanitize_float_out_of_bounds(self):
        """Test rejection of out-of-bounds float"""
        with pytest.raises(ValueError) as exc_info:
            InputSanitizer.sanitize_for_api(1e16)

        assert "out of bounds" in str(exc_info.value)

    def test_sanitize_string_with_log_context(self):
        """Test string sanitization with LOG_MESSAGE context"""
        result = InputSanitizer.sanitize_for_api(
            "Message\nwith newline",
            context=SanitizationContext.LOG_MESSAGE
        )
        assert '\n' not in result

    def test_sanitize_string_with_file_path_context(self):
        """Test string sanitization with FILE_PATH context"""
        result = InputSanitizer.sanitize_for_api(
            "logs/trading.log",
            context=SanitizationContext.FILE_PATH
        )
        assert result == "logs/trading.log"

    def test_sanitize_string_with_symbol_context(self):
        """Test string sanitization with SYMBOL_NAME context"""
        result = InputSanitizer.sanitize_for_api(
            "reliance",
            context=SanitizationContext.SYMBOL_NAME
        )
        assert result == "RELIANCE"

    def test_sanitize_string_with_html_context(self):
        """Test string sanitization with HTML_CONTENT context"""
        result = InputSanitizer.sanitize_for_api(
            "<script>alert(1)</script>",
            context=SanitizationContext.HTML_CONTENT
        )
        assert "<script>" not in result

    def test_sanitize_list_value(self):
        """Test sanitization of list value"""
        result = InputSanitizer.sanitize_for_api([1, "test", None])
        assert isinstance(result, list)
        assert len(result) == 3

    def test_sanitize_dict_value(self):
        """Test sanitization of dict value"""
        data = {"key": "value", "number": 123}
        result = InputSanitizer.sanitize_for_api(data)

        assert isinstance(result, dict)
        assert "key" in result


# ============================================================================
# String Sanitization Tests
# ============================================================================

class TestStringSanitization:
    """Test _sanitize_string method"""

    def test_sanitize_normal_string(self):
        """Test sanitization of normal string"""
        result = InputSanitizer._sanitize_string("Normal text")
        assert result == "Normal text"

    def test_sanitize_null_bytes(self):
        """Test removal of null bytes"""
        result = InputSanitizer._sanitize_string("Text\x00with null")
        assert '\x00' not in result

    def test_sanitize_control_characters(self):
        """Test removal of control characters"""
        result = InputSanitizer._sanitize_string("Text\x01\x02\x03")
        assert '\x01' not in result

    def test_sanitize_whitespace_normalization(self):
        """Test normalization of whitespace"""
        result = InputSanitizer._sanitize_string("Too   many    spaces")
        assert result == "Too many spaces"

    def test_sanitize_string_truncation(self):
        """Test truncation of long strings"""
        long_string = "A" * 2000
        result = InputSanitizer._sanitize_string(long_string, max_length=100)
        assert len(result) == 100

    def test_sanitize_string_strip(self):
        """Test stripping of leading/trailing whitespace"""
        result = InputSanitizer._sanitize_string("  text  ")
        assert result == "text"


# ============================================================================
# API Key Validation Tests
# ============================================================================

class TestAPIKeyValidation:
    """Test validate_api_key method"""

    def test_validate_valid_api_key(self):
        """Test validation of valid API key"""
        result = InputSanitizer.validate_api_key("valid_api_key_12345")
        assert result is True

    def test_validate_api_key_too_short(self):
        """Test rejection of too short API key"""
        with pytest.raises(ValueError) as exc_info:
            InputSanitizer.validate_api_key("short")

        assert "too short" in str(exc_info.value)

    def test_validate_api_key_too_long(self):
        """Test rejection of too long API key"""
        long_key = "A" * 150

        with pytest.raises(ValueError) as exc_info:
            InputSanitizer.validate_api_key(long_key)

        assert "too long" in str(exc_info.value)

    def test_validate_api_key_invalid_characters(self):
        """Test rejection of API key with invalid characters"""
        with pytest.raises(ValueError) as exc_info:
            InputSanitizer.validate_api_key("key_with_invalid!@#$%")

        assert "invalid characters" in str(exc_info.value)

    def test_validate_api_key_placeholder(self):
        """Test rejection of placeholder API key"""
        # Use placeholders that are long enough (16+ chars) to pass length check
        placeholders = ["test_api_key_example", "your_key_here_12345", "placeholder_xxxxx"]

        for placeholder in placeholders:
            with pytest.raises(ValueError) as exc_info:
                InputSanitizer.validate_api_key(placeholder)

            assert "placeholder" in str(exc_info.value)

    def test_validate_api_key_with_hyphens(self):
        """Test validation of API key with hyphens"""
        result = InputSanitizer.validate_api_key("api-key-with-hyphens-1234")
        assert result is True

    def test_validate_api_key_with_underscores(self):
        """Test validation of API key with underscores"""
        result = InputSanitizer.validate_api_key("api_key_with_underscores_1234")
        assert result is True

    def test_validate_api_key_with_dots(self):
        """Test validation of API key with dots"""
        result = InputSanitizer.validate_api_key("api.key.with.dots.1234")
        assert result is True

    def test_validate_non_string_api_key(self):
        """Test rejection of non-string API key"""
        with pytest.raises(ValueError) as exc_info:
            InputSanitizer.validate_api_key(12345)

        assert "must be a string" in str(exc_info.value)


# ============================================================================
# Numeric String Sanitization Tests
# ============================================================================

class TestNumericStringSanitization:
    """Test sanitize_numeric_string method"""

    def test_sanitize_positive_integer(self):
        """Test sanitization of positive integer"""
        result = InputSanitizer.sanitize_numeric_string("12345")
        assert result == "12345"

    def test_sanitize_negative_integer(self):
        """Test sanitization of negative integer"""
        result = InputSanitizer.sanitize_numeric_string("-12345", allow_negative=True)
        assert result == "-12345"

    def test_sanitize_negative_not_allowed(self):
        """Test rejection of negative when not allowed"""
        with pytest.raises(ValueError) as exc_info:
            InputSanitizer.sanitize_numeric_string("-12345", allow_negative=False)

        assert "Invalid numeric format" in str(exc_info.value)

    def test_sanitize_decimal_number(self):
        """Test sanitization of decimal number"""
        result = InputSanitizer.sanitize_numeric_string("123.45", allow_decimal=True)
        assert result == "123.45"

    def test_sanitize_decimal_not_allowed(self):
        """Test rejection of decimal when not allowed"""
        with pytest.raises(ValueError) as exc_info:
            InputSanitizer.sanitize_numeric_string("123.45", allow_decimal=False)

        assert "Invalid numeric format" in str(exc_info.value)

    def test_sanitize_negative_decimal(self):
        """Test sanitization of negative decimal"""
        result = InputSanitizer.sanitize_numeric_string(
            "-123.45",
            allow_negative=True,
            allow_decimal=True
        )
        assert result == "-123.45"

    def test_sanitize_invalid_numeric_format(self):
        """Test rejection of invalid numeric format"""
        with pytest.raises(ValueError) as exc_info:
            InputSanitizer.sanitize_numeric_string("not_a_number")

        assert "Invalid numeric format" in str(exc_info.value)

    def test_sanitize_numeric_with_spaces(self):
        """Test sanitization of numeric with spaces"""
        result = InputSanitizer.sanitize_numeric_string("  123.45  ")
        assert result == "123.45"


# ============================================================================
# Injection Detection Tests
# ============================================================================

class TestInjectionDetection:
    """Test detect_injection_attempt method"""

    def test_detect_no_injection(self):
        """Test detection returns empty for clean input"""
        result = InputSanitizer.detect_injection_attempt("Normal input")
        assert result == {}

    def test_detect_log_injection(self):
        """Test detection of log injection"""
        result = InputSanitizer.detect_injection_attempt("Message\nFAKE LOG")
        assert 'log_injection' in result

    def test_detect_path_traversal(self):
        """Test detection of path traversal"""
        result = InputSanitizer.detect_injection_attempt("../../../etc/passwd")
        assert 'path_traversal' in result

    def test_detect_command_injection(self):
        """Test detection of command injection"""
        result = InputSanitizer.detect_injection_attempt("test; rm -rf /")
        assert 'command_injection' in result

    def test_detect_sql_injection(self):
        """Test detection of SQL injection"""
        result = InputSanitizer.detect_injection_attempt("' OR '1'='1")
        assert 'sql_injection' in result

    def test_detect_sql_union(self):
        """Test detection of SQL UNION injection"""
        result = InputSanitizer.detect_injection_attempt("UNION SELECT * FROM users")
        assert 'sql_injection' in result

    def test_detect_sql_drop_table(self):
        """Test detection of SQL DROP TABLE"""
        result = InputSanitizer.detect_injection_attempt("DROP TABLE users")
        assert 'sql_injection' in result

    def test_detect_multiple_injections(self):
        """Test detection of multiple injection types"""
        result = InputSanitizer.detect_injection_attempt("../etc\npasswd; rm -rf")

        # Should detect multiple types
        assert len(result) > 1

    def test_detect_specific_check_types(self):
        """Test detection with specific check types"""
        result = InputSanitizer.detect_injection_attempt(
            "test\n../etc",
            check_types=['log_injection']
        )

        assert 'log_injection' in result
        assert 'path_traversal' not in result  # Not checked


# ============================================================================
# Dictionary Sanitization Tests
# ============================================================================

class TestDictionarySanitization:
    """Test sanitize_dict_for_logging method"""

    def test_sanitize_simple_dict(self):
        """Test sanitization of simple dictionary"""
        data = {"key": "value", "number": 123}
        result = InputSanitizer.sanitize_dict_for_logging(data)

        assert result["key"] == "value"
        assert result["number"] == 123

    def test_sanitize_dict_masks_password(self):
        """Test masking of password field"""
        data = {"user": "john", "password": "secret123"}
        result = InputSanitizer.sanitize_dict_for_logging(data)

        assert result["password"] == "***MASKED***"
        assert result["user"] == "john"

    def test_sanitize_dict_masks_api_key(self):
        """Test masking of api_key field"""
        data = {"api_key": "secret_key_12345"}
        result = InputSanitizer.sanitize_dict_for_logging(data)

        assert result["api_key"] == "***MASKED***"

    def test_sanitize_dict_masks_token(self):
        """Test masking of token field"""
        data = {"access_token": "jwt_token_xyz"}
        result = InputSanitizer.sanitize_dict_for_logging(data)

        assert result["access_token"] == "***MASKED***"

    def test_sanitize_nested_dict(self):
        """Test sanitization of nested dictionary"""
        data = {
            "user": "john",
            "credentials": {
                "api_key": "secret",
                "token": "jwt_xyz"
            }
        }
        result = InputSanitizer.sanitize_dict_for_logging(data)

        assert result["credentials"]["api_key"] == "***MASKED***"
        assert result["credentials"]["token"] == "***MASKED***"

    def test_sanitize_dict_with_list(self):
        """Test sanitization of dictionary with list values"""
        data = {"items": ["item1", "item2", "item3"]}
        result = InputSanitizer.sanitize_dict_for_logging(data)

        assert len(result["items"]) == 3

    def test_sanitize_dict_long_list_truncation(self):
        """Test truncation of long lists"""
        data = {"items": [f"item{i}" for i in range(20)]}
        result = InputSanitizer.sanitize_dict_for_logging(data)

        # Should limit to 10 items + truncation message
        assert len(result["items"]) == 11
        assert "more items" in result["items"][-1]

    def test_sanitize_dict_custom_mask_keys(self):
        """Test sanitization with custom mask keys"""
        data = {"sensitive_data": "secret", "public_data": "public"}
        result = InputSanitizer.sanitize_dict_for_logging(
            data,
            mask_keys=["sensitive_data"]
        )

        assert result["sensitive_data"] == "***MASKED***"
        assert result["public_data"] == "public"

    def test_sanitize_dict_key_sanitization(self):
        """Test sanitization of dictionary keys"""
        data = {"key\nwith\nnewlines": "value"}
        result = InputSanitizer.sanitize_dict_for_logging(data)

        # Key should be sanitized
        for key in result.keys():
            assert '\n' not in key


# ============================================================================
# Convenience Functions Tests
# ============================================================================

class TestConvenienceFunctions:
    """Test convenience functions"""

    def test_sanitize_log_function(self):
        """Test sanitize_log convenience function"""
        result = sanitize_log("Message\nwith newline")
        assert '\n' not in result

    def test_sanitize_symbol_function(self):
        """Test sanitize_symbol convenience function"""
        result = sanitize_symbol("m&m")
        assert result == "M&M"

    def test_sanitize_path_function(self):
        """Test sanitize_path convenience function"""
        result = sanitize_path("logs/trading.log")
        assert result == "logs/trading.log"


# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_sanitize_empty_string(self):
        """Test sanitization of empty string"""
        result = InputSanitizer._sanitize_string("")
        assert result == ""

    def test_sanitize_unicode_characters(self):
        """Test sanitization of unicode characters"""
        result = InputSanitizer.sanitize_for_logging("文字列")
        assert "文字列" in result

    def test_sanitize_emoji_characters(self):
        """Test sanitization of emoji characters"""
        result = InputSanitizer.sanitize_for_logging("Test 🚀 emoji")
        # Emojis may be removed or preserved depending on unicode category
        assert "Test" in result

    def test_sanitize_very_long_string(self):
        """Test sanitization of very long string"""
        long_str = "A" * 10000
        result = InputSanitizer.sanitize_for_logging(long_str, max_length=100)
        assert len(result) <= 115

    def test_sanitize_mixed_injection_attempts(self):
        """Test detection of mixed injection attempts"""
        malicious = "test\n../etc/passwd; DROP TABLE users"
        detected = InputSanitizer.detect_injection_attempt(malicious)

        # Should detect multiple injection types
        assert len(detected) >= 2

    def test_sanitize_api_nested_lists(self):
        """Test sanitization of nested lists"""
        data = [[1, 2], [3, 4]]
        result = InputSanitizer.sanitize_for_api(data)

        assert result == [[1, 2], [3, 4]]

    def test_sanitize_dict_with_numeric_keys(self):
        """Test sanitization of dict with numeric keys"""
        data = {1: "value1", 2: "value2"}
        result = InputSanitizer.sanitize_dict_for_logging(data)

        # Keys should be converted to strings and sanitized
        assert isinstance(result, dict)


if __name__ == "__main__":
    # Run tests with: pytest test_input_sanitizer.py -v
    pytest.main([__file__, "-v", "--tb=short"])
