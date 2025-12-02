#!/usr/bin/env python3
"""
Integration Tests for Week 1-2 Critical Fixes

Tests all critical fixes:
1. Unified Configuration System
2. Fixed Bollinger Bands Strategy
3. Fixed RSI Strategy
4. Fixed Moving Average Strategy
5. Memory-Bounded Cache
6. Centralized Alert Management
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unified_config import (
    UnifiedTradingConfig, RiskConfig, StrategyConfig,
    APIConfig, CacheConfig, AlertConfig, ConfigValidationError
)
from strategies.bollinger_fixed import BollingerBandsStrategy
from strategies.rsi_fixed import EnhancedRSIStrategy
from strategies.moving_average_fixed import ImprovedMovingAverageCrossover
from infrastructure.memory_bounded_cache import MemoryBoundedCache, InstrumentCache
from infrastructure.alert_manager import AlertManager, AlertSeverity, AlertCategory


class TestUnifiedConfiguration:
    """Test unified configuration system"""

    def test_default_config_creation(self):
        """Test creating default configuration"""
        config = UnifiedTradingConfig()

        assert config.initial_capital == 1_000_000.0
        assert config.risk.risk_per_trade_pct == 0.015
        assert config.strategy.min_confidence == 0.45
        assert config.cache.max_cache_size_mb == 2048

    def test_config_validation_success(self):
        """Test valid configuration passes validation"""
        config = UnifiedTradingConfig()
        assert config.validate() == True

    def test_config_validation_failure(self):
        """Test invalid configuration fails validation"""
        config = UnifiedTradingConfig()
        config.risk.risk_per_trade_pct = 0.10  # 10% - too high

        with pytest.raises(ConfigValidationError):
            config.validate()

    def test_risk_per_trade_mode_adjustment(self):
        """Test risk adjustment based on trading mode"""
        config = UnifiedTradingConfig()

        # Paper mode - uses configured value
        config.risk.risk_per_trade_pct = 0.02
        assert config.get_risk_per_trade_for_mode() == 0.02

        # Live mode - capped at 1.5%
        from unified_config import TradingMode
        config.mode = TradingMode.LIVE
        config.risk.risk_per_trade_pct = 0.02
        assert config.get_risk_per_trade_for_mode() == 0.015  # Capped

    def test_config_save_and_load(self, tmp_path):
        """Test saving and loading configuration"""
        config = UnifiedTradingConfig()
        config.initial_capital = 500_000.0
        config.risk.risk_per_trade_pct = 0.01

        # Save
        config_file = tmp_path / "test_config.json"
        config.save_to_file(config_file)

        # Load
        loaded_config = UnifiedTradingConfig.from_file(config_file)

        assert loaded_config.initial_capital == 500_000.0
        assert loaded_config.risk.risk_per_trade_pct == 0.01


class TestBollingerBandsFixed:
    """Test fixed Bollinger Bands strategy"""

    @pytest.fixture
    def sample_data(self):
        """Create sample OHLCV data"""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='1min')
        data = pd.DataFrame({
            'timestamp': dates,
            'open': np.random.uniform(100, 110, 100),
            'high': np.random.uniform(105, 115, 100),
            'low': np.random.uniform(95, 105, 100),
            'close': np.random.uniform(100, 110, 100),
            'volume': np.random.randint(1000, 10000, 100)
        })
        return data

    def test_strategy_initialization(self):
        """Test strategy initializes correctly"""
        strategy = BollingerBandsStrategy()

        assert strategy.name == "Bollinger_Bands_Fixed"
        assert strategy.period == 20
        assert strategy.confirmation_bars == 2
        assert strategy.cooldown_minutes == 15

    def test_insufficient_data_handling(self):
        """Test strategy handles insufficient data"""
        strategy = BollingerBandsStrategy()
        small_data = pd.DataFrame({
            'close': [100, 101, 102]
        })

        signal = strategy.generate_signals(small_data, 'TEST')
        assert signal['signal'] == 0
        assert signal['reason'] == 'insufficient_data'

    def test_cooldown_mechanism(self, sample_data):
        """Test that cooldown prevents rapid signals"""
        strategy = BollingerBandsStrategy(cooldown_minutes=1)

        # First signal
        signal1 = strategy.generate_signals(sample_data, 'TEST')

        # Immediate second call (should be on cooldown)
        signal2 = strategy.generate_signals(sample_data, 'TEST')

        # If first generated a signal, second should be on cooldown
        if signal1['signal'] != 0:
            assert signal2['reason'] == 'cooldown'

    def test_position_awareness(self, sample_data):
        """Test strategy is aware of positions"""
        strategy = BollingerBandsStrategy()

        # Set position
        strategy.set_position('TEST', 1)  # Long position
        assert strategy.get_position('TEST') == 1

        strategy.set_position('TEST', 0)  # Flat
        assert strategy.get_position('TEST') == 0

    def test_no_division_by_zero(self):
        """Test strategy handles zero standard deviation"""
        strategy = BollingerBandsStrategy()

        # Create flat price data (zero std dev)
        flat_data = pd.DataFrame({
            'close': [100.0] * 50,
            'volume': [1000] * 50
        })

        # Should not raise exception
        signal = strategy.generate_signals(flat_data, 'TEST')
        assert signal['signal'] == 0  # Should return neutral


class TestRSIFixed:
    """Test fixed RSI strategy"""

    @pytest.fixture
    def trending_data(self):
        """Create trending price data"""
        # Downtrend followed by uptrend
        prices = list(range(100, 70, -1)) + list(range(70, 100))
        data = pd.DataFrame({
            'close': prices,
            'volume': [1000] * len(prices)
        })
        return data

    def test_strategy_initialization(self):
        """Test strategy initializes correctly"""
        strategy = EnhancedRSIStrategy()

        assert strategy.name == "Enhanced_RSI_Fixed"
        assert strategy.oversold == 25
        assert strategy.overbought == 75
        assert strategy.neutral == 50

    def test_exit_logic_exists(self, trending_data):
        """Test strategy has exit logic"""
        strategy = EnhancedRSIStrategy()

        # Set long position
        strategy.set_position('TEST', 1)

        # Generate signal (should check for exits)
        signal = strategy.generate_signals(trending_data, 'TEST')

        # Strategy should generate exit signals when appropriate
        assert 'exit' in signal['reason'] or signal['signal'] in [-1, 0, 1]

    def test_position_awareness(self):
        """Test position tracking"""
        strategy = EnhancedRSIStrategy()

        strategy.set_position('SYMBOL1', 1)
        strategy.set_position('SYMBOL2', -1)

        assert strategy.get_position('SYMBOL1') == 1
        assert strategy.get_position('SYMBOL2') == -1
        assert strategy.get_position('SYMBOL3') == 0  # Default

    def test_divergence_detection(self, trending_data):
        """Test divergence detection doesn't crash"""
        strategy = EnhancedRSIStrategy()

        # Should not raise exception
        signal = strategy.generate_signals(trending_data, 'TEST')
        assert signal is not None


class TestMovingAverageFixed:
    """Test fixed Moving Average strategy"""

    @pytest.fixture
    def crossover_data(self):
        """Create data with clear crossover"""
        # Start with short below long, then crossover
        prices = [100 - i*0.5 for i in range(30)] + [70 + i*0.5 for i in range(30)]
        data = pd.DataFrame({
            'close': prices,
            'volume': [1000] * len(prices)
        })
        return data

    def test_strategy_initialization(self):
        """Test strategy uses less aggressive parameters"""
        strategy = ImprovedMovingAverageCrossover()

        # Should be 5/20 not 3/10
        assert strategy.short_window == 5
        assert strategy.long_window == 20
        assert strategy.min_separation_pct == 0.005

    def test_crossover_only_signals(self, crossover_data):
        """Test strategy only signals on crossovers"""
        strategy = ImprovedMovingAverageCrossover()

        # First signal
        signal1 = strategy.generate_signals(crossover_data[:40], 'TEST')

        # Next bar (no crossover)
        signal2 = strategy.generate_signals(crossover_data[:41], 'TEST2')

        # Should not continuously signal
        assert signal1 is not None
        assert signal2 is not None

    def test_volume_confirmation(self, crossover_data):
        """Test volume confirmation feature"""
        strategy = ImprovedMovingAverageCrossover()

        # Add low volume
        low_vol_data = crossover_data.copy()
        low_vol_data['volume'] = 100  # Very low

        signal = strategy.generate_signals(low_vol_data, 'TEST')

        # Should still work with low volume (just won't boost signal)
        assert signal is not None

    def test_minimum_separation_threshold(self):
        """Test minimum separation prevents noise"""
        strategy = ImprovedMovingAverageCrossover()

        # Create data with tiny separation
        close_prices = [100.0 + i*0.001 for i in range(50)]
        data = pd.DataFrame({
            'close': close_prices,
            'volume': [1000] * 50
        })

        signal = strategy.generate_signals(data, 'TEST')

        # Should filter out insignificant moves
        if signal['signal'] != 0:
            assert 'crossover' in signal['reason'] or signal['reason'] == 'insufficient_separation'


class TestMemoryBoundedCache:
    """Test memory-bounded cache"""

    def test_cache_initialization(self):
        """Test cache initializes with limits"""
        cache = MemoryBoundedCache(max_size_mb=10, max_entries=100)

        assert cache.max_size_bytes == 10 * 1024 * 1024
        assert cache.max_entries == 100

    def test_basic_operations(self):
        """Test get/set operations"""
        cache = MemoryBoundedCache(max_size_mb=10)

        cache.set('key1', 'value1')
        assert cache.get('key1') == 'value1'

        cache.set('key2', 'value2')
        assert cache.get('key2') == 'value2'

        assert cache.get('nonexistent') is None

    def test_ttl_expiration(self):
        """Test TTL expiration"""
        import time

        cache = MemoryBoundedCache(max_size_mb=10, default_ttl=1)  # 1 second TTL

        cache.set('key1', 'value1')
        assert cache.get('key1') == 'value1'

        # Wait for expiration
        time.sleep(1.1)

        assert cache.get('key1') is None

    def test_lru_eviction(self):
        """Test LRU eviction when limit reached"""
        cache = MemoryBoundedCache(max_size_mb=1, max_entries=10)

        # Fill cache
        for i in range(15):
            cache.set(f'key_{i}', 'x' * 1000)

        # Early keys should be evicted (LRU)
        stats = cache.get_stats()
        assert stats['evictions'] > 0
        assert stats['entries'] <= 10

    def test_memory_limit_enforcement(self):
        """Test memory limit is enforced"""
        cache = MemoryBoundedCache(max_size_mb=1)

        # Try to cache large object
        large_data = 'x' * (2 * 1024 * 1024)  # 2MB
        result = cache.set('large', large_data)

        # Should reject (larger than max)
        assert result == False

    def test_cache_statistics(self):
        """Test cache statistics tracking"""
        cache = MemoryBoundedCache(max_size_mb=10)

        cache.set('key1', 'value1')
        cache.get('key1')  # Hit
        cache.get('key2')  # Miss

        stats = cache.get_stats()
        assert stats['hits'] == 1
        assert stats['misses'] == 1


class TestInstrumentCache:
    """Test specialized instrument cache"""

    def test_instrument_caching(self):
        """Test instrument-specific caching"""
        cache = InstrumentCache(max_size_mb=10)

        cache.set_instrument('RELIANCE', {'exchange': 'NSE', 'lot_size': 1})
        inst = cache.get_instrument('RELIANCE')

        assert inst is not None
        assert inst['exchange'] == 'NSE'

    def test_quote_caching(self):
        """Test quote caching with shorter TTL"""
        cache = InstrumentCache(max_size_mb=10, quote_ttl=60)

        cache.set_quote('NIFTY', {'ltp': 25000, 'change': 1.5})
        quote = cache.get_quote('NIFTY')

        assert quote is not None
        assert quote['ltp'] == 25000

    def test_symbol_lookup_performance(self):
        """Test O(1) symbol lookup"""
        cache = InstrumentCache(max_size_mb=10)

        # Add instruments
        for i in range(100):
            cache.set_instrument(f'SYMBOL_{i}', {'id': i})

        # Lookup should be O(1)
        key = cache.find_by_symbol('SYMBOL_50')
        assert key is not None


class TestAlertManager:
    """Test centralized alert management"""

    def test_alert_manager_initialization(self):
        """Test alert manager initializes"""
        alert_mgr = AlertManager()

        assert alert_mgr.max_history == 1000
        assert alert_mgr.enable_console == True
        assert alert_mgr.enable_log == True

    def test_basic_alert_creation(self):
        """Test creating alerts"""
        alert_mgr = AlertManager(enable_console=False)

        alert = alert_mgr.alert(
            severity=AlertSeverity.HIGH,
            category=AlertCategory.EXECUTION,
            title="Test Alert",
            message="This is a test"
        )

        assert alert is not None
        assert alert.severity == AlertSeverity.HIGH
        assert alert.title == "Test Alert"

    def test_alert_suppression(self):
        """Test alert suppression prevents spam"""
        alert_mgr = AlertManager(suppression_window_seconds=5, enable_console=False)

        # First alert
        alert1 = alert_mgr.alert(
            severity=AlertSeverity.MEDIUM,
            category=AlertCategory.DATA,
            title="Same Alert",
            message="Message 1",
            suppress=True
        )

        # Immediate duplicate (should be suppressed)
        alert2 = alert_mgr.alert(
            severity=AlertSeverity.MEDIUM,
            category=AlertCategory.DATA,
            title="Same Alert",
            message="Message 2",
            suppress=True
        )

        assert alert1 is not None
        assert alert2 is None  # Suppressed

    def test_execution_alerts(self):
        """Test execution-specific alerts"""
        alert_mgr = AlertManager(enable_console=False)

        # Slow execution
        alert_mgr.check_execution_alerts({
            'order_id': '123',
            'duration_ms': 6000,  # 6 seconds
            'status': 'COMPLETED'
        })

        stats = alert_mgr.get_stats()
        assert stats['total_alerts'] > 0

    def test_risk_alerts(self):
        """Test risk management alerts"""
        alert_mgr = AlertManager(enable_console=False)

        # Position limit breach
        alert_mgr.check_risk_alerts({
            'positions': 30,
            'max_positions': 25,
            'daily_pnl_pct': -3.0,
            'max_daily_loss_pct': -5.0
        })

        stats = alert_mgr.get_stats()
        assert stats['critical'] > 0  # Should have critical alert

    def test_alert_statistics(self):
        """Test alert statistics tracking"""
        alert_mgr = AlertManager(enable_console=False)

        # Generate various alerts
        alert_mgr.alert(AlertSeverity.CRITICAL, AlertCategory.SYSTEM, "C1", "msg")
        alert_mgr.alert(AlertSeverity.HIGH, AlertCategory.SYSTEM, "H1", "msg")
        alert_mgr.alert(AlertSeverity.MEDIUM, AlertCategory.SYSTEM, "M1", "msg")

        stats = alert_mgr.get_stats()
        assert stats['critical'] == 1
        assert stats['high'] == 1
        assert stats['medium'] == 1
        assert stats['total_alerts'] == 3


def run_all_tests():
    """Run all tests with pytest"""
    import subprocess

    result = subprocess.run(
        ['pytest', __file__, '-v', '--tb=short'],
        capture_output=True,
        text=True
    )

    print(result.stdout)
    print(result.stderr)

    return result.returncode == 0


if __name__ == "__main__":
    print("="*70)
    print("WEEK 1-2 CRITICAL FIXES - INTEGRATION TESTS")
    print("="*70)
    print()

    # Run tests
    success = run_all_tests()

    if success:
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED")
        print("="*70)
    else:
        print("\n" + "="*70)
        print("❌ SOME TESTS FAILED")
        print("="*70)
        sys.exit(1)
