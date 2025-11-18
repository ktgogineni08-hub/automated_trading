-- ==============================================================================
-- PostgreSQL Database Initialization Script
-- Enhanced NIFTY 50 Trading System
-- ==============================================================================
-- This script is automatically executed when PostgreSQL container starts
-- ==============================================================================

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- ==============================================================================
-- TRADES TABLE
-- ==============================================================================
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    trade_id VARCHAR(100) UNIQUE NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    trade_type VARCHAR(10) NOT NULL CHECK (trade_type IN ('BUY', 'SELL')),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    entry_price DECIMAL(12, 2) NOT NULL CHECK (entry_price > 0),
    exit_price DECIMAL(12, 2),
    stop_loss DECIMAL(12, 2),
    take_profit DECIMAL(12, 2),
    entry_time TIMESTAMP NOT NULL DEFAULT NOW(),
    exit_time TIMESTAMP,
    pnl DECIMAL(12, 2),
    pnl_percent DECIMAL(5, 2),
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED', 'CANCELLED')),
    strategy VARCHAR(100),
    confidence DECIMAL(3, 2),
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for trades table
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time);
CREATE INDEX IF NOT EXISTS idx_trades_created_at ON trades(created_at);

-- ==============================================================================
-- POSITIONS TABLE
-- ==============================================================================
CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    quantity INTEGER NOT NULL,
    avg_price DECIMAL(12, 2) NOT NULL,
    current_price DECIMAL(12, 2),
    pnl DECIMAL(12, 2),
    pnl_percent DECIMAL(5, 2),
    position_type VARCHAR(10) NOT NULL CHECK (position_type IN ('LONG', 'SHORT')),
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'CLOSED')),
    opened_at TIMESTAMP NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for positions table
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);

-- ==============================================================================
-- ORDERS TABLE
-- ==============================================================================
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(100) UNIQUE NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    order_type VARCHAR(20) NOT NULL CHECK (order_type IN ('MARKET', 'LIMIT', 'SL', 'SL-M')),
    transaction_type VARCHAR(10) NOT NULL CHECK (transaction_type IN ('BUY', 'SELL')),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    price DECIMAL(12, 2),
    trigger_price DECIMAL(12, 2),
    status VARCHAR(30) NOT NULL CHECK (status IN ('PENDING', 'OPEN', 'COMPLETE', 'CANCELLED', 'REJECTED')),
    status_message TEXT,
    exchange VARCHAR(10) NOT NULL,
    product VARCHAR(20) NOT NULL,
    order_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    exchange_timestamp TIMESTAMP,
    average_price DECIMAL(12, 2),
    filled_quantity INTEGER DEFAULT 0,
    pending_quantity INTEGER,
    cancelled_quantity INTEGER DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for orders table
CREATE INDEX IF NOT EXISTS idx_orders_order_id ON orders(order_id);
CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_timestamp ON orders(order_timestamp);

-- ==============================================================================
-- PORTFOLIO TABLE
-- ==============================================================================
CREATE TABLE IF NOT EXISTS portfolio (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    total_value DECIMAL(15, 2) NOT NULL,
    cash_balance DECIMAL(15, 2) NOT NULL,
    positions_value DECIMAL(15, 2) NOT NULL,
    daily_pnl DECIMAL(12, 2),
    total_pnl DECIMAL(12, 2),
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(5, 2),
    sharpe_ratio DECIMAL(5, 2),
    max_drawdown DECIMAL(12, 2),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Index for portfolio table
CREATE INDEX IF NOT EXISTS idx_portfolio_date ON portfolio(date);

-- ==============================================================================
-- ALERTS TABLE
-- ==============================================================================
CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    alert_id UUID DEFAULT uuid_generate_v4(),
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    details JSONB,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMP,
    acknowledged_by VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for alerts table
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_acknowledged ON alerts(acknowledged);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at);
CREATE INDEX IF NOT EXISTS idx_alerts_details ON alerts USING GIN (details);

-- ==============================================================================
-- API_CALLS TABLE (for quota monitoring)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS api_calls (
    id SERIAL PRIMARY KEY,
    endpoint VARCHAR(200) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INTEGER,
    response_time_ms INTEGER,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    request_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    date DATE NOT NULL DEFAULT CURRENT_DATE
);

-- Indexes for api_calls table
CREATE INDEX IF NOT EXISTS idx_api_calls_timestamp ON api_calls(request_timestamp);
CREATE INDEX IF NOT EXISTS idx_api_calls_date ON api_calls(date);
CREATE INDEX IF NOT EXISTS idx_api_calls_success ON api_calls(success);

-- ==============================================================================
-- SYSTEM_METRICS TABLE (for monitoring)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS system_metrics (
    id SERIAL PRIMARY KEY,
    metric_type VARCHAR(50) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(15, 4),
    metric_unit VARCHAR(20),
    metadata JSONB,
    collected_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for system_metrics table
CREATE INDEX IF NOT EXISTS idx_system_metrics_type ON system_metrics(metric_type);
CREATE INDEX IF NOT EXISTS idx_system_metrics_collected_at ON system_metrics(collected_at);

-- ==============================================================================
-- FUNCTIONS
-- ==============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- ==============================================================================
-- TRIGGERS
-- ==============================================================================

-- Triggers to automatically update updated_at
CREATE TRIGGER update_trades_updated_at BEFORE UPDATE ON trades
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_positions_updated_at BEFORE UPDATE ON positions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_orders_updated_at BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_portfolio_updated_at BEFORE UPDATE ON portfolio
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ==============================================================================
-- VIEWS
-- ==============================================================================

-- View for daily trading summary
CREATE OR REPLACE VIEW daily_trading_summary AS
SELECT
    DATE(entry_time) as trading_date,
    COUNT(*) as total_trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
    ROUND(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)::DECIMAL / COUNT(*) * 100, 2) as win_rate,
    SUM(pnl) as total_pnl,
    AVG(pnl) as avg_pnl,
    MAX(pnl) as max_profit,
    MIN(pnl) as max_loss
FROM trades
WHERE status = 'CLOSED' AND exit_time IS NOT NULL
GROUP BY DATE(entry_time)
ORDER BY trading_date DESC;

-- View for active positions summary
CREATE OR REPLACE VIEW active_positions_summary AS
SELECT
    symbol,
    SUM(quantity) as total_quantity,
    AVG(avg_price) as weighted_avg_price,
    SUM(pnl) as total_pnl,
    COUNT(*) as position_count
FROM positions
WHERE status = 'ACTIVE'
GROUP BY symbol;

-- ==============================================================================
-- INITIAL DATA (Optional)
-- ==============================================================================

-- Insert initial portfolio record
INSERT INTO portfolio (date, total_value, cash_balance, positions_value, total_trades)
VALUES (CURRENT_DATE, 1000000.00, 1000000.00, 0.00, 0)
ON CONFLICT (date) DO NOTHING;

-- ==============================================================================
-- CLEANUP PROCEDURES
-- ==============================================================================

-- Procedure to archive old api_calls (older than 30 days)
CREATE OR REPLACE FUNCTION archive_old_api_calls()
RETURNS void AS $$
BEGIN
    DELETE FROM api_calls WHERE request_timestamp < NOW() - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql;

-- Procedure to archive old system_metrics (older than 7 days)
CREATE OR REPLACE FUNCTION archive_old_metrics()
RETURNS void AS $$
BEGIN
    DELETE FROM system_metrics WHERE collected_at < NOW() - INTERVAL '7 days';
END;
$$ LANGUAGE plpgsql;

-- ==============================================================================
-- PERMISSIONS
-- ==============================================================================

-- Grant permissions to trading user (if not default user)
-- Note: Replace 'trading_user' with actual username if different
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO trading_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO trading_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO trading_user;

-- ==============================================================================
-- COMPLETION MESSAGE
-- ==============================================================================
DO $$
BEGIN
    RAISE NOTICE 'Database initialization completed successfully!';
    RAISE NOTICE 'Tables created: trades, positions, orders, portfolio, alerts, api_calls, system_metrics';
    RAISE NOTICE 'Views created: daily_trading_summary, active_positions_summary';
END $$;
