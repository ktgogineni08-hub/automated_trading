-- Trading System Database Schema
-- PostgreSQL 15+

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- For text search

-- =============================================================================
-- CORE TABLES
-- =============================================================================

-- Trading modes and configurations
CREATE TABLE IF NOT EXISTS trading_modes (
    mode_id SERIAL PRIMARY KEY,
    mode_name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO trading_modes (mode_name, description) VALUES
    ('paper', 'Paper trading mode for testing'),
    ('live', 'Live trading with real money'),
    ('backtest', 'Historical backtesting mode')
ON CONFLICT (mode_name) DO NOTHING;

-- Trading instruments/symbols
CREATE TABLE IF NOT EXISTS instruments (
    instrument_id SERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL UNIQUE,
    exchange VARCHAR(20) NOT NULL,
    instrument_type VARCHAR(20) NOT NULL, -- EQUITY, FUTURES, OPTIONS
    name VARCHAR(200),
    lot_size INTEGER DEFAULT 1,
    tick_size DECIMAL(10, 4) DEFAULT 0.05,
    is_active BOOLEAN DEFAULT true,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_instruments_symbol ON instruments(symbol);
CREATE INDEX idx_instruments_type ON instruments(instrument_type);
CREATE INDEX idx_instruments_active ON instruments(is_active);

-- =============================================================================
-- PORTFOLIO & POSITIONS
-- =============================================================================

-- Portfolio state
CREATE TABLE IF NOT EXISTS portfolio (
    portfolio_id SERIAL PRIMARY KEY,
    mode VARCHAR(50) NOT NULL,
    capital DECIMAL(15, 2) NOT NULL,
    available_cash DECIMAL(15, 2) NOT NULL,
    used_margin DECIMAL(15, 2) DEFAULT 0,
    total_pnl DECIMAL(15, 2) DEFAULT 0,
    realized_pnl DECIMAL(15, 2) DEFAULT 0,
    unrealized_pnl DECIMAL(15, 2) DEFAULT 0,
    snapshot_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_portfolio_mode ON portfolio(mode);
CREATE INDEX idx_portfolio_snapshot ON portfolio(snapshot_time DESC);

-- Active positions
CREATE TABLE IF NOT EXISTS positions (
    position_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL, -- BUY, SELL
    quantity INTEGER NOT NULL,
    entry_price DECIMAL(15, 4) NOT NULL,
    current_price DECIMAL(15, 4),
    stop_loss DECIMAL(15, 4),
    take_profit DECIMAL(15, 4),
    pnl DECIMAL(15, 2) DEFAULT 0,
    pnl_percentage DECIMAL(10, 4) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'OPEN', -- OPEN, CLOSED, PARTIALLY_CLOSED
    strategy VARCHAR(100),
    entry_time TIMESTAMP WITH TIME ZONE NOT NULL,
    exit_time TIMESTAMP WITH TIME ZONE,
    exit_price DECIMAL(15, 4),
    exit_reason VARCHAR(100),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_positions_symbol ON positions(symbol);
CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_entry_time ON positions(entry_time DESC);
CREATE INDEX idx_positions_strategy ON positions(strategy);

-- =============================================================================
-- ORDERS & TRADES
-- =============================================================================

-- Order book
CREATE TABLE IF NOT EXISTS orders (
    order_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position_id UUID REFERENCES positions(position_id),
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL, -- BUY, SELL
    order_type VARCHAR(20) NOT NULL, -- MARKET, LIMIT, SL, SL-M
    quantity INTEGER NOT NULL,
    price DECIMAL(15, 4),
    trigger_price DECIMAL(15, 4),
    status VARCHAR(20) NOT NULL, -- PENDING, PLACED, EXECUTED, CANCELLED, REJECTED
    exchange_order_id VARCHAR(100),
    filled_quantity INTEGER DEFAULT 0,
    average_price DECIMAL(15, 4),
    product VARCHAR(20), -- MIS, CNC, NRML
    validity VARCHAR(20) DEFAULT 'DAY',
    placed_at TIMESTAMP WITH TIME ZONE,
    executed_at TIMESTAMP WITH TIME ZONE,
    cancelled_at TIMESTAMP WITH TIME ZONE,
    rejection_reason TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_orders_symbol ON orders(symbol);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_placed_at ON orders(placed_at DESC);
CREATE INDEX idx_orders_position ON orders(position_id);

-- Trade executions
CREATE TABLE IF NOT EXISTS trades (
    trade_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID REFERENCES orders(order_id),
    position_id UUID REFERENCES positions(position_id),
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL,
    price DECIMAL(15, 4) NOT NULL,
    value DECIMAL(15, 2) NOT NULL,
    commission DECIMAL(10, 2) DEFAULT 0,
    executed_at TIMESTAMP WITH TIME ZONE NOT NULL,
    exchange_trade_id VARCHAR(100),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_trades_symbol ON trades(symbol);
CREATE INDEX idx_trades_executed_at ON trades(executed_at DESC);
CREATE INDEX idx_trades_order ON trades(order_id);
CREATE INDEX idx_trades_position ON trades(position_id);

-- =============================================================================
-- STRATEGIES & SIGNALS
-- =============================================================================

-- Trading strategies
CREATE TABLE IF NOT EXISTS strategies (
    strategy_id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(100) NOT NULL UNIQUE,
    strategy_type VARCHAR(50) NOT NULL,
    parameters JSONB,
    is_active BOOLEAN DEFAULT true,
    performance_metrics JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_strategies_active ON strategies(is_active);

-- Trading signals
CREATE TABLE IF NOT EXISTS signals (
    signal_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    strategy_id INTEGER REFERENCES strategies(strategy_id),
    symbol VARCHAR(50) NOT NULL,
    signal_type VARCHAR(20) NOT NULL, -- BUY, SELL, HOLD
    strength DECIMAL(5, 2), -- 0-100
    price DECIMAL(15, 4),
    target_price DECIMAL(15, 4),
    stop_loss DECIMAL(15, 4),
    reasoning TEXT,
    indicators JSONB,
    generated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'ACTIVE', -- ACTIVE, EXECUTED, EXPIRED, CANCELLED
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_signals_symbol ON signals(symbol);
CREATE INDEX idx_signals_status ON signals(status);
CREATE INDEX idx_signals_generated_at ON signals(generated_at DESC);
CREATE INDEX idx_signals_strategy ON signals(strategy_id);

-- =============================================================================
-- MARKET DATA
-- =============================================================================

-- Market quotes (real-time snapshots)
CREATE TABLE IF NOT EXISTS market_quotes (
    quote_id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    open DECIMAL(15, 4),
    high DECIMAL(15, 4),
    low DECIMAL(15, 4),
    close DECIMAL(15, 4),
    volume BIGINT,
    bid DECIMAL(15, 4),
    ask DECIMAL(15, 4),
    last_traded_price DECIMAL(15, 4),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_market_quotes_symbol ON market_quotes(symbol, timestamp DESC);
CREATE INDEX idx_market_quotes_timestamp ON market_quotes(timestamp DESC);

-- OHLC candles (aggregated data)
CREATE TABLE IF NOT EXISTS ohlc_data (
    ohlc_id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    timeframe VARCHAR(10) NOT NULL, -- 1m, 5m, 15m, 1h, 1d
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    open DECIMAL(15, 4) NOT NULL,
    high DECIMAL(15, 4) NOT NULL,
    low DECIMAL(15, 4) NOT NULL,
    close DECIMAL(15, 4) NOT NULL,
    volume BIGINT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, timeframe, timestamp)
);

CREATE INDEX idx_ohlc_symbol_timeframe ON ohlc_data(symbol, timeframe, timestamp DESC);
CREATE INDEX idx_ohlc_timestamp ON ohlc_data(timestamp DESC);

-- =============================================================================
-- RISK MANAGEMENT
-- =============================================================================

-- Risk limits
CREATE TABLE IF NOT EXISTS risk_limits (
    limit_id SERIAL PRIMARY KEY,
    limit_type VARCHAR(50) NOT NULL,
    limit_value DECIMAL(15, 2) NOT NULL,
    current_value DECIMAL(15, 2) DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    last_checked_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Risk events
CREATE TABLE IF NOT EXISTS risk_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL, -- LOW, MEDIUM, HIGH, CRITICAL
    description TEXT NOT NULL,
    affected_symbols VARCHAR(200)[],
    current_exposure DECIMAL(15, 2),
    limit_breached DECIMAL(15, 2),
    action_taken VARCHAR(100),
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
    resolved_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_risk_events_type ON risk_events(event_type);
CREATE INDEX idx_risk_events_severity ON risk_events(severity);
CREATE INDEX idx_risk_events_occurred_at ON risk_events(occurred_at DESC);

-- =============================================================================
-- AUDIT & LOGGING
-- =============================================================================

-- System audit log
CREATE TABLE IF NOT EXISTS audit_log (
    log_id BIGSERIAL PRIMARY KEY,
    log_level VARCHAR(20) NOT NULL, -- DEBUG, INFO, WARNING, ERROR, CRITICAL
    component VARCHAR(100) NOT NULL,
    action VARCHAR(100) NOT NULL,
    message TEXT,
    user_id VARCHAR(100),
    ip_address INET,
    request_id UUID,
    correlation_id UUID,
    execution_time_ms INTEGER,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_log_level ON audit_log(log_level);
CREATE INDEX idx_audit_log_component ON audit_log(component);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at DESC);
CREATE INDEX idx_audit_log_correlation_id ON audit_log(correlation_id);

-- Performance metrics
CREATE TABLE IF NOT EXISTS performance_metrics (
    metric_id BIGSERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(15, 4) NOT NULL,
    metric_unit VARCHAR(20),
    component VARCHAR(100),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_metrics_name ON performance_metrics(metric_name, timestamp DESC);
CREATE INDEX idx_metrics_timestamp ON performance_metrics(timestamp DESC);

-- =============================================================================
-- VIEWS
-- =============================================================================

-- Active positions view
CREATE OR REPLACE VIEW v_active_positions AS
SELECT 
    p.position_id,
    p.symbol,
    p.side,
    p.quantity,
    p.entry_price,
    p.current_price,
    p.stop_loss,
    p.take_profit,
    p.pnl,
    p.pnl_percentage,
    p.strategy,
    p.entry_time,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - p.entry_time)) / 3600 AS hours_held
FROM positions p
WHERE p.status = 'OPEN'
ORDER BY p.entry_time DESC;

-- Daily P&L summary
CREATE OR REPLACE VIEW v_daily_pnl AS
SELECT 
    DATE(executed_at) AS trade_date,
    COUNT(*) AS num_trades,
    SUM(CASE WHEN side = 'BUY' THEN value ELSE 0 END) AS buy_value,
    SUM(CASE WHEN side = 'SELL' THEN value ELSE 0 END) AS sell_value,
    SUM(commission) AS total_commission
FROM trades
GROUP BY DATE(executed_at)
ORDER BY trade_date DESC;

-- Strategy performance
CREATE OR REPLACE VIEW v_strategy_performance AS
SELECT 
    p.strategy,
    COUNT(*) AS total_positions,
    COUNT(*) FILTER (WHERE p.status = 'CLOSED' AND p.pnl > 0) AS winning_positions,
    COUNT(*) FILTER (WHERE p.status = 'CLOSED' AND p.pnl < 0) AS losing_positions,
    AVG(p.pnl) AS avg_pnl,
    SUM(p.pnl) AS total_pnl,
    MAX(p.pnl) AS best_trade,
    MIN(p.pnl) AS worst_trade
FROM positions p
WHERE p.strategy IS NOT NULL
GROUP BY p.strategy;

-- =============================================================================
-- TRIGGERS
-- =============================================================================

-- Update timestamp trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply update timestamp triggers
CREATE TRIGGER update_positions_updated_at BEFORE UPDATE ON positions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_orders_updated_at BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_strategies_updated_at BEFORE UPDATE ON strategies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- PARTITIONING (for high-volume tables)
-- =============================================================================

-- Partition market_quotes by month (optional, for production scale)
-- CREATE TABLE market_quotes_template (LIKE market_quotes INCLUDING ALL);
-- CREATE TABLE market_quotes_2025_01 PARTITION OF market_quotes
--     FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

-- =============================================================================
-- GRANTS (adjust as needed)
-- =============================================================================

-- Grant permissions to trading_app user
-- CREATE USER trading_app WITH PASSWORD 'secure_password';
-- GRANT CONNECT ON DATABASE trading_system TO trading_app;
-- GRANT USAGE ON SCHEMA public TO trading_app;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO trading_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO trading_app;

COMMENT ON DATABASE trading_system IS 'Trading System Production Database';
