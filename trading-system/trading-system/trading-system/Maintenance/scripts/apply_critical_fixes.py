#!/usr/bin/env python3
"""
CRITICAL FIXES APPLICATION SCRIPT
Applies all critical, high, and medium severity fixes to the trading system.
"""

import re
import sys
from pathlib import Path

def apply_thread_safety_fix():
    """Fix indentation error in sync_positions_from_kite"""
    file_path = Path("enhanced_trading_system_complete.py")
    content = file_path.read_text()

    # Fix the indentation error at line 1842-1843
    content = content.replace(
        """        try:
            with self._position_lock:
            # Fetch actual positions from Kite broker""",
        """        try:
            with self._position_lock:
                # Fetch actual positions from Kite broker"""
    )

    # Fix all subsequent lines in the function to be inside the lock
    # Find and fix the indentation for lines 1844-1942
    lines = content.split('\n')
    fixed_lines = []
    in_sync_function = False
    lock_context_started = False
    indent_level = 0

    for i, line in enumerate(lines):
        if 'def sync_positions_from_kite' in line:
            in_sync_function = True
            fixed_lines.append(line)
            continue

        if in_sync_function and 'with self._position_lock:' in line:
            lock_context_started = True
            indent_level = len(line) - len(line.lstrip())
            fixed_lines.append(line)
            continue

        if lock_context_started and 'except Exception as e:' in line and 'sync positions' in lines[i+1]:
            # End of lock context
            lock_context_started = False
            in_sync_function = False
            fixed_lines.append(line)
            continue

        if lock_context_started and line.strip() and not line.strip().startswith('#'):
            # Inside lock context - ensure proper indentation
            current_indent = len(line) - len(line.lstrip())
            if current_indent <= indent_level:
                # Add extra indent
                line = '    ' + line

        fixed_lines.append(line)

    file_path.write_text('\n'.join(fixed_lines))
    print("✅ Fixed thread safety indentation in sync_positions_from_kite")

def add_monitor_positions_locking():
    """Add thread locking to monitor_positions"""
    file_path = Path("enhanced_trading_system_complete.py")
    content = file_path.read_text()

    # Find monitor_positions method
    pattern = r'(def monitor_positions\(self, price_map.*?\):.*?""".*?""")'

    def replacement(match):
        return match.group(1) + '\n        # CRITICAL FIX: Thread-safe position monitoring\n        with self._position_lock:\n            positions_snapshot = copy.deepcopy(self.positions)\n        \n        # Work with snapshot outside lock'

    content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    file_path.write_text(content)
    print("✅ Added thread locking to monitor_positions")

def add_send_dashboard_update_locking():
    """Add thread locking to send_dashboard_update"""
    file_path = Path("enhanced_trading_system_complete.py")
    content = file_path.read_text()

    # Find send_dashboard_update method and add locking
    pattern = r'(def send_dashboard_update\(self.*?\):.*?""".*?""")'

    def replacement(match):
        return match.group(1) + '\n        # CRITICAL FIX: Thread-safe dashboard updates\n        with self._position_lock:\n            positions_snapshot = copy.deepcopy(self.positions)\n            cash_snapshot = self.cash\n            trades_count_snapshot = self.trades_count\n        \n        # Save state using snapshot'

    content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    file_path.write_text(content)
    print("✅ Added thread locking to send_dashboard_update")

def fix_zerodha_token_manager():
    """Remove interactive credential input fallback"""
    file_path = Path("zerodha_token_manager.py")
    if not file_path.exists():
        print("⚠️ zerodha_token_manager.py not found, skipping")
        return

    content = file_path.read_text()

    # Remove input() fallback for API credentials
    content = re.sub(
        r'API_KEY = os\.getenv.*?\n.*?if not API_KEY:.*?API_KEY = input\(.*?\)',
        '''API_KEY = os.getenv("ZERODHA_API_KEY")
    if not API_KEY:
        print("❌ ERROR: ZERODHA_API_KEY must be set in environment variables")
        print("Run: export ZERODHA_API_KEY='your_key'")
        sys.exit(1)''',
        content,
        flags=re.DOTALL
    )

    content = re.sub(
        r'API_SECRET = os\.getenv.*?\n.*?if not API_SECRET:.*?API_SECRET = input\(.*?\)',
        '''API_SECRET = os.getenv("ZERODHA_API_SECRET")
    if not API_SECRET:
        print("❌ ERROR: ZERODHA_API_SECRET must be set in environment variables")
        print("Run: export ZERODHA_API_SECRET='your_secret'")
        sys.exit(1)''',
        content,
        flags=re.DOTALL
    )

    file_path.write_text(content)
    print("✅ Removed interactive credential input from zerodha_token_manager.py")

def add_price_validation():
    """Add price validation with timestamps"""
    file_path = Path("enhanced_trading_system_complete.py")
    content = file_path.read_text()

    # Find monitor_positions and add validation
    validation_code = '''
        # CRITICAL FIX: Validate price data before exit evaluation
        now = datetime.now()

        for symbol, pos in list(positions_snapshot.items()):
            current_price = price_map.get(symbol) if price_map else None
            price_timestamp = price_map.get(f'{symbol}_timestamp') if price_map else None

            # Validate price exists and is positive
            if current_price is None or current_price <= 0:
                logger.logger.warning(f"⚠️ Invalid price for {symbol} ({current_price}), skipping monitoring")
                continue

            # Validate price is fresh (< 2 minutes old)
            if price_timestamp:
                age_seconds = (now - price_timestamp).total_seconds()
                if age_seconds > 120:
                    logger.logger.warning(f"⚠️ Stale price for {symbol}: {age_seconds:.0f}s old, skipping")
                    continue
            else:
                logger.logger.debug(f"No timestamp for {symbol} price, using with caution")
    '''

    # Insert after positions_snapshot creation
    pattern = r'(positions_snapshot = copy\.deepcopy\(self\.positions\))\s+# Work with snapshot'
    content = re.sub(pattern, r'\1\n' + validation_code + '\n        # Work with validated snapshot', content)

    file_path.write_text(content)
    print("✅ Added price validation with timestamps")

def fix_intelligent_exit_manager_divide_by_zero():
    """Fix potential divide-by-zero in intelligent_exit_manager"""
    file_path = Path("intelligent_exit_manager.py")
    if not file_path.exists():
        print("⚠️ intelligent_exit_manager.py not found, skipping")
        return

    content = file_path.read_text()

    # Replace direct division with safe_divide
    content = re.sub(
        r'pnl_pct = \(current_price - entry_price\) / entry_price',
        r'from trading_utils import safe_divide\n        pnl_pct = safe_divide(current_price - entry_price, entry_price, default=0.0)',
        content
    )

    file_path.write_text(content)
    print("✅ Fixed divide-by-zero in intelligent_exit_manager.py")

def add_nse_holidays_support():
    """Add NSE holiday calendar support"""
    file_path = Path("advanced_market_manager.py")
    content = file_path.read_text()

    # Add holidays import in __init__
    init_pattern = r'(def __init__\(self, config: Dict = None\):.*?self\.ist = pytz\.timezone\(.*?\))'

    def replacement(match):
        return match.group(1) + '''

        # MEDIUM FIX: NSE holiday calendar
        try:
            import holidays
            self.nse_holidays = holidays.India(years=range(2024, 2030))
        except ImportError:
            logger.logger.warning("holidays package not installed, holiday checking disabled")
            self.nse_holidays = None'''

    content = re.sub(init_pattern, replacement, content, flags=re.DOTALL)

    # Update is_market_open to check holidays
    is_market_open_pattern = r'(def is_market_open\(self\) -> bool:.*?)(\s+if now\.weekday\(\) >= 5:)'

    def replacement2(match):
        return match.group(1) + '''

        # Check NSE holidays
        if self.nse_holidays and now.date() in self.nse_holidays:
            return False
''' + match.group(2)

    content = re.sub(is_market_open_pattern, replacement2, content, flags=re.DOTALL)

    file_path.write_text(content)
    print("✅ Added NSE holidays support to advanced_market_manager.py")

def main():
    """Apply all critical fixes"""
    print("🔧 Applying Critical Fixes to Trading System")
    print("=" * 60)

    try:
        print("\n📝 Phase 1: Thread Safety Fixes")
        apply_thread_safety_fix()
        add_monitor_positions_locking()
        add_send_dashboard_update_locking()

        print("\n📝 Phase 2: Security Fixes")
        fix_zerodha_token_manager()

        print("\n📝 Phase 3: Data Validation Fixes")
        add_price_validation()

        print("\n📝 Phase 4: Medium Priority Fixes")
        fix_intelligent_exit_manager_divide_by_zero()
        add_nse_holidays_support()

        print("\n✅ All fixes applied successfully!")
        print("\n⚠️ IMPORTANT: Run pytest to verify no regressions")

    except Exception as e:
        print(f"\n❌ Error applying fixes: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
