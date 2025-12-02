"""
Input validation utilities for trading system
"""
import re
from typing import Any, Union, Optional
from trading_exceptions import ValidationError


class InputValidator:
    """Comprehensive input validation for trading system"""

    @staticmethod
    def validate_symbol(symbol: str) -> str:
        """
        Validate and normalize trading symbol

        Args:
            symbol: Trading symbol to validate

        Returns:
            Normalized symbol in uppercase

        Raises:
            ValidationError: If symbol is invalid
        """
        if not symbol or not isinstance(symbol, str):
            raise ValidationError(f"Invalid symbol: {symbol}")

        symbol = symbol.strip().upper()

        if not symbol:
            raise ValidationError("Symbol cannot be empty")

        # Check length
        if len(symbol) < 2 or len(symbol) > 20:
            raise ValidationError(f"Symbol length invalid: {symbol} (must be 2-20 characters)")

        # Check for valid characters (alphanumeric, &, -, _)
        if not re.match(r'^[A-Z0-9&\-_]+$', symbol):
            raise ValidationError(f"Symbol contains invalid characters: {symbol}")

        return symbol

    @staticmethod
    def validate_positive_number(value: Any, name: str, min_value: float = 0.0,
                                 max_value: Optional[float] = None) -> float:
        """
        Validate that value is a positive number within range

        Args:
            value: Value to validate
            name: Name of the parameter (for error messages)
            min_value: Minimum allowed value (exclusive)
            max_value: Maximum allowed value (inclusive)

        Returns:
            Validated float value

        Raises:
            ValidationError: If value is invalid
        """
        try:
            num = float(value)
        except (ValueError, TypeError):
            raise ValidationError(f"{name} must be a number, got: {value}")

        if num <= min_value:
            raise ValidationError(f"{name} must be greater than {min_value}, got: {num}")

        if max_value is not None and num > max_value:
            raise ValidationError(f"{name} must be less than or equal to {max_value}, got: {num}")

        return num

    @staticmethod
    def validate_percentage(value: Any, name: str, min_pct: float = 0.0,
                           max_pct: float = 100.0) -> float:
        """
        Validate percentage value

        Args:
            value: Percentage value (0-100)
            name: Name of the parameter
            min_pct: Minimum percentage
            max_pct: Maximum percentage

        Returns:
            Validated percentage as decimal (e.g., 10 -> 0.10)

        Raises:
            ValidationError: If percentage is invalid
        """
        try:
            pct = float(value)
        except (ValueError, TypeError):
            raise ValidationError(f"{name} must be a number, got: {value}")

        if pct < min_pct or pct > max_pct:
            raise ValidationError(f"{name} must be between {min_pct}% and {max_pct}%, got: {pct}%")

        return pct / 100.0

    @staticmethod
    def validate_integer(value: Any, name: str, min_value: int = 0,
                        max_value: Optional[int] = None) -> int:
        """
        Validate integer value

        Args:
            value: Value to validate
            name: Name of the parameter
            min_value: Minimum allowed value
            max_value: Maximum allowed value

        Returns:
            Validated integer

        Raises:
            ValidationError: If value is invalid
        """
        try:
            num = int(value)
        except (ValueError, TypeError):
            raise ValidationError(f"{name} must be an integer, got: {value}")

        if num < min_value:
            raise ValidationError(f"{name} must be at least {min_value}, got: {num}")

        if max_value is not None and num > max_value:
            raise ValidationError(f"{name} must be at most {max_value}, got: {num}")

        return num

    @staticmethod
    def validate_choice(value: Any, name: str, valid_choices: list) -> Any:
        """
        Validate that value is in list of valid choices

        Args:
            value: Value to validate
            name: Name of the parameter
            valid_choices: List of valid choices

        Returns:
            Validated value

        Raises:
            ValidationError: If value not in valid choices
        """
        if value not in valid_choices:
            raise ValidationError(
                f"{name} must be one of {valid_choices}, got: {value}"
            )

        return value

    @staticmethod
    def validate_date_string(date_str: str, name: str = "Date") -> str:
        """
        Validate date string in YYYY-MM-DD format

        Args:
            date_str: Date string to validate
            name: Name of the parameter

        Returns:
            Validated date string

        Raises:
            ValidationError: If date format is invalid
        """
        if not isinstance(date_str, str):
            raise ValidationError(f"{name} must be a string, got: {type(date_str)}")

        # Check format YYYY-MM-DD
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            raise ValidationError(
                f"{name} must be in YYYY-MM-DD format, got: {date_str}"
            )

        # Validate actual date values
        try:
            year, month, day = map(int, date_str.split('-'))

            if not (1900 <= year <= 2100):
                raise ValidationError(f"Year must be between 1900 and 2100, got: {year}")

            if not (1 <= month <= 12):
                raise ValidationError(f"Month must be between 1 and 12, got: {month}")

            if not (1 <= day <= 31):
                raise ValidationError(f"Day must be between 1 and 31, got: {day}")

        except ValueError as e:
            raise ValidationError(f"Invalid date: {date_str}, {e}")

        return date_str

    @staticmethod
    def validate_confirmation(user_input: str, expected: str,
                             case_sensitive: bool = False) -> bool:
        """
        Validate user confirmation input

        Args:
            user_input: User's input
            expected: Expected confirmation string
            case_sensitive: Whether comparison is case-sensitive

        Returns:
            True if input matches expected

        Raises:
            ValidationError: If confirmation doesn't match
        """
        if not isinstance(user_input, str):
            raise ValidationError("Confirmation input must be a string")

        user_input = user_input.strip()
        expected = expected.strip()

        if not case_sensitive:
            user_input = user_input.lower()
            expected = expected.lower()

        if user_input != expected:
            raise ValidationError(f"Confirmation failed. Expected '{expected}', got '{user_input}'")

        return True

    @staticmethod
    def validate_url(url: str, name: str = "URL") -> str:
        """
        Validate URL format

        Args:
            url: URL to validate
            name: Name of the parameter

        Returns:
            Validated URL

        Raises:
            ValidationError: If URL is invalid
        """
        if not isinstance(url, str):
            raise ValidationError(f"{name} must be a string")

        url = url.strip()

        if not url:
            raise ValidationError(f"{name} cannot be empty")

        if not re.match(r'^https?://', url):
            raise ValidationError(f"{name} must start with http:// or https://")

        # Basic URL validation
        if not re.match(r'^https?://[a-zA-Z0-9\-\.]+(:\d+)?(/.*)?$', url):
            raise ValidationError(f"{name} format is invalid: {url}")

        return url

    @staticmethod
    def sanitize_user_input(user_input: str, max_length: int = 1000) -> str:
        """
        Sanitize user input by removing dangerous characters

        Args:
            user_input: Raw user input
            max_length: Maximum allowed length

        Returns:
            Sanitized string

        Raises:
            ValidationError: If input is too long or contains dangerous patterns
        """
        if not isinstance(user_input, str):
            raise ValidationError("Input must be a string")

        # Trim whitespace
        sanitized = user_input.strip()

        # Check length
        if len(sanitized) > max_length:
            raise ValidationError(f"Input too long: {len(sanitized)} chars (max {max_length})")

        # Check for command injection patterns
        dangerous_patterns = [
            r'\brm\s+-',      # rm command with flags
            r'\brm\s+',       # rm command
            r';\s*rm\s',      # rm command after semicolon
            r';\s*drop\s',    # SQL drop
            r'&&',            # Command chaining
            r'\|',            # Pipe
            r'`',             # Command substitution
            r'\$\(',          # Command substitution
            r'<script',       # XSS
            r'</script',      # XSS closing
            r'javascript:',   # JavaScript protocol
            r'on\w+\s*=',     # Event handlers (onclick, onload, etc.)
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, sanitized, re.IGNORECASE):
                raise ValidationError("Input contains potentially dangerous patterns")

        return sanitized

    @staticmethod
    def validate_capital_amount(amount: Any, min_capital: float = 10000.0,
                                max_capital: float = 100000000.0) -> float:
        """
        Validate capital amount for trading

        Args:
            amount: Capital amount to validate
            min_capital: Minimum allowed capital
            max_capital: Maximum allowed capital

        Returns:
            Validated capital amount

        Raises:
            ValidationError: If amount is invalid
        """
        try:
            capital = float(amount)
        except (ValueError, TypeError):
            raise ValidationError(f"Capital must be a number, got: {amount}")

        if capital < min_capital:
            raise ValidationError(
                f"Capital too low: ₹{capital:,.2f} (minimum: ₹{min_capital:,.2f})"
            )

        if capital > max_capital:
            raise ValidationError(
                f"Capital too high: ₹{capital:,.2f} (maximum: ₹{max_capital:,.2f})"
            )

        return capital


def get_validated_int(
    prompt: str,
    min_val: Optional[int] = None,
    max_val: Optional[int] = None,
    default: Optional[int] = None
) -> int:
    """Prompt the user until a valid integer is provided."""
    while True:
        raw_value = input(prompt)
        if not raw_value.strip() and default is not None:
            value = default
        else:
            try:
                value = int(raw_value)
            except (ValueError, TypeError):
                print(f"❌ Invalid number: {raw_value}")
                continue

        if min_val is not None and value < min_val:
            print(f"❌ Value must be at least {min_val}")
            continue

        if max_val is not None and value > max_val:
            print(f"❌ Value must be at most {max_val}")
            continue

        return value


def get_validated_float(
    prompt: str,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
    default: Optional[float] = None
) -> float:
    """Prompt the user until a valid float is provided."""
    while True:
        raw_value = input(prompt)
        if not raw_value.strip() and default is not None:
            value = default
        else:
            try:
                value = float(raw_value)
            except (ValueError, TypeError):
                print(f"❌ Invalid number: {raw_value}")
                continue

        if min_val is not None and value < min_val:
            print(f"❌ Value must be at least {min_val}")
            continue

        if max_val is not None and value > max_val:
            print(f"❌ Value must be at most {max_val}")
            continue

        return value
        try:
            value = int(raw_value)
        except (ValueError, TypeError):
            print(f"❌ Invalid number: {raw_value}")
            continue

        if min_val is not None and value < min_val:
            print(f"❌ Value must be at least {min_val}")
            continue

        if max_val is not None and value > max_val:
            print(f"❌ Value must be at most {max_val}")
            continue

        return value
