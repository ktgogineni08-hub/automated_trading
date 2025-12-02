#!/usr/bin/env python3
"""
Robust Trading Loop with Error Recovery
Handles transient errors and ensures system continues running
"""

import time
import logging
import cProfile
import pstats
from collections import deque
from typing import Callable, Optional, Dict, Any
from datetime import datetime, timedelta

from trading_utils import CircuitBreaker, exponential_backoff, get_ist_now
from trading_exceptions import APIError, MarketHoursError

logger = logging.getLogger('trading_system.trading_loop')


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


class RobustTradingLoop:
    """
    Robust trading loop with error recovery

    Features:
    - Automatic retry with exponential backoff
    - Circuit breaker for persistent failures
    - Graceful degradation
    - Health monitoring
    - Automatic recovery
    """

    def __init__(
        self,
        market_manager,
        shutdown_handler,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 300.0
    ):
        """
        Initialize robust trading loop

        Args:
            market_manager: Market manager instance
            shutdown_handler: Graceful shutdown handler
            circuit_breaker_threshold: Failures before opening circuit
            circuit_breaker_timeout: Seconds before retrying after circuit open
        """
        self.market_manager = market_manager
        self.shutdown_handler = shutdown_handler

        # Circuit breakers for different subsystems
        self.api_circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_threshold,
            timeout=circuit_breaker_timeout,
            name="api"
        )

        self.data_circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_threshold,
            timeout=circuit_breaker_timeout,
            name="data_feed"
        )

        # Statistics
        self.iteration_count = 0
        self.error_count = 0
        self.last_successful_iteration = None
        self.loop_start_time = None

        # Health check
        self.last_health_check = None
        self.health_check_interval = 300  # 5 minutes

        logger.info("✅ Robust trading loop initialized")

        # Performance tracking
        self.iteration_durations: deque[float] = deque(maxlen=200)
        self.latest_profile: Optional[Dict[str, Any]] = None

    def run(
        self,
        fetch_data_func: Callable,
        execute_strategy_func: Callable,
        iteration_delay: float = 60.0
    ):
        """
        Run main trading loop with error recovery

        Args:
            fetch_data_func: Function to fetch market data
            execute_strategy_func: Function to execute trading strategy
            iteration_delay: Seconds between iterations
        """
        self.loop_start_time = get_ist_now()
        logger.info(f"🚀 Trading loop started at {self.loop_start_time.strftime('%H:%M:%S')}")

        while not self.shutdown_handler.should_stop():
            iteration_start = time.time()

            try:
                # Check market hours
                if not self._check_market_hours():
                    if self.shutdown_handler.should_stop():
                        logger.info("🛑 Shutdown requested - exiting trading loop")
                        break
                    time.sleep(60)  # Check again in 1 minute
                    continue

                # Periodic health check
                self._periodic_health_check()

                # Run iteration
                self._run_iteration(fetch_data_func, execute_strategy_func)

                # Mark successful
                self.last_successful_iteration = get_ist_now()
                self.iteration_count += 1
                work_duration = time.time() - iteration_start
                self.iteration_durations.append(work_duration)

                # Wait before next iteration
                elapsed = time.time() - iteration_start
                sleep_time = max(0, iteration_delay - elapsed)

                if sleep_time > 0:
                    logger.debug(f"💤 Sleeping {sleep_time:.1f}s until next iteration")
                    time.sleep(sleep_time)

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                break

            except MarketHoursError as e:
                logger.info(f"Market closed: {e}")
                time.sleep(300)  # Check again in 5 minutes

            except CircuitBreakerOpenError as e:
                logger.error(f"Circuit breaker open: {e}")
                time.sleep(60)  # Wait before retry

            except Exception as e:
                self.error_count += 1
                self._handle_error(e)

                # Exponential backoff on errors
                backoff_time = min(2 ** min(self.error_count, 6), 300)  # Max 5 minutes
                logger.warning(f"Waiting {backoff_time}s before retry...")
                time.sleep(backoff_time)

        # Loop ended
        self._cleanup()

    def _run_iteration(
        self,
        fetch_data_func: Callable,
        execute_strategy_func: Callable
    ):
        """
        Run single iteration with error recovery

        Args:
            fetch_data_func: Function to fetch data
            execute_strategy_func: Function to execute strategy
        """
        logger.debug(f"📊 Iteration {self.iteration_count + 1}")

        # Fetch market data with retry and circuit breaker
        market_data = self._fetch_data_with_recovery(fetch_data_func)

        if market_data is None:
            logger.warning("No market data available, skipping iteration")
            return

        # Execute strategy
        try:
            execute_strategy_func(market_data)
        except Exception as e:
            logger.error(f"Strategy execution failed: {e}", exc_info=True)
            # Don't break loop on strategy errors
            raise

    def _fetch_data_with_recovery(self, fetch_func: Callable) -> Optional[Dict]:
        """
        Fetch data with retry and circuit breaker

        Args:
            fetch_func: Function that fetches data

        Returns:
            Market data or None
        """
        try:
            # Check circuit breaker
            if self.api_circuit_breaker.state == 'OPEN':
                # Try to transition to half-open
                if (self.api_circuit_breaker.last_failure_time and
                    time.time() - self.api_circuit_breaker.last_failure_time > self.api_circuit_breaker.timeout):
                    logger.info("API circuit breaker: OPEN → HALF_OPEN (timeout expired)")
                    self.api_circuit_breaker.state = 'HALF_OPEN'
                else:
                    raise CircuitBreakerOpenError("API circuit breaker is OPEN")

            # Fetch with retry
            def _fetch_with_retry():
                try:
                    return fetch_func()
                except APIError as e:
                    if e.status_code in [429, 503]:  # Rate limit or service unavailable
                        logger.warning(f"API temporarily unavailable: {e}")
                        raise  # Will be retried
                    else:
                        logger.error(f"API error: {e}")
                        raise

            data = exponential_backoff(
                _fetch_with_retry,
                max_attempts=3,
                initial_delay=1.0,
                max_delay=10.0
            )

            # Success - reset circuit breaker
            if self.api_circuit_breaker.state == 'HALF_OPEN':
                logger.info("API circuit breaker: HALF_OPEN → CLOSED (recovery confirmed)")
                self.api_circuit_breaker.reset()
            self.api_circuit_breaker.failure_count = 0

            return data

        except Exception as e:
            # Record failure
            self.api_circuit_breaker.failure_count += 1
            self.api_circuit_breaker.last_failure_time = time.time()

            # Open circuit if threshold exceeded
            if self.api_circuit_breaker.failure_count >= self.api_circuit_breaker.failure_threshold:
                if self.api_circuit_breaker.state != 'OPEN':
                    logger.error(
                        f"API circuit breaker: {self.api_circuit_breaker.state} → OPEN "
                        f"(failures: {self.api_circuit_breaker.failure_count})"
                    )
                self.api_circuit_breaker.state = 'OPEN'
                raise CircuitBreakerOpenError(f"API circuit breaker opened after {self.api_circuit_breaker.failure_count} failures")

            raise

    def _check_market_hours(self) -> bool:
        """Check if trading is allowed"""
        try:
            should_stop, reason = self.market_manager.should_stop_trading()

            if should_stop:
                logger.info(f"Trading not allowed: {reason}")
                if hasattr(self.shutdown_handler, "request_stop") and reason in {"market_closed", "market_closed_weekend"}:
                    logger.info("🕰️ Market close detected - requesting graceful shutdown")
                    self.shutdown_handler.request_stop(reason)
                return False

            return True

        except Exception as e:
            logger.error(f"Error checking market hours: {e}")
            # Fail safe - assume market closed
            return False

    def _periodic_health_check(self):
        """Perform periodic health check"""
        now = time.time()

        if self.last_health_check is None or (now - self.last_health_check) > self.health_check_interval:
            logger.info("🏥 Health Check:")
            logger.info(f"   Uptime: {self._get_uptime()}")
            logger.info(f"   Iterations: {self.iteration_count}")
            logger.info(f"   Errors: {self.error_count}")
            logger.info(f"   Last Success: {self._format_time_ago(self.last_successful_iteration)}")
            logger.info(f"   API Circuit Breaker: {self.api_circuit_breaker.state}")

            self.last_health_check = now

    def _handle_error(self, error: Exception):
        """Handle error with appropriate logging and recovery"""
        error_type = type(error).__name__

        logger.error(
            f"❌ Error in trading loop (#{self.error_count}): {error_type}: {error}",
            exc_info=True
        )

        # Specific error handling
        if isinstance(error, APIError):
            logger.error(f"API Error: Status={error.status_code}, Response={error.response}")
        elif isinstance(error, ConnectionError):
            logger.error("Connection error - network issue or API down")
        elif isinstance(error, TimeoutError):
            logger.error("Timeout error - slow network or API response")

        # Alert on excessive errors
        if self.error_count >= 10:
            logger.critical(f"⚠️  HIGH ERROR COUNT: {self.error_count} errors!")
            logger.critical("   System may be unstable, consider manual intervention")

    def _get_uptime(self) -> str:
        """Get formatted uptime"""
        if self.loop_start_time:
            uptime = get_ist_now() - self.loop_start_time
            hours = uptime.total_seconds() / 3600
            return f"{hours:.1f}h"
        return "N/A"

    def _format_time_ago(self, dt: Optional[datetime]) -> str:
        """Format time ago"""
        if dt is None:
            return "Never"

        elapsed = get_ist_now() - dt
        seconds = elapsed.total_seconds()

        if seconds < 60:
            return f"{seconds:.0f}s ago"
        elif seconds < 3600:
            return f"{seconds/60:.0f}m ago"
        else:
            return f"{seconds/3600:.1f}h ago"

    def _cleanup(self):
        """Cleanup on loop exit"""
        logger.info("🛑 Trading loop stopped")
        logger.info(f"   Total iterations: {self.iteration_count}")
        logger.info(f"   Total errors: {self.error_count}")

    def get_iteration_metrics(self) -> Dict[str, float]:
        durations = list(self.iteration_durations)
        if not durations:
            return {
                'sample_size': 0,
                'average_duration': 0.0,
                'max_duration': 0.0,
                'min_duration': 0.0,
            }

        durations.sort()
        sample_size = len(durations)
        average = sum(durations) / sample_size
        min_duration = durations[0]
        max_duration = durations[-1]
        return {
            'sample_size': sample_size,
            'average_duration': average,
            'max_duration': max_duration,
            'min_duration': min_duration,
        }

    def profile_iterations(
        self,
        fetch_data_func: Callable,
        execute_strategy_func: Callable,
        iterations: int = 5
    ) -> Dict[str, Any]:
        """Profile a limited number of loop iterations for performance analysis."""
        profiler = cProfile.Profile()
        durations: list[float] = []
        errors = 0

        profiler.enable()
        for _ in range(max(0, iterations)):
            iteration_start = time.perf_counter()
            try:
                self._run_iteration(fetch_data_func, execute_strategy_func)
                duration = time.perf_counter() - iteration_start
                durations.append(duration)
                self.iteration_durations.append(duration)
            except Exception:
                errors += 1
        profiler.disable()

        stats = pstats.Stats(profiler)
        stats.strip_dirs().sort_stats('cumulative')
        top_entries = []
        for func, data in sorted(stats.stats.items(), key=lambda item: item[1][3], reverse=True)[:5]:
            filename, lineno, func_name = func
            cc, nc, tt, ct, callers = data
            top_entries.append({
                'function': f"{func_name} ({filename}:{lineno})",
                'cumulative_time': ct,
                'total_time': tt,
                'calls': nc,
            })

        total_time = sum(durations)
        avg_time = total_time / len(durations) if durations else 0.0

        profile_summary = {
            'iterations': iterations,
            'errors': errors,
            'total_time': total_time,
            'average_time': avg_time,
            'top_calls': top_entries,
        }

        self.latest_profile = profile_summary
        return profile_summary
        logger.info(f"   Uptime: {self._get_uptime()}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get loop statistics"""
        return {
            'iteration_count': self.iteration_count,
            'error_count': self.error_count,
            'uptime': self._get_uptime(),
            'last_successful_iteration': self.last_successful_iteration,
            'api_circuit_breaker_state': self.api_circuit_breaker.state,
            'api_failures': self.api_circuit_breaker.failure_count
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("🧪 Testing Robust Trading Loop")

    # Mock components
    class MockMarketManager:
        def should_stop_trading(self):
            return False, "market_open"

    class MockShutdownHandler:
        def __init__(self):
            self.stop_count = 0

        def should_stop(self):
            self.stop_count += 1
            return self.stop_count > 5  # Stop after 5 iterations

    mock_market = MockMarketManager()
    mock_shutdown = MockShutdownHandler()

    loop = RobustTradingLoop(mock_market, mock_shutdown)

    # Mock functions
    def mock_fetch_data():
        print("  Fetching data...")
        return {'price': 25000, 'volume': 1000}

    def mock_execute_strategy(data):
        print(f"  Executing strategy with {data}")

    # Run loop
    loop.run(mock_fetch_data, mock_execute_strategy, iteration_delay=1.0)

    print(f"\n✅ Loop completed: {loop.get_statistics()}")
