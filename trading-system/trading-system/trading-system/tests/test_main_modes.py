from types import ModuleType, SimpleNamespace
import sys

import main


def test_run_backtesting_invokes_fast_backtest(monkeypatch):
    calls = []

    class StubDataProvider:
        def __init__(self, kite=None, instruments_map=None, use_yf_fallback=True):
            self.kite = kite
            self.instruments = instruments_map or {}

    class StubTradingSystem:
        def __init__(self, data_provider, kite, initial_cash, trading_mode):
            self.data_provider = data_provider
            self.kite = kite
            self.initial_cash = initial_cash
            self.trading_mode = trading_mode
            self.portfolio = SimpleNamespace(save_state_to_files=lambda: calls.append('save'))

        def run_fast_backtest(self, interval="5minute", days=30):
            calls.append((interval, days, self.trading_mode))

    stub_module = ModuleType('data.provider')
    stub_module.DataProvider = StubDataProvider
    monkeypatch.setitem(sys.modules, 'data.provider', stub_module)
    monkeypatch.setattr(main, 'UnifiedTradingSystem', StubTradingSystem)

    main.run_backtesting(kite=None)

    assert calls == [('5minute', 30, 'backtest')]


def test_run_paper_trading_handles_keyboard_interrupt(monkeypatch):
    calls = []

    class StubDataProvider:
        def __init__(self, kite=None, instruments_map=None, use_yf_fallback=True):
            self.kite = kite
            self.instruments = instruments_map or {}

    class StubTradingSystem:
        def __init__(self, data_provider, kite, initial_cash, trading_mode):
            self.portfolio = SimpleNamespace(save_state_to_files=lambda: calls.append('saved'))

        def run_nifty50_trading(self, interval="5minute", check_interval=30):
            raise KeyboardInterrupt

    stub_module = ModuleType('data.provider')
    stub_module.DataProvider = StubDataProvider
    monkeypatch.setitem(sys.modules, 'data.provider', stub_module)
    monkeypatch.setattr(main, 'UnifiedTradingSystem', StubTradingSystem)

    main.run_paper_trading(kite=None)

    assert calls == ['saved']
