#!/usr/bin/env python3
"""
Focused tests for enhanced_risk_manager.py module
Tests sector exposure, correlation limits, dynamic risk adjustment, and position sizing
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.enhanced_risk_manager import (
    RiskLevel,
    SectorExposure,
    CorrelationRisk,
    EnhancedRiskManager,
    SECTOR_MAPPING,
    HIGH_CORRELATION_PAIRS
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def risk_manager():
    """Create basic risk manager"""
    with patch('core.enhanced_risk_manager.get_config') as mock_config:
        mock_config.return_value.risk.risk_per_trade_pct = 0.02
        return EnhancedRiskManager(
            total_capital=1_000_000,
            max_sector_exposure_pct=0.30,
            max_correlation_exposure_pct=0.40
        )


@pytest.fixture
def sample_positions():
    """Sample positions for testing"""
    return {
        'RELIANCE': 50_000,
        'HDFCBANK': 40_000,
        'TCS': 30_000,
        'INFY': 25_000
    }


# ============================================================================
# Enum and Dataclass Tests
# ============================================================================

class TestRiskLevel:
    """Test RiskLevel enum"""

    def test_risk_levels(self):
        """Test risk level values"""
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.EXTREME.value == "extreme"


class TestSectorExposure:
    """Test SectorExposure dataclass"""

    def test_sector_exposure_creation(self):
        """Test creating sector exposure"""
        exposure = SectorExposure(
            sector="IT",
            total_value=100_000,
            num_positions=3,
            symbols=['TCS', 'INFY', 'WIPRO'],
            percentage_of_portfolio=10.0
        )

        assert exposure.sector == "IT"
        assert exposure.total_value == 100_000
        assert exposure.num_positions == 3
        assert len(exposure.symbols) == 3


class TestCorrelationRisk:
    """Test CorrelationRisk dataclass"""

    def test_correlation_risk_creation(self):
        """Test creating correlation risk"""
        risk = CorrelationRisk(
            symbol1="TCS",
            symbol2="INFY",
            correlation=0.90,
            combined_exposure=100_000,
            risk_level=RiskLevel.HIGH
        )

        assert risk.symbol1 == "TCS"
        assert risk.symbol2 == "INFY"
        assert risk.correlation == 0.90
        assert risk.risk_level == RiskLevel.HIGH


# ============================================================================
# EnhancedRiskManager Tests
# ============================================================================

class TestRiskManagerInit:
    """Test EnhancedRiskManager initialization"""

    def test_initialization(self, risk_manager):
        """Test basic initialization"""
        assert risk_manager.total_capital == 1_000_000
        assert risk_manager.max_sector_exposure_pct == 0.30
        assert risk_manager.max_correlation_exposure_pct == 0.40
        assert risk_manager.dynamic_risk_adjustment is True

    def test_initialization_custom_params(self):
        """Test initialization with custom parameters"""
        with patch('core.enhanced_risk_manager.get_config') as mock_config:
            mock_config.return_value.risk.risk_per_trade_pct = 0.02

            manager = EnhancedRiskManager(
                total_capital=500_000,
                max_sector_exposure_pct=0.25,
                max_correlation_exposure_pct=0.35,
                high_correlation_threshold=0.75,
                dynamic_risk_adjustment=False
            )

            assert manager.total_capital == 500_000
            assert manager.max_sector_exposure_pct == 0.25
            assert manager.max_correlation_exposure_pct == 0.35
            assert manager.high_correlation_threshold == 0.75
            assert manager.dynamic_risk_adjustment is False


class TestSectorMapping:
    """Test sector mapping and exposure"""

    def test_get_sector_known_symbols(self, risk_manager):
        """Test getting sector for known symbols"""
        assert risk_manager.get_sector('TCS') == 'IT'
        assert risk_manager.get_sector('HDFCBANK') == 'Banking'
        assert risk_manager.get_sector('RELIANCE') == 'Energy'
        assert risk_manager.get_sector('MARUTI') == 'Auto'

    def test_get_sector_unknown_symbol(self, risk_manager):
        """Test getting sector for unknown symbol"""
        assert risk_manager.get_sector('UNKNOWN_SYMBOL') == 'Other'

    def test_calculate_sector_exposure(self, risk_manager, sample_positions):
        """Test calculating sector exposure"""
        exposures = risk_manager.calculate_sector_exposure(sample_positions)

        assert 'Energy' in exposures  # RELIANCE
        assert 'Banking' in exposures  # HDFCBANK
        assert 'IT' in exposures  # TCS, INFY

        it_exposure = exposures['IT']
        assert it_exposure.total_value == 55_000  # TCS + INFY
        assert it_exposure.num_positions == 2
        assert set(it_exposure.symbols) == {'TCS', 'INFY'}

    def test_sector_exposure_empty_positions(self, risk_manager):
        """Test sector exposure with no positions"""
        exposures = risk_manager.calculate_sector_exposure({})
        assert len(exposures) == 0


class TestPositionLimits:
    """Test position and exposure limits"""

    def test_can_open_position_within_limits(self, risk_manager):
        """Test can open position when within limits"""
        can_open, reasons = risk_manager.can_open_position(
            symbol='TCS',
            value=50_000,
            existing_positions={'RELIANCE': 30_000}
        )

        assert can_open is True
        assert isinstance(reasons, list)

    def test_can_open_position_exceeds_sector_limit(self, risk_manager):
        """Test cannot open position if sector limit exceeded"""
        # Create large IT sector exposure
        existing = {
            'TCS': 100_000,
            'INFY': 100_000,
            'WIPRO': 100_000  # Total IT = 300k = 30% of 1M
        }

        can_open, reasons = risk_manager.can_open_position(
            symbol='HCLTECH',  # Another IT stock
            value=50_000,
            existing_positions=existing
        )

        assert can_open is False
        assert len(reasons) > 0

    def test_can_open_position_correlation_risk(self, risk_manager):
        """Test cannot open position if correlation risk too high"""
        # TCS and INFY are highly correlated (0.90)
        existing = {'TCS': 200_000}

        can_open, reasons = risk_manager.can_open_position(
            symbol='INFY',
            value=200_000,  # Combined = 400k = 40% of 1M
            existing_positions=existing
        )

        # Should fail due to correlation limit
        assert can_open is False
        assert len(reasons) > 0


class TestCorrelationAnalysis:
    """Test correlation analysis"""

    def test_find_correlated_positions(self, risk_manager, sample_positions):
        """Test finding correlated positions"""
        correlated = risk_manager.find_correlated_positions(sample_positions)

        # Should return list of correlated pairs
        assert isinstance(correlated, list)

    def test_check_correlation_limits(self, risk_manager):
        """Test correlation limits check"""
        # TCS and INFY are highly correlated
        positions = {'TCS': 150_000, 'INFY': 150_000}

        violations = risk_manager.check_correlation_limits(positions)

        # Should return violations list
        assert isinstance(violations, list)


class TestDynamicPositionSizing:
    """Test dynamic position sizing"""

    def test_calculate_dynamic_position_size_basic(self, risk_manager):
        """Test basic dynamic position sizing"""
        size = risk_manager.calculate_dynamic_position_size(
            symbol='RELIANCE',
            win_rate=0.60,
            avg_profit=1000,
            avg_loss=500,
            current_volatility=0.15
        )

        assert size > 0
        assert size <= risk_manager.total_capital * 0.10  # Reasonable limit

    def test_calculate_dynamic_position_size_high_volatility(self, risk_manager):
        """Test position sizing reduces with high volatility"""
        size_low_vol = risk_manager.calculate_dynamic_position_size(
            symbol='TCS',
            win_rate=0.60,
            avg_profit=1000,
            avg_loss=500,
            current_volatility=0.10  # Low volatility
        )

        size_high_vol = risk_manager.calculate_dynamic_position_size(
            symbol='TCS',
            win_rate=0.60,
            avg_profit=1000,
            avg_loss=500,
            current_volatility=0.40  # High volatility
        )

        # High volatility should reduce position size
        assert size_high_vol < size_low_vol

    def test_calculate_dynamic_position_size_negative_edge(self, risk_manager):
        """Test position sizing with negative edge returns zero"""
        size = risk_manager.calculate_dynamic_position_size(
            symbol='BADSTOCK',
            win_rate=0.40,
            avg_profit=500,
            avg_loss=1000,  # Losing strategy
            current_volatility=0.20
        )

        assert size == 0


class TestRiskMetrics:
    """Test risk metrics and calculations"""

    def test_get_risk_report(self, risk_manager, sample_positions):
        """Test getting risk report"""
        report = risk_manager.get_risk_report(sample_positions)

        assert isinstance(report, dict)
        assert 'total_exposure' in report
        assert 'num_positions' in report

    def test_print_risk_report(self, risk_manager, sample_positions):
        """Test printing risk report (should not raise)"""
        # Should not raise any errors
        risk_manager.print_risk_report(sample_positions)


class TestDynamicRiskAdjustment:
    """Test dynamic risk adjustment"""

    def test_calculate_dynamic_risk_adjustment(self, risk_manager):
        """Test dynamic risk adjustment calculation"""
        adjustment = risk_manager.calculate_dynamic_risk_adjustment(
            current_volatility=0.20
        )

        assert isinstance(adjustment, (int, float))
        assert 0 < adjustment <= 2.0  # Reasonable adjustment range


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_positions(self, risk_manager):
        """Test handling empty positions"""
        report = risk_manager.get_risk_report({})

        assert report['total_exposure'] == 0
        assert report['num_positions'] == 0

    def test_single_position(self, risk_manager):
        """Test handling single position"""
        positions = {'RELIANCE': 100_000}

        report = risk_manager.get_risk_report(positions)

        assert report['total_exposure'] == 100_000
        assert report['num_positions'] == 1

    def test_very_large_position_value(self, risk_manager):
        """Test handling very large position values"""
        can_open, reasons = risk_manager.can_open_position(
            symbol='RELIANCE',
            value=10_000_000,  # 10x capital
            existing_positions={}
        )

        # Should reject oversized position
        assert can_open is False
        assert len(reasons) > 0

    def test_zero_capital(self):
        """Test initialization with zero capital"""
        with patch('core.enhanced_risk_manager.get_config') as mock_config:
            mock_config.return_value.risk.risk_per_trade_pct = 0.02

            manager = EnhancedRiskManager(total_capital=0)

            assert manager.total_capital == 0


if __name__ == "__main__":
    # Run tests with: pytest test_enhanced_risk_manager.py -v
    pytest.main([__file__, "-v", "--tb=short"])
