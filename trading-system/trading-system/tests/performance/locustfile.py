#!/usr/bin/env python3
"""Load Testing for Trading System using the Locust framework."""

from locust import HttpUser, task, between, events
import os
import random
import threading
from datetime import datetime

# Fail fast when API key is missing so runs don't silently degrade.
API_KEY = os.environ.get("DASHBOARD_API_KEY")
if not API_KEY:
    raise RuntimeError("DASHBOARD_API_KEY is required for authenticated load tests.")

# Allow overriding the default symbol universe via an environment variable for quick experiments.
_symbols_env = os.environ.get("LOCUST_SYMBOLS")
if _symbols_env:
    NIFTY_50_SYMBOLS = [symbol.strip() for symbol in _symbols_env.split(",") if symbol.strip()]
else:
    NIFTY_50_SYMBOLS = [
        "RELIANCE",
        "TCS",
        "HDFCBANK",
        "INFY",
        "HINDUNILVR",
        "ICICIBANK",
        "HDFC",
        "KOTAKBANK",
        "SBIN",
        "BHARTIARTL",
        "ITC",
        "AXISBANK",
        "LT",
        "ASIANPAINT",
        "MARUTI",
        "BAJFINANCE",
        "HCLTECH",
        "WIPRO",
        "TITAN",
        "ULTRACEMCO",
    ]

# Performance metrics storage guarded by a lock to protect against concurrent updates.
performance_metrics = {
    "response_times": [],
    "request_counts": {},
    "error_counts": {},
    "trade_executions": 0,
    "failed_trades": 0,
}
metrics_lock = threading.Lock()


def auth_headers(**extra):
    """Build headers with the required API key plus optional extras."""
    headers = {"X-API-Key": API_KEY}
    headers.update(extra)
    return headers


def failure_message(response, prefix: str) -> str:
    """Attach a short snippet of the response body to failure messages."""
    snippet = (response.text or "")[:200]
    return f"{prefix}: {response.status_code} {snippet}"


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Initialize test metrics when test starts."""
    print("\n" + "=" * 70)
    print("🚀 TRADING SYSTEM LOAD TEST STARTING")
    print("=" * 70)
    print(f"Target host: {environment.host}")
    print(f"Test started: {datetime.now().isoformat()}")
    print("=" * 70 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print summary metrics when test stops."""
    print("\n" + "=" * 70)
    print("📊 LOAD TEST COMPLETED - SUMMARY")
    print("=" * 70)

    stats = environment.stats

    print(f"\n📈 Request Statistics:")
    print(f"  Total Requests: {stats.total.num_requests}")
    print(f"  Failed Requests: {stats.total.num_failures}")
    print(f"  Failure Rate: {stats.total.fail_ratio * 100:.2f}%")

    print(f"\n⏱️  Response Times:")
    print(f"  Average: {stats.total.avg_response_time:.2f}ms")
    print(f"  Median: {stats.total.median_response_time:.2f}ms")
    print(f"  95th Percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")
    print(f"  99th Percentile: {stats.total.get_response_time_percentile(0.99):.2f}ms")
    print(f"  Max: {stats.total.max_response_time:.2f}ms")

    print(f"\n🔄 Request Rate:")
    print(f"  Total RPS: {stats.total.total_rps:.2f}")
    print(f"  Current RPS: {stats.total.current_rps:.2f}")

    with metrics_lock:
        trade_executions = performance_metrics["trade_executions"]
        failed_trades = performance_metrics["failed_trades"]

    print(f"\n💼 Trading Metrics:")
    print(f"  Trade Executions: {trade_executions}")
    print(f"  Failed Trades: {failed_trades}")

    print("\n" + "=" * 70 + "\n")


class TradingSystemUser(HttpUser):
    """Simulates a trading system user performing various operations."""

    # Wait time between tasks (1-3 seconds)
    wait_time = between(1, 3)

    def on_start(self):
        """Called when a user starts - perform login/setup."""
        self.user_id = f"user_{random.randint(1000, 9999)}"
        self.session_token = None
        self.active_positions = []

        # Health check on startup
        self.check_health()

    @task(10)
    def check_health(self):
        """Health check endpoint - high frequency."""
        with self.client.get("/health", headers=auth_headers(), catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(failure_message(response, "Health check failed"))

    @task(5)
    def check_readiness(self):
        """Readiness check endpoint."""
        with self.client.get("/health/ready", headers=auth_headers(), catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(failure_message(response, "Readiness check failed"))

    @task(8)
    def get_market_data(self):
        """Fetch market data for random symbols."""
        symbol = random.choice(NIFTY_50_SYMBOLS)

        with self.client.get(
            f"/api/v1/market/quote/{symbol}",
            headers=auth_headers(),
            name="/api/v1/market/quote/[symbol]",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                with metrics_lock:
                    performance_metrics["request_counts"]["market_data"] = (
                        performance_metrics["request_counts"].get("market_data", 0) + 1
                    )
            else:
                response.failure(failure_message(response, "Market data failed"))

    @task(6)
    def get_multiple_quotes(self):
        """Fetch quotes for multiple symbols."""
        symbols = random.sample(NIFTY_50_SYMBOLS, 5)

        with self.client.post(
            "/api/v1/market/quotes",
            headers=auth_headers(),
            json={"symbols": symbols},
            name="/api/v1/market/quotes",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(failure_message(response, "Multiple quotes failed"))

    @task(4)
    def get_portfolio_summary(self):
        """Fetch portfolio summary."""
        with self.client.get(
            "/api/v1/portfolio/summary",
            headers=auth_headers(**{"X-User-ID": self.user_id}),
            catch_response=True,
        ) as response:
            if response.status_code in [200, 404]:  # 404 is OK for new users
                response.success()
            else:
                response.failure(failure_message(response, "Portfolio summary failed"))

    @task(3)
    def get_active_positions(self):
        """Fetch active positions."""
        with self.client.get(
            "/api/v1/positions/active",
            headers=auth_headers(**{"X-User-ID": self.user_id}),
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    self.active_positions = data.get("positions", [])
                    response.success()
                except Exception as exc:
                    response.failure(f"Failed to parse positions: {exc}")
            else:
                response.failure(failure_message(response, "Active positions failed"))

    @task(2)
    def place_order(self):
        """Place a trading order."""
        symbol = random.choice(NIFTY_50_SYMBOLS)
        side = random.choice(["BUY", "SELL"])
        quantity = random.choice([1, 5, 10, 25, 50])

        order_data = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": "MARKET",
            "product": "MIS",  # Intraday
            "validity": "DAY",
        }

        with self.client.post(
            "/api/v1/orders/place",
            json=order_data,
            headers=auth_headers(**{"X-User-ID": self.user_id}),
            name="/api/v1/orders/place",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                with metrics_lock:
                    performance_metrics["trade_executions"] += 1
            elif response.status_code == 400:
                # Validation errors are expected in load tests
                response.success()
            else:
                response.failure(failure_message(response, "Order placement failed"))
                with metrics_lock:
                    performance_metrics["failed_trades"] += 1

    @task(3)
    def get_order_history(self):
        """Fetch order history."""
        with self.client.get(
            "/api/v1/orders/history",
            headers=auth_headers(**{"X-User-ID": self.user_id}),
            catch_response=True,
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(failure_message(response, "Order history failed"))

    @task(5)
    def get_strategy_signals(self):
        """Fetch strategy signals."""
        strategy = random.choice(
            ["moving_average", "rsi", "bollinger", "momentum", "volume_breakout"]
        )

        with self.client.get(
            f"/api/v1/strategies/{strategy}/signals",
            headers=auth_headers(),
            name="/api/v1/strategies/[strategy]/signals",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(failure_message(response, "Strategy signals failed"))

    @task(2)
    def get_risk_metrics(self):
        """Fetch risk metrics."""
        with self.client.get(
            "/api/v1/risk/metrics",
            headers=auth_headers(**{"X-User-ID": self.user_id}),
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(failure_message(response, "Risk metrics failed"))

    @task(1)
    def cancel_order(self):
        """Cancel a random order."""
        order_id = f"ORDER_{random.randint(1000, 9999)}"

        with self.client.delete(
            f"/api/v1/orders/{order_id}",
            headers=auth_headers(**{"X-User-ID": self.user_id}),
            name="/api/v1/orders/[order_id]",
            catch_response=True,
        ) as response:
            if response.status_code in [200, 404]:  # 404 is OK for non-existent orders
                response.success()
            else:
                response.failure(failure_message(response, "Order cancellation failed"))

    @task(4)
    def get_dashboard_data(self):
        """Fetch dashboard data."""
        with self.client.get(
            "/api/v1/dashboard/summary",
            headers=auth_headers(**{"X-User-ID": self.user_id}),
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(failure_message(response, "Dashboard data failed"))


class HighFrequencyTrader(HttpUser):
    """
    Simulates high-frequency trading patterns
    Lower wait time, more aggressive trading.
    """

    wait_time = between(0.1, 0.5)  # Very short wait times

    @task(20)
    def rapid_market_data(self):
        """Fetch market data rapidly."""
        symbol = random.choice(NIFTY_50_SYMBOLS[:10])  # Focus on top 10

        with self.client.get(
            f"/api/v1/market/quote/{symbol}",
            headers=auth_headers(),
            name="/api/v1/market/quote/[symbol]",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(failure_message(response, "Rapid market data failed"))

    @task(5)
    def rapid_order_placement(self):
        """Place orders rapidly."""
        symbol = random.choice(NIFTY_50_SYMBOLS[:5])

        order_data = {
            "symbol": symbol,
            "side": random.choice(["BUY", "SELL"]),
            "quantity": 1,
            "order_type": "MARKET",
            "product": "MIS",
        }

        with self.client.post(
            "/api/v1/orders/place",
            headers=auth_headers(),
            json=order_data,
            name="/api/v1/orders/place",
            catch_response=True,
        ) as response:
            if response.status_code in [200, 400]:
                response.success()
            else:
                response.failure(failure_message(response, "Rapid order failed"))


class DashboardUser(HttpUser):
    """Simulates dashboard users who mostly view data."""

    wait_time = between(2, 5)

    @task(10)
    def view_dashboard(self):
        """View main dashboard."""
        with self.client.get("/dashboard", headers=auth_headers(), catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(failure_message(response, "Dashboard view failed"))

    @task(5)
    def view_positions(self):
        """View positions page."""
        with self.client.get(
            "/dashboard/positions", headers=auth_headers(), catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(failure_message(response, "Positions view failed"))

    @task(5)
    def view_trades(self):
        """View trades page."""
        with self.client.get("/dashboard/trades", headers=auth_headers(), catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(failure_message(response, "Trades view failed"))

    @task(3)
    def view_analytics(self):
        """View analytics page."""
        with self.client.get(
            "/dashboard/analytics", headers=auth_headers(), catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(failure_message(response, "Analytics view failed"))


if __name__ == "__main__":
    print("Run with: locust -f locustfile.py --host=http://localhost:8000")
