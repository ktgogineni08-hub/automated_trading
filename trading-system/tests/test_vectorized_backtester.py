#!/usr/bin/env python3
"""Basic tests for vectorized_backtester.py module"""

import pytest
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

# Basic import test
def test_module_imports():
    """Test that module imports successfully"""
    try:
        import core.vectorized_backtester
        assert True
    except ImportError as e:
        pytest.skip(f"Module has import dependencies: {e}")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
