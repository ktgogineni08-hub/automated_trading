#!/usr/bin/env python3
"""
Script to integrate structured logging into existing modules
Month 2 - Week 1 Task
"""

import os
import re
from pathlib import Path
from typing import List, Tuple

# Modules that need structured logging integration
CRITICAL_MODULES = [
    "main.py",
    "core/trading_system.py",
    "core/portfolio/portfolio.py",
    "risk_manager.py",
    "zerodha_token_manager.py",
    "fno/terminal.py",
    "enhanced_dashboard_server.py"
]


def add_structured_logger_import(file_path: Path) -> Tuple[bool, str]:
    """
    Add structured logger import to a file if not already present

    Returns:
        Tuple of (success, message)
    """
    try:
        content = file_path.read_text()

        # Check if already has structured logger
        if 'from utilities.structured_logger import' in content:
            return True, f"Already has structured logger: {file_path.name}"

        # Find import section
        lines = content.split('\n')
        import_end_idx = 0

        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                import_end_idx = i + 1
            elif import_end_idx > 0 and line.strip() and not line.startswith('#'):
                break

        # Add structured logger import
        new_import = "from utilities.structured_logger import get_logger, log_function_call"
        lines.insert(import_end_idx, new_import)

        # Find logger initialization and replace
        new_lines = []
        for line in lines:
            if 'logger = logging.getLogger' in line:
                # Replace with structured logger
                indent = len(line) - len(line.lstrip())
                new_lines.append(' ' * indent + "logger = get_logger(__name__)")
            elif 'TradingLogger()' in line:
                # Replace TradingLogger with structured logger
                indent = len(line) - len(line.lstrip())
                new_lines.append(' ' * indent + "logger = get_logger(__name__)")
            else:
                new_lines.append(line)

        # Write back
        file_path.write_text('\n'.join(new_lines))

        return True, f"✅ Added structured logger to: {file_path.name}"

    except Exception as e:
        return False, f"❌ Error in {file_path.name}: {e}"


def add_correlation_context_example(file_path: Path) -> Tuple[bool, str]:
    """Add example of correlation context usage"""
    try:
        content = file_path.read_text()

        # Look for main execution functions
        if 'def main(' in content or 'def run(' in content:
            # Add comment about using correlation context
            comment = """
    # Use correlation context for tracking requests
    # with logger.correlation_context() as corr_id:
    #     logger.info("Processing request", request_id=corr_id)
"""
            if comment not in content:
                content = content.replace('def main(', comment + '\n    def main(', 1)
                file_path.write_text(content)
                return True, f"✅ Added correlation context example to: {file_path.name}"

        return True, f"No main function found in: {file_path.name}"

    except Exception as e:
        return False, f"❌ Error adding example to {file_path.name}: {e}"


def main():
    """Main integration script"""
    print("="*70)
    print("STRUCTURED LOGGING INTEGRATION")
    print("="*70)
    print()

    base_dir = Path("/Users/gogineni/Python/trading-system")
    os.chdir(base_dir)

    results = []

    for module_path in CRITICAL_MODULES:
        file_path = base_dir / module_path

        if not file_path.exists():
            results.append((False, f"⚠️  File not found: {module_path}"))
            continue

        print(f"Processing: {module_path}")

        # Add import
        success, msg = add_structured_logger_import(file_path)
        results.append((success, msg))
        print(f"  {msg}")

        # Add example
        success, msg = add_correlation_context_example(file_path)
        if "Added" in msg:
            print(f"  {msg}")

    print()
    print("="*70)
    print("SUMMARY")
    print("="*70)

    successful = sum(1 for success, _ in results if success)
    total = len(results)

    print(f"\n✅ Successful: {successful}/{total}")
    print(f"❌ Failed: {total - successful}/{total}")

    print("\n📋 Next Steps:")
    print("1. Review the changes in each file")
    print("2. Test imports: python -c 'from utilities.structured_logger import get_logger'")
    print("3. Update logging calls to use structured format")
    print("4. Add correlation contexts in main execution paths")
    print("5. Test with: python main.py --help")

    print("\n" + "="*70)


if __name__ == "__main__":
    main()
