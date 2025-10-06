#!/usr/bin/env python3
"""
Test script for refactored trading system modules
"""

import sys
from trading_exceptions import *
from trading_config import TradingConfig
from input_validator import InputValidator


def test_exceptions():
    """Test custom exceptions"""
    print("🧪 Testing Exceptions...")

    try:
        raise TradingError("Base trading error")
    except TradingError as e:
        print(f"✅ TradingError: {e}")

    try:
        raise ValidationError("Invalid input")
    except ValidationError as e:
        print(f"✅ ValidationError: {e}")

    try:
        raise APIError("API failed", status_code=500)
    except APIError as e:
        print(f"✅ APIError: {e} (status: {e.status_code})")

    print()


def test_config():
    """Test trading configuration"""
    print("🧪 Testing Configuration...")

    # Create default config
    config = TradingConfig()
    print(f"✅ Default config created: {config}")

    # Test validation
    try:
        config.validate()
        print("✅ Configuration validation passed")
    except ConfigurationError as e:
        print(f"❌ Validation failed: {e}")

    # Test risk-reward ratio
    rr = config.get_risk_reward_ratio()
    print(f"✅ Risk-Reward Ratio: {rr:.2f}:1")

    # Test safety check
    is_safe, warnings = config.is_safe_for_live_trading()
    print(f"✅ Safe for live trading: {is_safe}")
    if warnings:
        for warning in warnings:
            print(f"   ⚠️ {warning}")

    # Test dict conversion
    config_dict = config.to_dict()
    print(f"✅ Config as dict: {len(config_dict)} keys")

    print()


def test_validators():
    """Test input validators"""
    print("🧪 Testing Input Validators...")

    # Test symbol validation
    try:
        symbol = InputValidator.validate_symbol("RELIANCE")
        print(f"✅ Valid symbol: {symbol}")
    except ValidationError as e:
        print(f"❌ Symbol validation failed: {e}")

    try:
        InputValidator.validate_symbol("")
        print("❌ Empty symbol should fail")
    except ValidationError:
        print("✅ Empty symbol correctly rejected")

    # Test positive number
    try:
        value = InputValidator.validate_positive_number(100, "Test", min_value=0, max_value=1000)
        print(f"✅ Valid number: {value}")
    except ValidationError as e:
        print(f"❌ Number validation failed: {e}")

    try:
        InputValidator.validate_positive_number(-10, "Test")
        print("❌ Negative number should fail")
    except ValidationError:
        print("✅ Negative number correctly rejected")

    # Test percentage
    try:
        pct = InputValidator.validate_percentage(10, "Risk")
        print(f"✅ Valid percentage: {pct} (10% -> {pct})")
    except ValidationError as e:
        print(f"❌ Percentage validation failed: {e}")

    try:
        InputValidator.validate_percentage(150, "Risk")
        print("❌ Invalid percentage should fail")
    except ValidationError:
        print("✅ Invalid percentage correctly rejected")

    # Test integer
    try:
        num = InputValidator.validate_integer(25, "Positions", min_value=1, max_value=50)
        print(f"✅ Valid integer: {num}")
    except ValidationError as e:
        print(f"❌ Integer validation failed: {e}")

    # Test capital amount
    try:
        capital = InputValidator.validate_capital_amount(500000)
        print(f"✅ Valid capital: ₹{capital:,.2f}")
    except ValidationError as e:
        print(f"❌ Capital validation failed: {e}")

    try:
        InputValidator.validate_capital_amount(5000, min_capital=10000)
        print("❌ Low capital should fail")
    except ValidationError:
        print("✅ Low capital correctly rejected")

    # Test sanitization
    try:
        safe = InputValidator.sanitize_user_input("Hello World")
        print(f"✅ Sanitized input: '{safe}'")
    except ValidationError as e:
        print(f"❌ Sanitization failed: {e}")

    try:
        InputValidator.sanitize_user_input("rm -rf /")
        print("❌ Dangerous input should fail")
    except ValidationError:
        print("✅ Dangerous input correctly rejected")

    # Test date validation
    try:
        date = InputValidator.validate_date_string("2024-12-25")
        print(f"✅ Valid date: {date}")
    except ValidationError as e:
        print(f"❌ Date validation failed: {e}")

    try:
        InputValidator.validate_date_string("25-12-2024")
        print("❌ Invalid date format should fail")
    except ValidationError:
        print("✅ Invalid date format correctly rejected")

    # Test URL validation
    try:
        url = InputValidator.validate_url("http://localhost:8080")
        print(f"✅ Valid URL: {url}")
    except ValidationError as e:
        print(f"❌ URL validation failed: {e}")

    try:
        InputValidator.validate_url("not-a-url")
        print("❌ Invalid URL should fail")
    except ValidationError:
        print("✅ Invalid URL correctly rejected")

    print()


def test_config_validation():
    """Test configuration validation edge cases"""
    print("🧪 Testing Configuration Validation...")

    # Test invalid configurations
    test_cases = [
        ("Zero capital", {"initial_capital": 0}),
        ("Low capital", {"initial_capital": 50000}),
        ("Too many positions", {"max_positions": 100}),
        ("High max position", {"max_position_size": 0.50}),
        ("High risk", {"risk_per_trade_pct": 0.10}),
        ("Invalid stop loss", {"stop_loss_pct": 0.005}),
        ("Invalid take profit", {"take_profit_pct": 0.01}),
        ("Low cooldown", {"cooldown_minutes": 2}),
    ]

    for name, override in test_cases:
        config = TradingConfig(**override)
        try:
            config.validate()
            print(f"⚠️  {name}: validation passed (should it fail?)")
        except ConfigurationError as e:
            print(f"✅ {name}: correctly rejected - {str(e)[:50]}...")

    print()


def test_improved_defaults():
    """Test that new defaults are more conservative"""
    print("🧪 Testing Improved Risk Defaults...")

    config = TradingConfig()

    checks = [
        ("Risk per trade", config.risk_per_trade_pct, 0.015, "<="),
        ("Stop loss", config.stop_loss_pct, 0.03, ">="),
        ("Take profit", config.take_profit_pct, 0.10, "<="),
        ("Max position", config.max_position_size, 0.25, "<="),
        ("Cooldown", config.cooldown_minutes, 15, ">="),
        ("Min confidence", config.min_confidence, 0.45, ">="),
        ("Cache TTL", config.cache_ttl_seconds, 60, ">="),
    ]

    all_passed = True
    for name, actual, expected, op in checks:
        if op == "<=":
            passed = actual <= expected
            symbol = "≤"
        else:
            passed = actual >= expected
            symbol = "≥"

        status = "✅" if passed else "❌"
        if name in ["Risk per trade", "Stop loss", "Take profit", "Max position", "Min confidence"]:
            print(f"{status} {name}: {actual:.1%} {symbol} {expected:.1%}")
        else:
            print(f"{status} {name}: {actual} {symbol} {expected}")

        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎉 All risk defaults are improved!")
    else:
        print("\n⚠️  Some defaults may need adjustment")

    print()


def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing Refactored Trading System Modules")
    print("=" * 60)
    print()

    try:
        test_exceptions()
        test_config()
        test_validators()
        test_config_validation()
        test_improved_defaults()

        print("=" * 60)
        print("✅ All tests completed successfully!")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
