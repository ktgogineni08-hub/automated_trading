#!/usr/bin/env python3
"""
Trading System Health Check
Comprehensive system validation and diagnostics
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
import importlib.util

def check_python_version():
    """Check if Python version is compatible"""
    print("🐍 Checking Python Version...")
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        print(f"   ✅ Python {version.major}.{version.minor}.{version.micro} (Compatible)")
        return True
    else:
        print(f"   ❌ Python {version.major}.{version.minor}.{version.micro} (Requires Python 3.8+)")
        return False

def check_dependencies():
    """Check if all required dependencies are installed"""
    print("\n📦 Checking Dependencies...")

    required_packages = [
        'pandas', 'numpy', 'kiteconnect', 'pytz',
        'requests', 'pathlib', 'cryptography'
    ]

    missing_packages = []

    for package in required_packages:
        try:
            __import__(package)
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} (Missing)")
            missing_packages.append(package)

    if missing_packages:
        print(f"\n⚠️ Missing packages: {', '.join(missing_packages)}")
        print(f"💡 Install with: pip install {' '.join(missing_packages)}")
        return False

    return True

def check_files():
    """Check if all required files exist"""
    print("\n📁 Checking System Files...")

    required_files = [
        'enhanced_trading_system_complete.py',
        'zerodha_token_manager.py',
        'enhanced_dashboard_server.py',
        'requirements.txt'
    ]

    optional_files = [
        'trading_config.json',
        'instruments.csv',
        'instruments.pkl'
    ]

    missing_required = []

    for file in required_files:
        if Path(file).exists():
            print(f"   ✅ {file}")
        else:
            print(f"   ❌ {file} (Required)")
            missing_required.append(file)

    for file in optional_files:
        if Path(file).exists():
            print(f"   ✅ {file} (Optional)")
        else:
            print(f"   ⚠️ {file} (Optional - will be created)")

    token_cache = Path(os.getenv("ZERODHA_TOKEN_DIR", Path.home() / ".config" / "trading-system")) / "zerodha_token.json"
    if token_cache.exists():
        print(f"   ✅ {token_cache} (Token cache)")
    else:
        print(f"   ⚠️ {token_cache} (Token cache will be created after authentication)")

    return len(missing_required) == 0

def check_directories():
    """Check and create necessary directories"""
    print("\n📂 Checking Directories...")

    directories = ['logs', 'state', 'backtest_results', '__pycache__']

    for directory in directories:
        dir_path = Path(directory)
        if dir_path.exists():
            print(f"   ✅ {directory}/")
        else:
            try:
                dir_path.mkdir(exist_ok=True)
                print(f"   ✅ {directory}/ (Created)")
            except Exception as e:
                print(f"   ❌ {directory}/ (Error: {e})")
                return False

    return True

def check_configuration():
    """Check configuration files"""
    print("\n🔧 Checking Configuration...")

    # Check config.py
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from config import get_config
        cfg = get_config()
        print("   ✅ Configuration system loaded")

        # Check API credentials
        api_key, api_secret = cfg.get_api_credentials()
        if api_key and api_secret:
            print("   ✅ API credentials configured")
        else:
            print("   ⚠️ API credentials not configured")

        return True
    except Exception as e:
        print(f"   ❌ Configuration error: {e}")
        return False

def check_main_system():
    """Check if main trading system can be imported"""
    print("\n🎯 Checking Main Trading System...")

    try:
        sys.path.insert(0, str(Path(__file__).parent))

        # Check if enhanced_trading_system_complete can be imported
        spec = importlib.util.spec_from_file_location(
            "trading_system",
            "enhanced_trading_system_complete.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        print("   ✅ Main trading system imports successfully")

        # Check for main function
        if hasattr(module, 'main'):
            print("   ✅ Main function found")
        else:
            print("   ⚠️ Main function not found")

        return True

    except Exception as e:
        print(f"   ❌ Trading system import error: {e}")
        return False

def check_api_connectivity():
    """Check API connectivity (if tokens exist)"""
    print("\n🌐 Checking API Connectivity...")

    try:
        from config import get_config
        from zerodha_token_manager import ZerodhaTokenManager

        cfg = get_config()
        api_key, api_secret = cfg.get_api_credentials()

        if not api_key or not api_secret:
            print("   ⚠️ API credentials not configured. Skipping connectivity test.")
            return True

        token_file = cfg.get("api.zerodha.token_file")
        token_manager = ZerodhaTokenManager(api_key, api_secret, token_file=token_file)

        if token_manager.fernet is None:
            print("   ⚠️ ZERODHA_TOKEN_KEY not set. Configure it to enable secure token caching.")
            return True

        existing_token = token_manager.load_tokens()

        if existing_token:
            print(f"   ✅ Valid authentication token found at {token_manager.token_file}")

            # Quick API test
            kite = token_manager.get_authenticated_kite()
            profile = kite.profile()
            print(f"   ✅ API connectivity test passed: {profile.get('user_name', 'Unknown')}")
            return True

        print(f"   ⚠️ No valid authentication token found at {token_manager.token_file}. Run the token manager to authenticate.")
        return True  # Not a failure, just needs authentication

    except Exception as e:
        print(f"   ❌ API connectivity error: {e}")
        return False

def run_health_check():
    """Run complete health check"""
    print("🏥 TRADING SYSTEM HEALTH CHECK")
    print("="*60)
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📍 Directory: {Path.cwd()}")

    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("System Files", check_files),
        ("Directories", check_directories),
        ("Configuration", check_configuration),
        ("Main System", check_main_system),
        ("API Connectivity", check_api_connectivity)
    ]

    results = []

    for check_name, check_func in checks:
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print(f"   ❌ {check_name} check failed: {e}")
            results.append((check_name, False))

    # Summary
    print("\n📊 HEALTH CHECK SUMMARY")
    print("="*60)

    passed = 0
    total = len(results)

    for check_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:8} {check_name}")
        if result:
            passed += 1

    print("-"*60)
    print(f"📈 Overall: {passed}/{total} checks passed ({passed/total*100:.1f}%)")

    if passed == total:
        print("\n🎉 SYSTEM HEALTHY - Ready for trading!")
        return True
    elif passed >= total * 0.8:
        print("\n⚠️ SYSTEM MOSTLY HEALTHY - Minor issues detected")
        return True
    else:
        print("\n❌ SYSTEM ISSUES DETECTED - Please fix errors before trading")
        return False

def generate_diagnostics():
    """Generate detailed diagnostics report"""
    print("\n🔍 Generating Diagnostics Report...")

    diagnostics = {
        'timestamp': datetime.now().isoformat(),
        'system_info': {
            'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            'platform': sys.platform,
            'working_directory': str(Path.cwd()),
            'script_directory': str(Path(__file__).parent)
        },
        'file_status': {},
        'directory_status': {}
    }

    # File status
    files_to_check = [
        'enhanced_trading_system_complete.py',
        'zerodha_token_manager.py',
        'enhanced_dashboard_server.py',
        'config.py',
        'requirements.txt',
        'trading_config.json'
    ]

    for file in files_to_check:
        file_path = Path(file)
        diagnostics['file_status'][file] = {
            'exists': file_path.exists(),
            'size': file_path.stat().st_size if file_path.exists() else 0,
            'modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat() if file_path.exists() else None
        }

    secure_token_path = Path(os.getenv("ZERODHA_TOKEN_DIR", Path.home() / ".config" / "trading-system")) / "zerodha_token.json"
    diagnostics['file_status'][str(secure_token_path)] = {
        'exists': secure_token_path.exists(),
        'size': secure_token_path.stat().st_size if secure_token_path.exists() else 0,
        'modified': datetime.fromtimestamp(secure_token_path.stat().st_mtime).isoformat() if secure_token_path.exists() else None
    }

    # Directory status
    dirs_to_check = ['logs', 'state', 'backtest_results']
    for directory in dirs_to_check:
        dir_path = Path(directory)
        diagnostics['directory_status'][directory] = {
            'exists': dir_path.exists(),
            'file_count': len(list(dir_path.glob('*'))) if dir_path.exists() else 0
        }

    # Save diagnostics
    diagnostics_file = Path('system_diagnostics.json')
    try:
        with open(diagnostics_file, 'w') as f:
            json.dump(diagnostics, f, indent=2)
        print(f"   ✅ Diagnostics saved to {diagnostics_file}")
    except Exception as e:
        print(f"   ❌ Could not save diagnostics: {e}")

if __name__ == "__main__":
    healthy = run_health_check()
    generate_diagnostics()

    if not healthy:
        sys.exit(1)
    else:
        print("\n🚀 System ready for launch!")
