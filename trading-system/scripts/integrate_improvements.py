#!/usr/bin/env python3
"""
Integration Script for Trading System Improvements
Helps integrate new configuration, strategies, and trading loop into existing code
"""

import os
import sys
from pathlib import Path
import shutil
from datetime import datetime

class ImprovementIntegrator:
    """Manages integration of improvements into trading system"""

    def __init__(self):
        self.root_dir = Path(__file__).parent.parent
        self.backup_dir = self.root_dir / "integration_backup" / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.changes_made = []

    def create_backup(self, filepath):
        """Create backup of file before modifying"""
        if not filepath.exists():
            return None

        backup_path = self.backup_dir / filepath.relative_to(self.root_dir)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(filepath, backup_path)
        return backup_path

    def step1_activate_config(self):
        """Activate the new unified configuration system"""
        print("\n" + "="*70)
        print("STEP 1: Activate Unified Configuration")
        print("="*70)

        # Check if new config exists
        new_config = self.root_dir / "unified_config_new.py"
        yaml_config = self.root_dir / "trading_config.yaml"

        if not new_config.exists():
            print("❌ Error: unified_config_new.py not found")
            return False

        if not yaml_config.exists():
            print("❌ Error: trading_config.yaml not found")
            return False

        print("✅ New configuration files found")

        # Rename old unified_config.py if it exists
        old_unified = self.root_dir / "unified_config.py"
        if old_unified.exists():
            self.create_backup(old_unified)
            old_unified.rename(self.root_dir / "unified_config.py.old")
            print(f"✅ Backed up old unified_config.py")
            self.changes_made.append("Renamed unified_config.py → unified_config.py.old")

        # Create symlink or copy unified_config_new.py → unified_config.py
        target = self.root_dir / "unified_config.py"
        shutil.copy2(new_config, target)
        print(f"✅ Activated unified_config_new.py as unified_config.py")
        self.changes_made.append("Activated new unified configuration")

        print("\n📝 Configuration activated. You can now use:")
        print("   from unified_config import get_config")
        print("   config = get_config()")

        return True

    def step2_activate_strategies(self):
        """Activate refactored strategies"""
        print("\n" + "="*70)
        print("STEP 2: Activate Refactored Strategies")
        print("="*70)

        strategies_dir = self.root_dir / "strategies"
        strategy_files = [
            "bollinger_fixed.py",
            "rsi_fixed.py",
            "moving_average_fixed.py"
        ]

        activated = []

        for old_file in strategy_files:
            old_path = strategies_dir / old_file
            new_file = old_file.replace(".py", "_new.py")
            new_path = strategies_dir / new_file

            if not new_path.exists():
                print(f"⚠️  {new_file} not found, skipping")
                continue

            # Backup old file
            if old_path.exists():
                self.create_backup(old_path)
                backup_name = old_file.replace(".py", ".py.old_original")
                old_path.rename(strategies_dir / backup_name)
                print(f"✅ Backed up {old_file}")

            # Copy new version to old name
            shutil.copy2(new_path, old_path)
            print(f"✅ Activated {new_file} → {old_file}")
            activated.append(old_file)
            self.changes_made.append(f"Activated refactored {old_file}")

        if activated:
            print(f"\n✅ Activated {len(activated)} refactored strategies")
            print("\n📝 Your existing imports will now use refactored versions:")
            print("   from strategies.bollinger_fixed import BollingerBandsStrategy")
            print("   from strategies.rsi_fixed import EnhancedRSIStrategy")
            print("   from strategies.moving_average_fixed import ImprovedMovingAverageCrossover")
            return True
        else:
            print("❌ No strategies were activated")
            return False

    def step3_validate_integration(self):
        """Validate that integration was successful"""
        print("\n" + "="*70)
        print("STEP 3: Validate Integration")
        print("="*70)

        # Test config import
        print("\nTesting configuration...")
        try:
            sys.path.insert(0, str(self.root_dir))
            from unified_config import get_config
            config = get_config()
            print(f"✅ Config loaded: {config.risk.max_positions} max positions")
        except Exception as e:
            print(f"❌ Config test failed: {e}")
            return False

        # Test strategy imports
        print("\nTesting strategy imports...")
        try:
            from strategies.bollinger_fixed import BollingerBandsStrategy
            from strategies.rsi_fixed import EnhancedRSIStrategy
            from strategies.moving_average_fixed import ImprovedMovingAverageCrossover

            bb = BollingerBandsStrategy()
            rsi = EnhancedRSIStrategy()
            ma = ImprovedMovingAverageCrossover()

            print(f"✅ Bollinger: {bb.name}")
            print(f"✅ RSI: {rsi.name}")
            print(f"✅ MA: {ma.name}")
        except Exception as e:
            print(f"❌ Strategy import failed: {e}")
            return False

        print("\n✅ All validation tests passed!")
        return True

    def generate_integration_report(self):
        """Generate report of changes made"""
        print("\n" + "="*70)
        print("INTEGRATION REPORT")
        print("="*70)

        print(f"\nBackup Location: {self.backup_dir}")
        print(f"\nChanges Made ({len(self.changes_made)}):")
        for i, change in enumerate(self.changes_made, 1):
            print(f"  {i}. {change}")

        print("\n" + "="*70)
        print("NEXT STEPS")
        print("="*70)
        print("\n1. Review changes in your code that import these modules")
        print("2. Run your test suite to ensure everything works")
        print("3. Test in development environment before production")
        print("\nTo rollback if needed:")
        print(f"  - Restore files from: {self.backup_dir}")

    def rollback(self):
        """Rollback integration changes"""
        print("\n" + "="*70)
        print("ROLLBACK")
        print("="*70)

        if not self.backup_dir.exists():
            print("❌ No backup found")
            return False

        print(f"Restoring from: {self.backup_dir}")

        # Restore all backed up files
        for backup_file in self.backup_dir.rglob("*"):
            if backup_file.is_file():
                relative = backup_file.relative_to(self.backup_dir)
                target = self.root_dir / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_file, target)
                print(f"✅ Restored: {relative}")

        print("\n✅ Rollback complete")
        return True

    def run(self, mode="integrate"):
        """Run integration process"""
        print("="*70)
        print("TRADING SYSTEM INTEGRATION TOOL")
        print("="*70)
        print(f"Mode: {mode}")
        print(f"Root: {self.root_dir}")
        print()

        if mode == "rollback":
            return self.rollback()

        # Create backup directory
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        print(f"✅ Backup directory created: {self.backup_dir}")

        # Run integration steps
        success = True

        # Step 1: Configuration
        if not self.step1_activate_config():
            print("\n❌ Configuration activation failed")
            success = False

        # Step 2: Strategies
        if success and not self.step2_activate_strategies():
            print("\n❌ Strategy activation failed")
            success = False

        # Step 3: Validation
        if success and not self.step3_validate_integration():
            print("\n❌ Validation failed")
            success = False

        # Generate report
        self.generate_integration_report()

        if success:
            print("\n" + "="*70)
            print("✅ INTEGRATION SUCCESSFUL")
            print("="*70)
            print("\nYour trading system is now using the improved components!")
        else:
            print("\n" + "="*70)
            print("⚠️  INTEGRATION COMPLETED WITH WARNINGS")
            print("="*70)
            print("\nPlease review the errors above and test carefully.")

        return success

def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Integrate trading system improvements")
    parser.add_argument(
        "mode",
        choices=["integrate", "rollback"],
        default="integrate",
        nargs="?",
        help="Integration mode (integrate or rollback)"
    )

    args = parser.parse_args()

    integrator = ImprovementIntegrator()
    success = integrator.run(mode=args.mode)

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
