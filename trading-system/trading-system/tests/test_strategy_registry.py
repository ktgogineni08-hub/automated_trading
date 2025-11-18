#!/usr/bin/env python3
"""
Comprehensive tests for strategy_registry.py module
Tests StrategyRegistry for strategy management and validation
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock dependencies before importing - comprehensive mocking
_MODULES_TO_PATCH = [
    'strategies',
    'strategies.base',
    'strategies.moving_average',
    'strategies.rsi',
    'strategies.bollinger',
    'infrastructure.security',
    'infrastructure.database_manager',
]
_ORIGINAL_MODULES = {name: sys.modules.get(name) for name in _MODULES_TO_PATCH}

for module_name in _MODULES_TO_PATCH:
    sys.modules[module_name] = MagicMock()

# Create mock BaseStrategy class
class MockBaseStrategyClass:
    """Mock base strategy for testing"""
    pass

sys.modules['strategies.base'].BaseStrategy = MockBaseStrategyClass

# Import directly from module file to avoid core/__init__.py imports
import importlib.util
spec = importlib.util.spec_from_file_location(
    "strategy_registry",
    str(Path(__file__).parent.parent / "core" / "strategy_registry.py")
)
strategy_registry_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(strategy_registry_module)

for name, original in _ORIGINAL_MODULES.items():
    if original is not None:
        sys.modules[name] = original
    else:
        sys.modules.pop(name, None)

StrategyStatus = strategy_registry_module.StrategyStatus
StrategyMetadata = strategy_registry_module.StrategyMetadata
StrategyValidation = strategy_registry_module.StrategyValidation
StrategyRegistry = strategy_registry_module.StrategyRegistry
get_strategy_registry = strategy_registry_module.get_strategy_registry


# ============================================================================
# Mock Classes
# ============================================================================

class MockBaseStrategy(MockBaseStrategyClass):
    """Mock BaseStrategy for testing"""
    name = "MockStrategy"
    __version__ = "1.0.0"
    __author__ = "Test Author"
    risk_level = "low"
    tags = ["test", "mock"]

    def __init__(self, param1="default", param2=100):
        self.param1 = param1
        self.param2 = param2

    def generate_signals(self, data):
        return []

    def validate_data(self, data):
        return True


class MockInvalidStrategy(MockBaseStrategyClass):
    """Strategy missing required methods"""
    name = "InvalidStrategy"

    def __init__(self):
        pass


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_database():
    """Mock database"""
    db = Mock()
    db.get_strategy_performance = Mock(return_value=[])
    return db


@pytest.fixture
def registry(mock_database, tmp_path):
    """Create StrategyRegistry with mocked database"""
    # Create temp strategy directory
    strategy_dir = tmp_path / "strategies"
    strategy_dir.mkdir()

    with patch('core.strategy_registry.get_database', return_value=mock_database):
        reg = StrategyRegistry(strategy_dir=str(strategy_dir))
        return reg


# ============================================================================
# Enum Tests
# ============================================================================

class TestStrategyStatus:
    """Test StrategyStatus enum"""

    def test_strategy_status_values(self):
        """Test StrategyStatus enum values"""
        assert StrategyStatus.ACTIVE.value == "active"
        assert StrategyStatus.DISABLED.value == "disabled"
        assert StrategyStatus.DEPRECATED.value == "deprecated"
        assert StrategyStatus.TESTING.value == "testing"


# ============================================================================
# Dataclass Tests
# ============================================================================

class TestStrategyMetadata:
    """Test StrategyMetadata dataclass"""

    def test_strategy_metadata_creation(self):
        """Test creating StrategyMetadata"""
        metadata = StrategyMetadata(
            name="TestStrategy",
            class_name="TestStrategy",
            module_path="strategies.test",
            description="Test description",
            version="1.0.0",
            author="Test Author",
            created_date=datetime.now()
        )

        assert metadata.name == "TestStrategy"
        assert metadata.version == "1.0.0"
        assert metadata.status == StrategyStatus.ACTIVE
        assert metadata.risk_level == "medium"

    def test_strategy_metadata_defaults(self):
        """Test StrategyMetadata default values"""
        metadata = StrategyMetadata(
            name="Test",
            class_name="Test",
            module_path="test",
            description="desc",
            version="1.0",
            author="author",
            created_date=datetime.now()
        )

        assert metadata.parameters == {}
        assert metadata.tags == []
        assert metadata.recommended_capital == 100000.0


class TestStrategyValidation:
    """Test StrategyValidation dataclass"""

    def test_strategy_validation_creation(self):
        """Test creating StrategyValidation"""
        validation = StrategyValidation(
            is_valid=True,
            errors=[],
            warnings=["Minor warning"],
            score=95.0
        )

        assert validation.is_valid is True
        assert validation.score == 95.0
        assert len(validation.warnings) == 1

    def test_strategy_validation_defaults(self):
        """Test StrategyValidation defaults"""
        validation = StrategyValidation(is_valid=False)

        assert validation.errors == []
        assert validation.warnings == []
        assert validation.score == 0.0


# ============================================================================
# Initialization Tests
# ============================================================================

class TestInitialization:
    """Test StrategyRegistry initialization"""

    def test_initialization_default_dir(self, mock_database):
        """Test initialization with default directory"""
        with patch('core.strategy_registry.get_database', return_value=mock_database):
            registry = StrategyRegistry()

            assert registry.strategy_dir == Path("strategies")
            assert registry._strategies == {}
            assert registry._metadata == {}

    def test_initialization_custom_dir(self, mock_database):
        """Test initialization with custom directory"""
        with patch('core.strategy_registry.get_database', return_value=mock_database):
            registry = StrategyRegistry(strategy_dir="custom_strategies")

            assert registry.strategy_dir == Path("custom_strategies")


# ============================================================================
# Strategy Registration Tests
# ============================================================================

class TestStrategyRegistration:
    """Test strategy registration"""

    def test_register_strategy_manual(self, registry):
        """Test manually registering a strategy"""
        result = registry.register_strategy("MockStrategy", MockBaseStrategy)

        assert result is True
        assert "MockStrategy" in registry._strategies
        assert "MockStrategy" in registry._metadata

    def test_register_strategy_with_metadata(self, registry):
        """Test registering strategy with custom metadata"""
        custom_metadata = StrategyMetadata(
            name="CustomStrategy",
            class_name="CustomStrategy",
            module_path="test.module",
            description="Custom desc",
            version="2.0.0",
            author="Me",
            created_date=datetime.now()
        )

        result = registry.register_strategy("CustomStrategy", MockBaseStrategy, custom_metadata)

        assert result is True
        assert registry._metadata["CustomStrategy"].version == "2.0.0"

    def test_register_strategy_exception_handling(self, registry):
        """Test exception handling during registration"""
        # Use invalid class to trigger exception
        result = registry.register_strategy("Invalid", None)

        assert result is False


# ============================================================================
# Strategy Discovery Tests
# ============================================================================

class TestStrategyDiscovery:
    """Test strategy discovery"""

    def test_discover_strategies_no_directory(self, registry):
        """Test discovery when directory doesn't exist"""
        # Remove the directory
        import shutil
        if registry.strategy_dir.exists():
            shutil.rmtree(registry.strategy_dir)

        count = registry.discover_strategies()

        assert count == 0

    def test_discover_strategies_empty_directory(self, registry):
        """Test discovery in empty directory"""
        count = registry.discover_strategies()

        assert count == 0

    def test_discover_strategies_with_files(self, registry, tmp_path):
        """Test discovery with strategy files"""
        # Create a mock strategy file
        strategy_file = registry.strategy_dir / "test_strategy.py"
        strategy_file.write_text("""
from strategies.base import BaseStrategy

class TestStrategy(BaseStrategy):
    name = "TestStrategy"
    def generate_signals(self, data):
        return []
    def validate_data(self, data):
        return True
""")

        # Mock the imports
        with patch('importlib.import_module') as mock_import:
            mock_module = Mock()
            mock_module.TestStrategy = MockBaseStrategy
            mock_import.return_value = mock_module

            count = registry.discover_strategies()

            # Should attempt to import
            assert mock_import.called


# ============================================================================
# Metadata Extraction Tests
# ============================================================================

class TestMetadataExtraction:
    """Test metadata extraction"""

    def test_extract_metadata_basic(self, registry):
        """Test extracting metadata from strategy class"""
        metadata = registry._extract_metadata(MockBaseStrategy, "strategies.mock")

        assert metadata.name == "MockBaseStrategy"
        assert metadata.class_name == "MockBaseStrategy"
        assert metadata.module_path == "strategies.mock"
        assert metadata.version == "1.0.0"
        assert metadata.author == "Test Author"
        assert metadata.risk_level == "low"

    def test_extract_metadata_parameters(self, registry):
        """Test extracting parameters from __init__"""
        metadata = registry._extract_metadata(MockBaseStrategy, "strategies.mock")

        assert 'param1' in metadata.parameters
        assert 'param2' in metadata.parameters
        assert metadata.parameters['param1']['default'] == 'default'
        assert metadata.parameters['param2']['default'] == 100


# ============================================================================
# Strategy Retrieval Tests
# ============================================================================

class TestStrategyRetrieval:
    """Test getting strategy instances"""

    def test_get_strategy_success(self, registry):
        """Test getting strategy instance"""
        registry.register_strategy("MockStrategy", MockBaseStrategy)

        instance = registry.get_strategy("MockStrategy")

        assert instance is not None
        assert isinstance(instance, MockBaseStrategy)

    def test_get_strategy_not_found(self, registry):
        """Test getting nonexistent strategy"""
        instance = registry.get_strategy("NonExistent")

        assert instance is None

    def test_get_strategy_with_params(self, registry):
        """Test getting strategy with custom parameters"""
        registry.register_strategy("MockStrategy", MockBaseStrategy)

        instance = registry.get_strategy("MockStrategy", param1="custom", param2=200)

        assert instance.param1 == "custom"
        assert instance.param2 == 200

    def test_get_strategy_caching(self, registry):
        """Test that strategy instances are cached"""
        registry.register_strategy("MockStrategy", MockBaseStrategy)

        instance1 = registry.get_strategy("MockStrategy", param1="test")
        instance2 = registry.get_strategy("MockStrategy", param1="test")

        assert instance1 is instance2  # Same instance from cache

    def test_get_strategy_different_params_different_instances(self, registry):
        """Test different parameters create different instances"""
        registry.register_strategy("MockStrategy", MockBaseStrategy)

        instance1 = registry.get_strategy("MockStrategy", param1="test1")
        instance2 = registry.get_strategy("MockStrategy", param1="test2")

        assert instance1 is not instance2


# ============================================================================
# Strategy Validation Tests
# ============================================================================

class TestStrategyValidation:
    """Test strategy validation"""

    def test_validate_strategy_valid(self, registry):
        """Test validating a valid strategy"""
        registry.register_strategy("MockStrategy", MockBaseStrategy)

        validation = registry.validate_strategy("MockStrategy")

        assert validation.is_valid is True
        assert validation.score >= 90

    def test_validate_strategy_missing_methods(self, registry):
        """Test validating strategy with missing methods"""
        registry.register_strategy("InvalidStrategy", MockInvalidStrategy)

        validation = registry.validate_strategy("InvalidStrategy")

        assert validation.is_valid is False
        assert any("Missing required method" in e for e in validation.errors)

    def test_validate_strategy_not_found(self, registry):
        """Test validating nonexistent strategy"""
        validation = registry.validate_strategy("NonExistent")

        assert validation.is_valid is False
        assert "not found" in validation.errors[0]

    def test_validate_strategy_no_docstring(self, registry):
        """Test validation warning for missing docstring"""
        class NoDocStrategy:
            name = "NoDoc"
            def __init__(self):
                pass
            def generate_signals(self, data):
                return []
            def validate_data(self, data):
                return True

        registry.register_strategy("NoDoc", NoDocStrategy)

        validation = registry.validate_strategy("NoDoc")

        assert any("docstring" in w.lower() for w in validation.warnings)


# ============================================================================
# Strategy Listing Tests
# ============================================================================

class TestStrategyListing:
    """Test listing strategies"""

    def test_list_strategies_all(self, registry):
        """Test listing all strategies"""
        registry.register_strategy("Strategy1", MockBaseStrategy)
        registry.register_strategy("Strategy2", MockBaseStrategy)

        strategies = registry.list_strategies()

        assert len(strategies) == 2
        assert "Strategy1" in strategies
        assert "Strategy2" in strategies

    def test_list_strategies_filter_by_status(self, registry):
        """Test filtering strategies by status"""
        registry.register_strategy("Active", MockBaseStrategy)

        # Manually set status
        registry._metadata["Active"].status = StrategyStatus.ACTIVE

        strategies = registry.list_strategies(status=StrategyStatus.ACTIVE)

        assert "Active" in strategies

    def test_list_strategies_filter_by_risk(self, registry):
        """Test filtering strategies by risk level"""
        registry.register_strategy("LowRisk", MockBaseStrategy)

        strategies = registry.list_strategies(risk_level="low")

        assert "LowRisk" in strategies

    def test_list_strategies_sorted(self, registry):
        """Test that strategies are returned sorted"""
        registry.register_strategy("ZStrategy", MockBaseStrategy)
        registry.register_strategy("AStrategy", MockBaseStrategy)

        strategies = registry.list_strategies()

        assert strategies[0] == "AStrategy"
        assert strategies[1] == "ZStrategy"


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance:
    """Test performance tracking"""

    def test_update_performance_success(self, registry, mock_database):
        """Test updating strategy performance"""
        mock_database.get_strategy_performance.return_value = [{
            'strategy_name': 'MockStrategy',
            'total_trades': 100,
            'win_rate': 0.65,
            'total_pnl': 50000,
            'sharpe_ratio': 1.5
        }]

        registry.register_strategy("MockStrategy", MockBaseStrategy)

        perf = registry.update_performance("MockStrategy")

        assert perf is not None

    def test_update_performance_no_data(self, registry, mock_database):
        """Test updating performance with no data"""
        mock_database.get_strategy_performance.return_value = []

        registry.register_strategy("MockStrategy", MockBaseStrategy)

        perf = registry.update_performance("MockStrategy")

        assert perf is None

    def test_get_best_performing_strategy(self, registry, mock_database):
        """Test getting best performing strategy"""
        mock_database.get_strategy_performance.return_value = [
            {
                'strategy_name': 'Strategy1',
                'total_trades': 50,
                'win_rate': 0.60,
                'total_pnl': 30000,
                'sharpe_ratio': 1.2
            },
            {
                'strategy_name': 'Strategy2',
                'total_trades': 100,
                'win_rate': 0.70,
                'total_pnl': 50000,
                'sharpe_ratio': 1.8
            }
        ]

        best = registry.get_best_performing_strategy(min_trades=10)

        assert best == "Strategy2"

    def test_get_best_performing_strategy_min_trades(self, registry, mock_database):
        """Test best performing with minimum trades filter"""
        mock_database.get_strategy_performance.return_value = [
            {
                'strategy_name': 'LowTrades',
                'total_trades': 5,  # Below minimum
                'win_rate': 0.80,
                'total_pnl': 100000,
                'sharpe_ratio': 2.0
            }
        ]

        best = registry.get_best_performing_strategy(min_trades=10)

        assert best is None


# ============================================================================
# Strategy Comparison Tests
# ============================================================================

class TestStrategyComparison:
    """Test strategy comparison"""

    def test_compare_strategies(self, registry):
        """Test comparing multiple strategies"""
        registry.register_strategy("Strategy1", MockBaseStrategy)
        registry.register_strategy("Strategy2", MockBaseStrategy)

        comparison = registry.compare_strategies(["Strategy1", "Strategy2"])

        assert "Strategy1" in comparison
        assert "Strategy2" in comparison
        assert 'metadata' in comparison["Strategy1"]
        assert 'validation' in comparison["Strategy1"]


# ============================================================================
# Statistics Tests
# ============================================================================

class TestStatistics:
    """Test registry statistics"""

    def test_get_statistics(self, registry):
        """Test getting registry statistics"""
        registry.register_strategy("Strategy1", MockBaseStrategy)
        registry.register_strategy("Strategy2", MockBaseStrategy)

        stats = registry.get_statistics()

        assert stats['total_strategies'] == 2
        assert stats['active_strategies'] == 2
        assert stats['cached_instances'] >= 0


# ============================================================================
# Singleton Tests
# ============================================================================

class TestSingleton:
    """Test global registry singleton"""

    def test_get_strategy_registry_creates_instance(self):
        """Test that get_strategy_registry creates instance"""
        # Reset global
        import core.strategy_registry as module
        module._global_registry = None

        with patch('core.strategy_registry.get_database'):
            registry = get_strategy_registry()

            assert registry is not None

    def test_get_strategy_registry_returns_same_instance(self):
        """Test that subsequent calls return same instance"""
        # Reset global
        import core.strategy_registry as module
        module._global_registry = None

        with patch('core.strategy_registry.get_database'):
            registry1 = get_strategy_registry()
            registry2 = get_strategy_registry()

            assert registry1 is registry2


# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases"""

    def test_get_metadata_nonexistent(self, registry):
        """Test getting metadata for nonexistent strategy"""
        metadata = registry.get_metadata("NonExistent")

        assert metadata is None

    def test_instantiation_exception(self, registry):
        """Test handling exception during instantiation"""
        class BrokenStrategy:
            name = "Broken"
            def __init__(self):
                raise ValueError("Cannot instantiate")
            def generate_signals(self, data):
                return []
            def validate_data(self, data):
                return True

        registry.register_strategy("Broken", BrokenStrategy)

        instance = registry.get_strategy("Broken")

        assert instance is None

    def test_validation_exception_in_instantiation(self, registry):
        """Test validation handles instantiation exceptions"""
        class BrokenStrategy:
            name = "Broken"
            def __init__(self):
                raise ValueError("Cannot instantiate")
            def generate_signals(self, data):
                return []
            def validate_data(self, data):
                return True

        registry.register_strategy("Broken", BrokenStrategy)

        validation = registry.validate_strategy("Broken")

        assert "Cannot instantiate" in str(validation.errors)


if __name__ == "__main__":
    # Run tests with: pytest test_strategy_registry.py -v
    pytest.main([__file__, "-v", "--tb=short"])
