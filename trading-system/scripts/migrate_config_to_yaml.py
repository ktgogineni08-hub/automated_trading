#!/usr/bin/env python3
"""
Configuration Migration Script
Migrates from old JSON config files to new unified YAML format
"""

import json
import os
from pathlib import Path
from datetime import datetime


def backup_old_configs():
    """Backup old configuration files"""
    print("\n📦 Backing up old configuration files...")

    backup_dir = Path("config_backups") / datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)

    files_to_backup = [
        "trading_config.json",
        "trading_mode_config.json",
        "config.py",
        "unified_config.py"
    ]

    backed_up = []
    for filename in files_to_backup:
        filepath = Path(filename)
        if filepath.exists():
            backup_path = backup_dir / filename
            import shutil
            shutil.copy2(filepath, backup_path)
            backed_up.append(filename)
            print(f"  ✅ {filename} → {backup_path}")

    print(f"\n✅ Backed up {len(backed_up)} files to {backup_dir}")
    return backup_dir


def load_legacy_config():
    """Load configuration from legacy JSON files"""
    print("\n📖 Reading legacy configuration...")

    config_path = Path("trading_config.json")
    if not config_path.exists():
        print("  ⚠️  trading_config.json not found, using defaults")
        return {}

    with open(config_path, 'r') as f:
        config = json.load(f)

    print(f"  ✅ Loaded configuration from {config_path}")
    return config


def extract_env_vars(config: dict) -> dict:
    """Extract sensitive values to .env file"""
    print("\n🔐 Extracting sensitive values to .env...")

    env_vars = {}

    # Extract API credentials
    if 'api' in config and 'zerodha' in config['api']:
        zerodha = config['api']['zerodha']
        if zerodha.get('api_key'):
            env_vars['ZERODHA_API_KEY'] = zerodha['api_key']
        if zerodha.get('api_secret'):
            env_vars['ZERODHA_API_SECRET'] = zerodha['api_secret']

    # Extract dashboard config
    if 'dashboard' in config:
        if config['dashboard'].get('port'):
            env_vars['DASHBOARD_PORT'] = str(config['dashboard']['port'])

    # Write to .env file
    env_path = Path(".env")
    env_lines = []

    # Read existing .env if it exists
    if env_path.exists():
        with open(env_path, 'r') as f:
            env_lines = f.readlines()

    # Add new variables (don't duplicate)
    existing_vars = {line.split('=')[0] for line in env_lines if '=' in line}

    for key, value in env_vars.items():
        if key not in existing_vars:
            env_lines.append(f"{key}={value}\n")
            print(f"  ✅ Added {key} to .env")

    # Write back
    with open(env_path, 'w') as f:
        f.writelines(env_lines)

    print(f"\n✅ Environment variables updated in {env_path}")
    return env_vars


def verify_yaml_exists():
    """Verify trading_config.yaml exists"""
    yaml_path = Path("trading_config.yaml")

    if not yaml_path.exists():
        print("\n❌ trading_config.yaml not found!")
        print("   Please ensure the YAML config file exists before running migration.")
        return False

    print(f"\n✅ Found {yaml_path}")
    return True


def test_new_config():
    """Test loading the new configuration"""
    print("\n🧪 Testing new configuration system...")

    try:
        # Add current directory to path
        import sys
        sys.path.insert(0, str(Path.cwd()))

        from unified_config_new import get_config

        config = get_config()
        print("  ✅ Configuration loaded successfully!")
        print(f"     - Max positions: {config.risk.max_positions}")
        print(f"     - Min confidence: {config.strategies.min_confidence:.1%}")
        print(f"     - Risk per trade: {config.risk.risk_per_trade_pct:.1%}")

        return True

    except Exception as e:
        print(f"  ❌ Error loading configuration: {e}")
        import traceback
        traceback.print_exc()
        return False


def rename_old_files():
    """Rename old config files with .legacy extension"""
    print("\n📝 Renaming old configuration files...")

    files_to_rename = [
        "trading_config.json",
        "trading_mode_config.json"
    ]

    for filename in files_to_rename:
        filepath = Path(filename)
        if filepath.exists():
            legacy_path = filepath.with_suffix('.json.legacy')
            filepath.rename(legacy_path)
            print(f"  ✅ {filename} → {legacy_path}")


def create_migration_summary(backup_dir: Path):
    """Create a summary of the migration"""
    summary_path = backup_dir / "migration_summary.txt"

    with open(summary_path, 'w') as f:
        f.write("Configuration Migration Summary\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("Files Migrated:\n")
        f.write("  - trading_config.json → trading_config.yaml\n")
        f.write("  - config.py → unified_config_new.py\n\n")
        f.write("Changes Made:\n")
        f.write("  1. Created trading_config.yaml (YAML format)\n")
        f.write("  2. Extracted secrets to .env file\n")
        f.write("  3. Created unified config loader\n")
        f.write("  4. Backed up old files\n\n")
        f.write("Next Steps:\n")
        f.write("  1. Review .env file for sensitive values\n")
        f.write("  2. Update code to use: from unified_config_new import get_config\n")
        f.write("  3. Test thoroughly before production deployment\n")

    print(f"\n📄 Migration summary created: {summary_path}")


def main():
    """Run the migration"""
    print("=" * 60)
    print("   Configuration Migration Script")
    print("   Old JSON → New YAML Format")
    print("=" * 60)

    # Step 1: Verify YAML exists
    if not verify_yaml_exists():
        print("\n❌ Migration aborted")
        return

    # Step 2: Backup old configs
    backup_dir = backup_old_configs()

    # Step 3: Load legacy config
    legacy_config = load_legacy_config()

    # Step 4: Extract environment variables
    env_vars = extract_env_vars(legacy_config)

    # Step 5: Test new configuration
    if not test_new_config():
        print("\n⚠️  New configuration test failed!")
        response = input("    Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print("\n❌ Migration aborted")
            return

    # Step 6: Rename old files
    response = input("\n❓ Rename old config files to .legacy? (y/N): ")
    if response.lower() == 'y':
        rename_old_files()

    # Step 7: Create summary
    create_migration_summary(backup_dir)

    print("\n" + "=" * 60)
    print("✅ MIGRATION COMPLETE!")
    print("=" * 60)
    print("\n📝 Next Steps:")
    print("   1. Review .env file and ensure all secrets are set")
    print("   2. Test the system with new configuration")
    print("   3. Update imports in your code:")
    print("      from unified_config_new import get_config")
    print("      config = get_config()")
    print(f"\n📦 Backups saved to: {backup_dir}")
    print("\n⚠️  Before deploying to production:")
    print("   - Run full test suite")
    print("   - Test in staging environment")
    print("   - Verify all config values are correct")


if __name__ == "__main__":
    main()
