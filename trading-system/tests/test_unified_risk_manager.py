import unittest
from unittest.mock import MagicMock
import sys

# Mock kiteconnect
sys.modules['kiteconnect'] = MagicMock()

# Mock cryptography
cryptography = MagicMock()
sys.modules['cryptography'] = cryptography
sys.modules['cryptography.fernet'] = MagicMock()
sys.modules['cryptography.hazmat'] = MagicMock()
sys.modules['cryptography.hazmat.primitives'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.hashes'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.kdf'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.kdf.pbkdf2'] = MagicMock()
sys.modules['cryptography.hazmat.backends'] = MagicMock()

# Mock yaml
sys.modules['yaml'] = MagicMock()

# Mock holidays
sys.modules['holidays'] = MagicMock()

from core.unified_risk_manager import UnifiedRiskManager, VolatilityRegime

class TestUnifiedRiskManager(unittest.TestCase):
    def setUp(self):
        self.rm = UnifiedRiskManager(
            total_capital=1000000,
            risk_per_trade_pct=0.01,
            max_sector_exposure_pct=0.30,
            max_correlation_exposure_pct=0.40
        )

    def test_1_percent_rule(self):
        # Entry 100, Stop 90, Risk 10 per share.
        # Max loss = 10,000.
        # Max shares = 1000.
        # Lot size 1.
        lots = self.rm.calculate_position_size(100, 90, 1)
        self.assertEqual(lots, 1000)

    def test_volatility_adjustment(self):
        # High volatility -> 0.6 multiplier
        lots = self.rm.calculate_position_size(100, 90, 1, VolatilityRegime.HIGH)
        self.assertEqual(lots, 600)

    def test_rrr_validation(self):
        # Risk 10, Reward 15 -> RRR 1.5 (Valid)
        valid, rrr, _ = self.rm.validate_risk_reward_ratio(100, 90, 115)
        self.assertTrue(valid)
        self.assertAlmostEqual(rrr, 1.5)

        # Risk 10, Reward 10 -> RRR 1.0 (Invalid)
        valid, rrr, _ = self.rm.validate_risk_reward_ratio(100, 90, 110)
        self.assertFalse(valid)

    def test_sector_limits(self):
        # HDFCBANK is Banking. Limit 30% (300,000)
        existing = {'HDFCBANK': 250000} # 25%
        
        # Add 60,000 more Banking (ICICIBANK) -> Total 310,000 (31%) -> Fail
        ok, msg = self.rm.check_sector_limits('ICICIBANK', 60000, existing)
        self.assertFalse(ok)
        self.assertIn("Sector limit exceeded", msg)

        # Add 40,000 more Banking -> Total 290,000 (29%) -> Pass
        ok, msg = self.rm.check_sector_limits('ICICIBANK', 40000, existing)
        self.assertTrue(ok)

    def test_correlation_limits(self):
        # HDFCBANK and ICICIBANK are correlated (0.85)
        # Limit 40% (400,000) combined
        existing = {'HDFCBANK': 350000} # 35%
        
        # Add 60,000 ICICIBANK -> Total 410,000 (41%) -> Fail
        ok, msg = self.rm.check_correlation_limits('ICICIBANK', 60000, existing)
        self.assertFalse(ok)
        self.assertIn("Correlation limit exceeded", msg)

    def test_assess_trade_viability(self):
        existing = {'HDFCBANK': 100000}
        profile = self.rm.assess_trade_viability(
            symbol='INFY', # IT, not correlated with Banking
            entry_price=1000,
            stop_loss=900, # Risk 100. Risk/Lot = 1000. Lots = 10. Value = 100k.
            take_profit=1200, # Reward 200, RRR 2.0
            lot_size=10,
            existing_positions=existing
        )
        self.assertTrue(profile.is_valid, f"Rejection reason: {profile.rejection_reason}")
        self.assertEqual(profile.max_lots_allowed, 10)

if __name__ == '__main__':
    unittest.main()
