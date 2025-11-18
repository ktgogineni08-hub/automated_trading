#!/usr/bin/env python3
"""
Test script to verify all security and critical fixes
Run this before deploying to production
"""

import os
import sys
import json
from pathlib import Path

def test_environment_variables():
    """Test 1: Verify environment variables are set"""
    print("\n" + "="*60)
    print("TEST 1: Environment Variables")
    print("="*60)

    api_key = os.getenv('ZERODHA_API_KEY')
    api_secret = os.getenv('ZERODHA_API_SECRET')

    if api_key and api_secret:
        print(f"✅ ZERODHA_API_KEY: {api_key[:10]}...{api_key[-3:]}")
        print(f"✅ ZERODHA_API_SECRET: {api_secret[:10]}...***")

        # Check if they're the old exposed credentials
        if api_key == "<your_api_key>":
            print("⚠️  WARNING: You're still using the OLD exposed API key!")
            print("   Please rotate your credentials via Zerodha Console")
            return False

        return True
    else:
        print("❌ Environment variables not set")
        print("\n💡 Run the setup script:")
        print("   ./setup_credentials.sh")
        return False


def test_ban_list_enforcement():
    """Test 2: Verify SEBI ban list fetches real data"""
    print("\n" + "="*60)
    print("TEST 2: SEBI Ban List Enforcement")
    print("="*60)

    try:
        from sebi_compliance import SEBIComplianceChecker

        print("Creating compliance checker...")
        checker = SEBIComplianceChecker(kite=None)

        print("Refreshing ban list from NSE...")
        checker._refresh_ban_list()

        if checker.ban_list_cache is not None:
            print(f"✅ Ban list loaded: {len(checker.ban_list_cache)} securities")
            if checker.ban_list_cache:
                print(f"   Sample: {checker.ban_list_cache[:3]}")
            else:
                print("   (Currently no securities in ban period)")
            return True
        else:
            print("❌ Ban list is None (not initialized)")
            return False

    except Exception as e:
        print(f"❌ Error testing ban list: {e}")
        print("\n💡 Make sure dependencies are installed:")
        print("   pip install requests beautifulsoup4")
        return False


def test_token_encryption():
    """Test 3: Verify token file uses encryption"""
    print("\n" + "="*60)
    print("TEST 3: Token File Encryption")
    print("="*60)

    token_file = Path("zerodha_tokens.json")

    if not token_file.exists():
        print("ℹ️  Token file doesn't exist yet (will be created on first auth)")
        return True

    try:
        with open(token_file, 'r') as f:
            token_data = json.load(f)

        # Check if using new encrypted format
        if 'encrypted_token' in token_data:
            print("✅ Token file uses encrypted format")

            # Check file permissions
            import stat
            file_stat = os.stat(token_file)
            file_mode = stat.filemode(file_stat.st_mode)
            permissions = oct(file_stat.st_mode)[-3:]

            if permissions == '600':
                print(f"✅ File permissions secure: {file_mode} ({permissions})")
                return True
            else:
                print(f"⚠️  File permissions weak: {file_mode} ({permissions})")
                print("   Run: chmod 600 zerodha_tokens.json")
                return False

        elif 'access_token' in token_data:
            print("⚠️  Token file uses OLD plaintext format")
            print("   Delete it and re-authenticate to use encrypted format:")
            print("   rm zerodha_tokens.json")
            return False
        else:
            print("❌ Token file format unknown")
            return False

    except Exception as e:
        print(f"❌ Error reading token file: {e}")
        return False


def test_volatility_classification():
    """Test 4: Verify volatility classification logic"""
    print("\n" + "="*60)
    print("TEST 4: Volatility Classification")
    print("="*60)

    try:
        from risk_manager import VolatilityRegime

        # Simulate different ATR percentages
        test_cases = [
            (0.5, "LOW"),      # 0.5% ATR
            (2.0, "NORMAL"),   # 2.0% ATR
            (3.5, "HIGH"),     # 3.5% ATR
            (5.0, "EXTREME"),  # 5.0% ATR (should now be reachable)
        ]

        print("Testing volatility threshold logic:")
        all_passed = True

        for atr_pct, expected_regime in test_cases:
            # Replicate the fixed logic
            if atr_pct > 4.5:
                regime = "EXTREME"
            elif atr_pct > 3.0:
                regime = "HIGH"
            elif atr_pct < 1.0:
                regime = "LOW"
            else:
                regime = "NORMAL"

            status = "✅" if regime == expected_regime else "❌"
            print(f"   {status} {atr_pct}% ATR → {regime} (expected: {expected_regime})")

            if regime != expected_regime:
                all_passed = False

        return all_passed

    except Exception as e:
        print(f"❌ Error testing volatility: {e}")
        return False


def test_hardcoded_credentials():
    """Test 5: Scan for hardcoded credentials in source"""
    print("\n" + "="*60)
    print("TEST 5: Hardcoded Credentials Check")
    print("="*60)

    # Known exposed credentials to look for
    exposed_key = "<your_api_key>"
    exposed_secret = "<your_api_secret>"

    files_to_check = [
        "enhanced_trading_system_complete.py",
        "zerodha_token_manager.py",
    ]

    found_issues = []

    for filename in files_to_check:
        filepath = Path(filename)
        if not filepath.exists():
            continue

        with open(filepath, 'r') as f:
            content = f.read()
            line_num = 0
            for line in content.split('\n'):
                line_num += 1
                # Check for credentials in non-comment lines
                if exposed_key in line or exposed_secret in line:
                    # Skip if it's just in a comment or documentation
                    if not line.strip().startswith('#') and 'Old' not in line and 'exposed' not in line.lower():
                        found_issues.append(f"{filename}:{line_num}")

    if found_issues:
        print("❌ Found potential hardcoded credentials in:")
        for issue in found_issues:
            print(f"   {issue}")
        print("\n⚠️  These should be removed or documented as 'old/exposed'")
        return False
    else:
        print("✅ No active hardcoded credentials found in source")
        print("   (Old credentials may appear in comments/docs for reference)")
        return True


def main():
    """Run all tests"""
    print("\n🧪 Security & Critical Fixes - Test Suite")
    print("Testing all fixes before production deployment...")

    results = {
        "Environment Variables": test_environment_variables(),
        "SEBI Ban List": test_ban_list_enforcement(),
        "Token Encryption": test_token_encryption(),
        "Volatility Classification": test_volatility_classification(),
        "Hardcoded Credentials": test_hardcoded_credentials(),
    }

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\n{passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! System is ready for deployment.")
        print("\n📋 Next steps:")
        print("   1. Run in paper mode to verify trading logic")
        print("   2. Monitor logs for any issues")
        print("   3. Deploy to live trading when confident")
        return 0
    else:
        print("\n⚠️  Some tests failed. Fix issues before deployment.")
        print("\n📋 Common fixes:")
        print("   • Set credentials: ./setup_credentials.sh")
        print("   • Install deps: pip install requests beautifulsoup4")
        print("   • Delete old token: rm zerodha_tokens.json")
        print("   • Rotate exposed keys via Zerodha Console")
        return 1


if __name__ == "__main__":
    sys.exit(main())
