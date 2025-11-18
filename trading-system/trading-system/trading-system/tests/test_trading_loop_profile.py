import time

from robust_trading_loop import RobustTradingLoop


class StubMarketManager:
    def should_stop_trading(self):
        return False, "market open"


class StubShutdownHandler:
    def __init__(self):
        self._stop = False

    def should_stop(self):
        return self._stop

    def trigger_stop(self):
        self._stop = True


def test_trading_loop_profiling_metrics():
    market_manager = StubMarketManager()
    shutdown_handler = StubShutdownHandler()
    loop = RobustTradingLoop(market_manager, shutdown_handler)

    def fetch_data():
        return {"price": 100}

    def execute_strategy(data):
        assert data["price"] == 100
        time.sleep(0.01)

    profile = loop.profile_iterations(fetch_data, execute_strategy, iterations=3)

    assert profile["iterations"] == 3
    assert profile["errors"] == 0
    assert profile["average_time"] >= 0.009
    assert loop.latest_profile == profile

    metrics = loop.get_iteration_metrics()
    assert metrics["sample_size"] >= 3
    assert metrics["average_duration"] >= 0.009
