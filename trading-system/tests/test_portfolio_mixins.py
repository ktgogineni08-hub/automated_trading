from core.portfolio.order_execution_mixin import OrderExecutionMixin
from core.portfolio.compliance_mixin import ComplianceMixin
from core.portfolio.dashboard_mixin import DashboardSyncMixin


class DummyOrderPortfolio(OrderExecutionMixin):
    def __init__(self):
        self.positions = {}
        self.trading_mode = 'paper'
        self.security_context = None
        self.market_hours_manager = type('M', (), {'can_trade': lambda self: (True, '')})()
        self.cash = 100000.0
        self.risk_per_trade_pct = 0.01
        self.atr_stop_multiplier = 1.5
        self.atr_target_multiplier = 2.0
        self.pricing_engine = type('P', (), {
            'get_realistic_execution_price': lambda self, **kwargs: {
                'execution_price': kwargs['base_price'],
                'impact_pct': 0.0
            }
        })()

    def _extract_lot_size(self, symbol):
        return None

    def validate_trade_pre_execution(self, **kwargs):
        return True, "", type('Profile', (), {'max_lots_allowed': 1, 'is_valid': True, 'risk_reward_ratio': 2.0, 'risk_per_lot': 100})()

    def calculate_transaction_costs(self, amount, trade_type, **kwargs):
        return 0.0

    def _check_margin_requirement(self, *args, **kwargs):
        return True

    def place_live_order(self, *args, **kwargs):
        return 'ORDER123'

    def _wait_for_order_completion(self, order_id, shares):
        return shares, 100.0

    def sync_positions_from_kite(self):
        pass


def test_order_execution_rejects_invalid_symbol():
    portfolio = DummyOrderPortfolio()
    assert portfolio.execute_trade('', 10, 100.0, 'buy') is None


class DummyCompliancePortfolio(ComplianceMixin):
    def __init__(self):
        self.positions = {
            'A': {'strategy': 'trend'},
            'B': {'strategy': 'mean'},
            'C': {'strategy': 'trend'},
        }


def test_should_diversify_strategy_limits_concentration():
    portfolio = DummyCompliancePortfolio()
    assert not portfolio.should_diversify_strategy('trend', max_concentration=0.5)
    assert portfolio.should_diversify_strategy('mean', max_concentration=0.5)


class DummyDashboardPortfolio(DashboardSyncMixin):
    def __init__(self, tmp_path):
        self.trading_mode = 'paper'
        self.cash = 1000.0
        self.positions = {}
        self.shared_state_file_path = tmp_path / 'shared.json'
        self.current_state_file_path = tmp_path / 'current.json'
        self._position_lock = DummyLock()
        self.dashboard = None
        self.trades_history = []
        self.portfolio_history = []

    def save_state_to_files(self, price_map=None):
        return {}

    def _make_json_serializable(self, data):
        return data

    def calculate_total_value(self, price_map=None):
        return self.cash


class DummyLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_send_dashboard_update_no_dashboard(tmp_path):
    portfolio = DummyDashboardPortfolio(tmp_path)
    assert portfolio.send_dashboard_update(price_map={}) is None
