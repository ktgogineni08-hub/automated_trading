#!/usr/bin/env python3
"""
Comprehensive tests for realtime_data_pipeline.py module
Tests WebSocket pipeline, tick data, order books, and latency tracking
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock websockets module before importing
sys.modules['websockets'] = MagicMock()
sys.modules['websockets.exceptions'] = MagicMock()

from core.realtime_data_pipeline import (
    ConnectionState,
    TickData,
    OrderBookUpdate,
    LatencyStats,
    RealtimeDataPipeline
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection"""
    ws = AsyncMock()
    ws.send = AsyncMock()
    ws.close = AsyncMock()
    ws.ping = AsyncMock()
    return ws


@pytest.fixture
def pipeline():
    """Create RealtimeDataPipeline instance with metrics disabled"""
    with patch('core.realtime_data_pipeline.get_global_tracker', return_value=None):
        with patch('core.realtime_data_pipeline.get_global_metrics', return_value=None):
            return RealtimeDataPipeline(
                ws_url="wss://test.example.com/ws",
                reconnect_delay=1.0,
                max_reconnect_attempts=3,
                enable_metrics=False
            )


# ============================================================================
# ConnectionState Enum Tests
# ============================================================================

class TestConnectionState:
    """Test ConnectionState enum"""

    def test_connection_states(self):
        """Test all connection states"""
        assert ConnectionState.DISCONNECTED.value == "disconnected"
        assert ConnectionState.CONNECTING.value == "connecting"
        assert ConnectionState.CONNECTED.value == "connected"
        assert ConnectionState.RECONNECTING.value == "reconnecting"
        assert ConnectionState.ERROR.value == "error"


# ============================================================================
# TickData Tests
# ============================================================================

class TestTickData:
    """Test TickData dataclass"""

    def test_tick_data_creation(self):
        """Test creating tick data"""
        now = datetime.now()
        tick = TickData(
            symbol="NSE:RELIANCE",
            timestamp=now,
            last_price=2450.75,
            volume=1000000
        )

        assert tick.symbol == "NSE:RELIANCE"
        assert tick.last_price == 2450.75
        assert tick.volume == 1000000

    def test_latency_ms_calculation(self):
        """Test latency calculation"""
        exchange_time = datetime(2025, 1, 1, 10, 0, 0)
        received_time = datetime(2025, 1, 1, 10, 0, 0, 150000)  # 150ms later

        tick = TickData(
            symbol="NSE:RELIANCE",
            timestamp=exchange_time,
            last_price=2450.75,
            volume=1000000,
            exchange_timestamp=exchange_time,
            received_timestamp=received_time
        )

        latency = tick.latency_ms()
        assert latency == 150.0

    def test_latency_ms_no_timestamps(self):
        """Test latency is None when timestamps missing"""
        tick = TickData(
            symbol="NSE:RELIANCE",
            timestamp=datetime.now(),
            last_price=2450.75,
            volume=1000000
        )

        assert tick.latency_ms() is None

    def test_to_dict_conversion(self):
        """Test converting tick to dictionary"""
        now = datetime.now()
        tick = TickData(
            symbol="NSE:RELIANCE",
            timestamp=now,
            last_price=2450.75,
            volume=1000000,
            bid_price=2450.50,
            ask_price=2451.00
        )

        data = tick.to_dict()

        assert data["symbol"] == "NSE:RELIANCE"
        assert data["last_price"] == 2450.75
        assert data["volume"] == 1000000
        assert data["bid_price"] == 2450.50
        assert data["timestamp"] == now.isoformat()

    def test_to_dict_with_full_timestamps(self):
        """Test to_dict with exchange and received timestamps"""
        now = datetime.now()
        exchange_time = now - timedelta(milliseconds=10)

        tick = TickData(
            symbol="NSE:RELIANCE",
            timestamp=now,
            last_price=2450.75,
            volume=1000000,
            exchange_timestamp=exchange_time,
            received_timestamp=now
        )

        data = tick.to_dict()

        assert "exchange_timestamp" in data
        assert "received_timestamp" in data
        assert data["exchange_timestamp"] == exchange_time.isoformat()


# ============================================================================
# OrderBookUpdate Tests
# ============================================================================

class TestOrderBookUpdate:
    """Test OrderBookUpdate dataclass"""

    def test_order_book_creation(self):
        """Test creating order book update"""
        now = datetime.now()
        order_book = OrderBookUpdate(
            symbol="NSE:RELIANCE",
            timestamp=now,
            bids=[(2450.50, 500), (2450.25, 300)],
            asks=[(2451.00, 750), (2451.25, 400)]
        )

        assert order_book.symbol == "NSE:RELIANCE"
        assert len(order_book.bids) == 2
        assert len(order_book.asks) == 2

    def test_spread_calculation(self):
        """Test bid-ask spread calculation"""
        order_book = OrderBookUpdate(
            symbol="NSE:RELIANCE",
            timestamp=datetime.now(),
            bids=[(2450.50, 500), (2450.25, 300)],
            asks=[(2451.00, 750), (2451.25, 400)]
        )

        spread = order_book.spread()
        assert spread == 0.50  # 2451.00 - 2450.50

    def test_spread_empty_book(self):
        """Test spread is None for empty book"""
        order_book = OrderBookUpdate(
            symbol="NSE:RELIANCE",
            timestamp=datetime.now(),
            bids=[],
            asks=[]
        )

        assert order_book.spread() is None

    def test_mid_price_calculation(self):
        """Test mid-market price calculation"""
        order_book = OrderBookUpdate(
            symbol="NSE:RELIANCE",
            timestamp=datetime.now(),
            bids=[(2450.50, 500)],
            asks=[(2451.00, 750)]
        )

        mid_price = order_book.mid_price()
        assert mid_price == 2450.75  # (2450.50 + 2451.00) / 2

    def test_mid_price_empty_book(self):
        """Test mid price is None for empty book"""
        order_book = OrderBookUpdate(
            symbol="NSE:RELIANCE",
            timestamp=datetime.now(),
            bids=[],
            asks=[]
        )

        assert order_book.mid_price() is None


# ============================================================================
# LatencyStats Tests
# ============================================================================

class TestLatencyStats:
    """Test LatencyStats tracking"""

    def test_initial_stats(self):
        """Test initial latency statistics"""
        stats = LatencyStats()

        assert stats.min_latency_ms == float('inf')
        assert stats.max_latency_ms == 0.0
        assert stats.sample_count == 0

    def test_update_single_sample(self):
        """Test updating with single latency sample"""
        stats = LatencyStats()
        stats.update(10.5)

        assert stats.min_latency_ms == 10.5
        assert stats.max_latency_ms == 10.5
        assert stats.sample_count == 1

    def test_update_multiple_samples(self):
        """Test updating with multiple samples"""
        stats = LatencyStats()

        for i in range(20):
            stats.update(5.0 + i)

        assert stats.min_latency_ms == 5.0
        assert stats.max_latency_ms == 24.0
        assert stats.sample_count == 20

    def test_percentile_calculation(self):
        """Test percentile calculation after enough samples"""
        stats = LatencyStats()

        # Add 100 samples from 0 to 99
        for i in range(100):
            stats.update(float(i))

        # After 100 samples, percentiles should be calculated
        assert stats.p50_latency_ms > 0
        assert stats.p95_latency_ms > stats.p50_latency_ms
        assert stats.p99_latency_ms > stats.p95_latency_ms
        assert stats.avg_latency_ms > 0

    def test_recent_latencies_maxlen(self):
        """Test that recent_latencies deque has max length"""
        stats = LatencyStats()

        # Add 1500 samples (more than maxlen=1000)
        for i in range(1500):
            stats.update(float(i))

        # Should only keep last 1000
        assert len(stats.recent_latencies) == 1000
        assert stats.sample_count == 1500  # But total count is preserved


# ============================================================================
# Pipeline Initialization Tests
# ============================================================================

class TestPipelineInitialization:
    """Test RealtimeDataPipeline initialization"""

    def test_initialization_default_params(self):
        """Test initialization with default parameters"""
        with patch('core.realtime_data_pipeline.get_global_tracker', return_value=None):
            with patch('core.realtime_data_pipeline.get_global_metrics', return_value=None):
                pipeline = RealtimeDataPipeline(enable_metrics=False)

                assert pipeline.state == ConnectionState.DISCONNECTED
                assert pipeline.websocket is None
                assert len(pipeline.subscribed_symbols) == 0

    def test_initialization_custom_params(self):
        """Test initialization with custom parameters"""
        with patch('core.realtime_data_pipeline.get_global_tracker', return_value=None):
            with patch('core.realtime_data_pipeline.get_global_metrics', return_value=None):
                pipeline = RealtimeDataPipeline(
                    ws_url="wss://custom.example.com/ws",
                    reconnect_delay=10.0,
                    max_reconnect_attempts=5,
                    buffer_size=5000,
                    enable_metrics=False
                )

                assert pipeline.ws_url == "wss://custom.example.com/ws"
                assert pipeline.reconnect_delay == 10.0
                assert pipeline.max_reconnect_attempts == 5
                assert pipeline.tick_buffer.maxlen == 5000

    def test_initialization_with_auth(self):
        """Test initialization with authentication"""
        with patch('core.realtime_data_pipeline.get_global_tracker', return_value=None):
            with patch('core.realtime_data_pipeline.get_global_metrics', return_value=None):
                pipeline = RealtimeDataPipeline(
                    api_key="test_key",
                    access_token="test_token",
                    enable_metrics=False
                )

                assert pipeline.api_key == "test_key"
                assert pipeline.access_token == "test_token"


# ============================================================================
# Connection Tests
# ============================================================================

class TestConnection:
    """Test WebSocket connection management"""

    @pytest.mark.asyncio
    async def test_connect_already_connected(self, pipeline):
        """Test connecting when already connected"""
        pipeline.state = ConnectionState.CONNECTED

        result = await pipeline.connect()

        assert result is True

    @pytest.mark.asyncio
    async def test_disconnect_when_disconnected(self, pipeline):
        """Test disconnecting when already disconnected"""
        pipeline.state = ConnectionState.DISCONNECTED

        await pipeline.disconnect()

        assert pipeline.state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_disconnect_cancels_tasks(self, pipeline, mock_websocket):
        """Test that disconnect cancels background tasks"""
        pipeline.state = ConnectionState.CONNECTED
        pipeline.websocket = mock_websocket

        # Create mock tasks
        receive_task = Mock()
        receive_task.done.return_value = False
        receive_task.cancel = Mock()

        heartbeat_task = Mock()
        heartbeat_task.done.return_value = False
        heartbeat_task.cancel = Mock()

        pipeline.receive_task = receive_task
        pipeline.heartbeat_task = heartbeat_task

        await pipeline.disconnect()

        receive_task.cancel.assert_called_once()
        heartbeat_task.cancel.assert_called_once()
        mock_websocket.close.assert_called_once()


# ============================================================================
# Subscription Tests
# ============================================================================

class TestSubscription:
    """Test subscription management"""

    @pytest.mark.asyncio
    async def test_subscribe_not_connected(self, pipeline):
        """Test subscribing when not connected"""
        pipeline.state = ConnectionState.DISCONNECTED

        result = await pipeline.subscribe("NSE:RELIANCE")

        assert result is False

    @pytest.mark.asyncio
    async def test_subscribe_success(self, pipeline, mock_websocket):
        """Test successful subscription"""
        pipeline.state = ConnectionState.CONNECTED
        pipeline.websocket = mock_websocket

        result = await pipeline.subscribe("NSE:RELIANCE", mode="quote")

        assert result is True
        # Symbol is sanitized (colon removed)
        assert "NSERELIANCE" in pipeline.subscribed_symbols
        assert pipeline.subscription_modes["NSERELIANCE"] == "quote"
        mock_websocket.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscribe_sends_correct_message(self, pipeline, mock_websocket):
        """Test that subscribe sends correct message format"""
        pipeline.state = ConnectionState.CONNECTED
        pipeline.websocket = mock_websocket

        await pipeline.subscribe("NSE:RELIANCE", mode="full")

        call_args = mock_websocket.send.call_args[0][0]
        message = json.loads(call_args)

        assert message['a'] == 'subscribe'
        # Symbol is sanitized (colon removed)
        assert 'NSERELIANCE' in message['v']
        assert message['m'] == 'full'

    @pytest.mark.asyncio
    async def test_unsubscribe_not_connected(self, pipeline):
        """Test unsubscribing when not connected"""
        pipeline.state = ConnectionState.DISCONNECTED

        result = await pipeline.unsubscribe("NSE:RELIANCE")

        assert result is False

    @pytest.mark.asyncio
    async def test_unsubscribe_success(self, pipeline, mock_websocket):
        """Test successful unsubscription"""
        pipeline.state = ConnectionState.CONNECTED
        pipeline.websocket = mock_websocket
        pipeline.subscribed_symbols.add("NSE:RELIANCE")
        pipeline.subscription_modes["NSE:RELIANCE"] = "quote"

        result = await pipeline.unsubscribe("NSE:RELIANCE")

        assert result is True
        assert "NSE:RELIANCE" not in pipeline.subscribed_symbols
        assert "NSE:RELIANCE" not in pipeline.subscription_modes
        mock_websocket.send.assert_called_once()


# ============================================================================
# Data Processing Tests
# ============================================================================

class TestDataProcessing:
    """Test tick and order book data processing"""

    def test_process_tick_adds_to_buffer(self, pipeline):
        """Test that processing tick adds to buffer"""
        tick = TickData(
            symbol="NSE:RELIANCE",
            timestamp=datetime.now(),
            last_price=2450.75,
            volume=1000000
        )

        pipeline._process_tick(tick)

        assert len(pipeline.tick_buffer) == 1
        assert pipeline.tick_buffer[0] == tick

    def test_process_tick_updates_latency_stats(self, pipeline):
        """Test that processing tick updates latency statistics"""
        exchange_time = datetime.now() - timedelta(milliseconds=10)
        received_time = datetime.now()

        tick = TickData(
            symbol="NSE:RELIANCE",
            timestamp=exchange_time,
            last_price=2450.75,
            volume=1000000,
            exchange_timestamp=exchange_time,
            received_timestamp=received_time
        )

        pipeline._process_tick(tick)

        assert pipeline.latency_stats.sample_count > 0

    def test_process_tick_calls_callbacks(self, pipeline):
        """Test that processing tick calls registered callbacks"""
        received_ticks = []

        def tick_callback(tick: TickData):
            received_ticks.append(tick)

        pipeline.on_tick(tick_callback)

        tick = TickData(
            symbol="NSE:RELIANCE",
            timestamp=datetime.now(),
            last_price=2450.75,
            volume=1000000
        )

        pipeline._process_tick(tick)

        assert len(received_ticks) == 1
        assert received_ticks[0] == tick

    def test_process_tick_callback_error_handled(self, pipeline):
        """Test that callback errors are handled gracefully"""
        def failing_callback(tick: TickData):
            raise ValueError("Callback error")

        pipeline.on_tick(failing_callback)

        tick = TickData(
            symbol="NSE:RELIANCE",
            timestamp=datetime.now(),
            last_price=2450.75,
            volume=1000000
        )

        # Should not raise exception
        pipeline._process_tick(tick)

    def test_process_order_book_adds_to_buffer(self, pipeline):
        """Test that processing order book adds to buffer"""
        order_book = OrderBookUpdate(
            symbol="NSE:RELIANCE",
            timestamp=datetime.now(),
            bids=[(2450.50, 500)],
            asks=[(2451.00, 750)]
        )

        pipeline._process_order_book(order_book)

        assert len(pipeline.order_book_buffer) == 1
        assert pipeline.order_book_buffer[0] == order_book

    def test_process_order_book_calls_callbacks(self, pipeline):
        """Test that processing order book calls callbacks"""
        received_books = []

        def order_book_callback(book: OrderBookUpdate):
            received_books.append(book)

        pipeline.on_order_book(order_book_callback)

        order_book = OrderBookUpdate(
            symbol="NSE:RELIANCE",
            timestamp=datetime.now(),
            bids=[(2450.50, 500)],
            asks=[(2451.00, 750)]
        )

        pipeline._process_order_book(order_book)

        assert len(received_books) == 1


# ============================================================================
# Parsing Tests
# ============================================================================

class TestParsing:
    """Test data parsing methods"""

    def test_parse_json_tick_complete(self, pipeline):
        """Test parsing complete JSON tick data"""
        now = datetime.now()
        data = {
            'tradingsymbol': 'NSE:RELIANCE',
            'timestamp': now.isoformat(),
            'last_price': 2450.75,
            'volume': 1000000,
            'bid_price': 2450.50,
            'ask_price': 2451.00,
            'bid_quantity': 500,
            'ask_quantity': 750,
            'last_quantity': 100,
            'oi': 50000
        }

        tick = pipeline._parse_json_tick(data, now)

        assert tick is not None
        assert tick.symbol == 'NSE:RELIANCE'
        assert tick.last_price == 2450.75
        assert tick.volume == 1000000
        assert tick.bid_price == 2450.50
        assert tick.ask_price == 2451.00

    def test_parse_json_tick_minimal(self, pipeline):
        """Test parsing minimal JSON tick data"""
        now = datetime.now()
        data = {
            'tradingsymbol': 'NSE:RELIANCE',
            'last_price': 2450.75,
            'volume': 1000000
        }

        tick = pipeline._parse_json_tick(data, now)

        assert tick is not None
        assert tick.symbol == 'NSE:RELIANCE'
        assert tick.last_price == 2450.75
        assert tick.bid_price is None
        assert tick.ask_price is None

    def test_parse_json_tick_no_symbol(self, pipeline):
        """Test parsing tick without symbol returns None"""
        now = datetime.now()
        data = {
            'last_price': 2450.75,
            'volume': 1000000
        }

        tick = pipeline._parse_json_tick(data, now)

        assert tick is None

    def test_parse_json_tick_invalid_data(self, pipeline):
        """Test parsing invalid tick data returns None"""
        now = datetime.now()
        data = {
            'tradingsymbol': 'NSE:RELIANCE',
            'last_price': 'invalid',  # Invalid type
        }

        tick = pipeline._parse_json_tick(data, now)

        assert tick is None

    def test_parse_order_book_complete(self, pipeline):
        """Test parsing complete order book data"""
        now = datetime.now()
        data = {
            'tradingsymbol': 'NSE:RELIANCE',
            'bids': [
                {'price': 2450.50, 'quantity': 500},
                {'price': 2450.25, 'quantity': 300}
            ],
            'asks': [
                {'price': 2451.00, 'quantity': 750},
                {'price': 2451.25, 'quantity': 400}
            ]
        }

        order_book = pipeline._parse_order_book(data, now)

        assert order_book is not None
        assert order_book.symbol == 'NSE:RELIANCE'
        assert len(order_book.bids) == 2
        assert len(order_book.asks) == 2
        assert order_book.bids[0] == (2450.50, 500)

    def test_parse_order_book_no_symbol(self, pipeline):
        """Test parsing order book without symbol returns None"""
        now = datetime.now()
        data = {
            'bids': [{'price': 2450.50, 'quantity': 500}],
            'asks': [{'price': 2451.00, 'quantity': 750}]
        }

        order_book = pipeline._parse_order_book(data, now)

        assert order_book is None

    def test_parse_order_book_empty(self, pipeline):
        """Test parsing order book with empty bids/asks"""
        now = datetime.now()
        data = {
            'tradingsymbol': 'NSE:RELIANCE',
            'bids': [],
            'asks': []
        }

        order_book = pipeline._parse_order_book(data, now)

        assert order_book is not None
        assert len(order_book.bids) == 0
        assert len(order_book.asks) == 0

    def test_parse_binary_tick_returns_none(self, pipeline):
        """Test that binary tick parsing returns None (placeholder)"""
        now = datetime.now()
        binary_data = b'\x00\x01\x02\x03'

        tick = pipeline._parse_binary_tick(binary_data, now)

        # Currently returns None as placeholder
        assert tick is None


# ============================================================================
# Text Message Processing Tests
# ============================================================================

class TestTextMessageProcessing:
    """Test _process_text_message method"""

    def test_process_text_message_order_book(self, pipeline):
        """Test processing order book text message"""
        now = datetime.now()
        data = {
            'type': 'order_book',
            'tradingsymbol': 'NSE:RELIANCE',
            'bids': [{'price': 2450.50, 'quantity': 500}],
            'asks': [{'price': 2451.00, 'quantity': 750}]
        }

        pipeline._process_text_message(data, now)

        assert len(pipeline.order_book_buffer) == 1

    def test_process_text_message_tick(self, pipeline):
        """Test processing tick text message"""
        now = datetime.now()
        data = {
            'type': 'tick',
            'tradingsymbol': 'NSE:RELIANCE',
            'last_price': 2450.75,
            'volume': 1000000
        }

        pipeline._process_text_message(data, now)

        assert len(pipeline.tick_buffer) == 1

    def test_process_text_message_error(self, pipeline):
        """Test processing error text message"""
        now = datetime.now()
        data = {
            'type': 'error',
            'message': 'Test error message'
        }

        # Should log error but not crash
        pipeline._process_text_message(data, now)


# ============================================================================
# Callback Registration Tests
# ============================================================================

class TestCallbackRegistration:
    """Test callback registration methods"""

    def test_on_tick_registration(self, pipeline):
        """Test registering tick callback"""
        def callback(tick):
            pass

        pipeline.on_tick(callback)

        assert callback in pipeline.tick_callbacks

    def test_on_order_book_registration(self, pipeline):
        """Test registering order book callback"""
        def callback(book):
            pass

        pipeline.on_order_book(callback)

        assert callback in pipeline.order_book_callbacks

    def test_on_error_registration(self, pipeline):
        """Test registering error callback"""
        def callback(error):
            pass

        pipeline.on_error(callback)

        assert callback in pipeline.error_callbacks


# ============================================================================
# Status and Stats Tests
# ============================================================================

class TestStatusAndStats:
    """Test status and statistics methods"""

    def test_get_latency_stats(self, pipeline):
        """Test getting latency statistics"""
        # Add some samples
        for i in range(20):
            pipeline.latency_stats.update(5.0 + i)

        stats = pipeline.get_latency_stats()

        assert 'min_ms' in stats
        assert 'max_ms' in stats
        assert 'avg_ms' in stats
        assert 'p50_ms' in stats
        assert 'p95_ms' in stats
        assert 'p99_ms' in stats
        assert 'sample_count' in stats
        assert stats['sample_count'] == 20

    def test_get_latency_stats_no_samples(self, pipeline):
        """Test getting latency stats with no samples"""
        stats = pipeline.get_latency_stats()

        assert stats['min_ms'] == 0  # inf converted to 0
        assert stats['max_ms'] == 0
        assert stats['sample_count'] == 0

    def test_get_status(self, pipeline):
        """Test getting pipeline status"""
        pipeline.subscribed_symbols.add("NSE:RELIANCE")
        pipeline.subscribed_symbols.add("NSE:TCS")

        status = pipeline.get_status()

        assert status['state'] == ConnectionState.DISCONNECTED.value
        assert status['connected'] is False
        assert status['subscribed_symbols'] == 2
        assert 'NSE:RELIANCE' in status['symbols']
        assert 'NSE:TCS' in status['symbols']
        assert 'tick_buffer_size' in status
        assert 'latency' in status

    def test_get_status_connected(self, pipeline):
        """Test status when connected"""
        pipeline.state = ConnectionState.CONNECTED

        status = pipeline.get_status()

        assert status['connected'] is True


# ============================================================================
# Async Iterator Tests
# ============================================================================

class TestStreamTicks:
    """Test stream_ticks async iterator"""

    @pytest.mark.asyncio
    async def test_stream_ticks_yields_from_buffer(self, pipeline):
        """Test that stream_ticks yields ticks from buffer"""
        # Add tick to buffer
        tick = TickData(
            symbol="NSE:RELIANCE",
            timestamp=datetime.now(),
            last_price=2450.75,
            volume=1000000
        )
        pipeline.tick_buffer.append(tick)

        # Get one tick from stream
        async def get_one_tick():
            async for t in pipeline.stream_ticks():
                return t

        received_tick = await asyncio.wait_for(get_one_tick(), timeout=1.0)

        assert received_tick == tick


if __name__ == "__main__":
    # Run tests with: pytest test_realtime_data_pipeline.py -v
    pytest.main([__file__, "-v", "--tb=short"])
