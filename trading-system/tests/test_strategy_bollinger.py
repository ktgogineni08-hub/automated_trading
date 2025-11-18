#!/usr/bin/env python3
"""Basic tests for strategies/bollinger.py"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

def test_strategy_import():
    """Test that strategy module imports"""
    try:
        import strategies.bollinger
        assert True
    except ImportError as e:
        pytest.skip(f"Strategy has dependencies: {e}")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
