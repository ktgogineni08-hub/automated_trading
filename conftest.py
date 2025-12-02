"""Pytest configuration for trading-system project."""

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ensure_real_strategies_module():
    """Reload the strategies package if a test replaced it with a mock."""
    module = sys.modules.get("strategies")
    if module is None:
        importlib.import_module("strategies")
        return

    if not hasattr(module, "__path__"):
        # Module was replaced with a mock – remove and re-import the real package.
        sys.modules.pop("strategies", None)
        importlib.import_module("strategies")


def pytest_runtest_setup(item):
    # Allow strategy_registry tests to inject their own mocks
    if "test_strategy_registry.py" in item.nodeid:
        return
    _ensure_real_strategies_module()


collect_ignore_glob = [
    "archived_development_files/old_tests/*.py",
]
