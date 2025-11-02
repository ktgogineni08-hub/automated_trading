#!/usr/bin/env python3
"""
Trading System Installer
Automated installation and setup script for the trading system
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from datetime import datetime

def print_header(title):
    """Print formatted header"""
    print(f"\n{'='*60}")
    print(f"🛠️ {title}")
    print(f"{'='*60}")

def run_command(command, description):
    """Run a command with error handling

    Args:
        command: Command as a list (e.g., ['pip', '--version']) or string (will be split)
        description: Description of the command for logging
    """
    print(f"▶️ {description}...")
    try:
        # Convert string to list if needed (safer than shell=True)
        if isinstance(command, str):
            import shlex
            command = shlex.split(command)

        result = subprocess.run(command, shell=False, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
            if result.stdout.strip():
                print(f"   Output: {result.stdout.strip()[:200]}...")
            return True
        else:
            print(f"❌ {description} failed")
            print(f"   Error: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"❌ {description} failed with exception: {e}")
        return False

def check_python_version():
    """Check Python version compatibility"""
    print_header("Python Version Check")

    version = sys.version_info
    print(f"🐍 Current Python version: {version.major}.{version.minor}.{version.micro}")

    if version.major == 3 and version.minor >= 8:
        print("✅ Python version is compatible")
        return True
    else:
        print("❌ Python 3.8+ required")
        print("💡 Please upgrade Python and try again")
        return False

def install_dependencies():
    """Install required dependencies"""
    print_header("Installing Dependencies")

    # Check if pip is available
    if not run_command("pip --version", "Checking pip availability"):
        print("❌ pip is not available")
        return False

    # Install dependencies from requirements.txt
    if Path("requirements.txt").exists():
        success = run_command("pip install -r requirements.txt", "Installing dependencies from requirements.txt")
        if not success:
            print("⚠️ Some dependencies may have failed to install")
            print("💡 Try installing them individually if needed")
    else:
        print("⚠️ requirements.txt not found, installing core dependencies...")
        core_deps = [
            "pandas>=2.0.0",
            "numpy>=1.24.0",
            "kiteconnect>=4.3.0",
            "pytz>=2023.3",
            "requests>=2.31.0",
            "cryptography>=41.0.0"
        ]

        for dep in core_deps:
            run_command(f"pip install '{dep}'", f"Installing {dep}")

    # Verify installation
    print("\n🔍 Verifying installations...")
    test_imports = [
        ("pandas", "pd"),
        ("numpy", "np"),
        ("kiteconnect", "kiteconnect"),
        ("pytz", "pytz"),
        ("requests", "requests"),
        ("cryptography", "cryptography")
    ]

    all_imported = True
    for module, alias in test_imports:
        try:
            __import__(module)
            print(f"   ✅ {module}")
        except ImportError:
            print(f"   ❌ {module} (Failed to import)")
            all_imported = False

    return all_imported

def create_directories():
    """Create necessary directories"""
    print_header("Creating Directories")

    directories = [
        "logs",
        "state",
        "backtest_results",
        "__pycache__"
    ]

    success = True
    for directory in directories:
        try:
            Path(directory).mkdir(exist_ok=True)
            print(f"✅ {directory}/")
        except Exception as e:
            print(f"❌ Failed to create {directory}/: {e}")
            success = False

    return success

def setup_configuration():
    """Setup initial configuration"""
    print_header("Configuration Setup")

    # Create config if it doesn't exist
    if not Path("config.py").exists():
        print("❌ config.py not found - this should have been created")
        return False

    try:
        # Import and test config
        sys.path.insert(0, str(Path.cwd()))
        from config import get_config

        cfg = get_config()
        print("✅ Configuration system loaded")

        # Create necessary directories
        cfg.create_directories()
        print("✅ Configuration directories created")

        return True
    except Exception as e:
        print(f"❌ Configuration setup failed: {e}")
        return False

def setup_api_credentials():
    """Guide user through API credential setup"""
    print_header("API Credentials Setup")

    print("🔐 Zerodha API credentials must be provided from your environment or a secure secrets store.")
    print("📋 Export them before launching the trading system, for example:")
    print("   export ZERODHA_API_KEY='your_api_key'")
    print("   export ZERODHA_API_SECRET='your_api_secret'")
    print("\n💡 After setting the variables:")
    print("1. Run the token manager to authenticate: python zerodha_token_manager.py")
    print("2. Follow the authentication flow to fetch an access token")
    print("3. Tokens are cached outside the repository when an encryption key is configured")

    return True

def run_health_check():
    """Run system health check"""
    print_header("System Health Check")

    if not Path("system_health_check.py").exists():
        print("❌ system_health_check.py not found")
        return False

    return run_command("python system_health_check.py", "Running comprehensive system health check")

def create_launch_scripts():
    """Create convenient launch scripts"""
    print_header("Creating Launch Scripts")

    scripts_created = []

    # Create a unified launcher
    launcher_content = '''#!/usr/bin/env python3
"""
Unified Trading System Launcher
"""
import sys
from pathlib import Path

def main():
    print("🎯 ENHANCED NIFTY 50 TRADING SYSTEM")
    print("="*50)
    print("Choose an option:")
    print("1. 🚀 Launch Full Trading System")
    print("2. 📝 Launch Paper Trading")
    print("3. 📊 Launch Dashboard")
    print("4. 🔐 Manage Authentication")
    print("5. 🏥 Run Health Check")
    print("6. ❌ Exit")

    while True:
        try:
            choice = input("\\nSelect option (1-6): ").strip()

            if choice == "1":
                import subprocess
                subprocess.run([sys.executable, "enhanced_trading_system_complete.py"])
                break
            elif choice == "2":
                subprocess.run([sys.executable, "launch_paper_trading.py"])
                break
            elif choice == "3":
                subprocess.run([sys.executable, "launch_dashboard.py"])
                break
            elif choice == "4":
                subprocess.run([sys.executable, "zerodha_token_manager.py"])
                break
            elif choice == "5":
                subprocess.run([sys.executable, "system_health_check.py"])
                break
            elif choice == "6":
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice. Please select 1-6.")
        except KeyboardInterrupt:
            print("\\n👋 Goodbye!")
            break

if __name__ == "__main__":
    main()
'''

    try:
        with open("launch.py", "w") as f:
            f.write(launcher_content)
        scripts_created.append("launch.py")
        print("✅ launch.py (Unified launcher)")
    except Exception as e:
        print(f"❌ Failed to create launch.py: {e}")

    # Make scripts executable on Unix systems
    if sys.platform != "win32":
        for script in scripts_created:
            try:
                os.chmod(script, 0o755)  # nosec B103 - intentional: make script executable
            except:
                pass

    return len(scripts_created) > 0

def main():
    """Main installation process"""
    print("🎯 TRADING SYSTEM INSTALLER")
    print("="*60)
    print(f"📅 Installation Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📍 Installation Directory: {Path.cwd()}")

    steps = [
        ("Python Version Check", check_python_version),
        ("Install Dependencies", install_dependencies),
        ("Create Directories", create_directories),
        ("Setup Configuration", setup_configuration),
        ("Setup API Credentials", setup_api_credentials),
        ("Create Launch Scripts", create_launch_scripts),
        ("Run Health Check", run_health_check)
    ]

    results = []

    for step_name, step_func in steps:
        try:
            result = step_func()
            results.append((step_name, result))

            if not result:
                print(f"\n⚠️ {step_name} failed but continuing...")

        except Exception as e:
            print(f"\n❌ {step_name} failed with error: {e}")
            results.append((step_name, False))

    # Installation Summary
    print_header("Installation Summary")

    passed = 0
    for step_name, result in results:
        status = "✅ SUCCESS" if result else "❌ FAILED"
        print(f"{status:11} {step_name}")
        if result:
            passed += 1

    total = len(results)
    success_rate = (passed / total) * 100

    print(f"\n📊 Overall Success Rate: {passed}/{total} ({success_rate:.1f}%)")

    if success_rate >= 80:
        print_header("🎉 Installation Complete!")
        print("✅ Trading system is ready to use!")
        print("\n🚀 Next Steps:")
        print("1. Run: python zerodha_token_manager.py (to authenticate)")
        print("2. Run: python launch.py (to start the system)")
        print("3. Or run: python enhanced_trading_system_complete.py (direct launch)")
        print("\n📚 Quick Start Guide:")
        print("• Paper Trading: python launch_paper_trading.py")
        print("• Dashboard: python launch_dashboard.py")
        print("• Health Check: python system_health_check.py")

        return 0
    else:
        print_header("⚠️ Installation Issues Detected")
        print("Some components failed to install correctly.")
        print("Please review the errors above and fix them before using the system.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
