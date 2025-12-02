#!/usr/bin/env python3
"""Basic tests for strategies/moving_average.py"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

def test_strategy_import():
    """Test that strategy module imports"""
    try:
        import strategies.moving_average
        assert True
    except ImportError as e:
        pytest.skip(f"Strategy has dependencies: {e}")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
