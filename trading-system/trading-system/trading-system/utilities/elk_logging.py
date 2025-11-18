"""
Enhanced Logging for ELK Stack
Phase 4 Tier 3: Advanced Observability

Provides structured logging with JSON format for ELK Stack integration.
Supports multiple handlers: Console, File, TCP (Logstash), Elasticsearch.

Features:
- JSON structured logging
- Multiple log levels and handlers
- Automatic field enrichment
- Performance monitoring
- Error tracking with context

Author: Trading System
Date: October 22, 2025
"""

import logging
import logging.handlers
import json
import socket
import traceback
from datetime import datetime, timezone
from typing import Dict, Optional, Any
from pathlib import Path
import sys

try:
    from elasticsearch import Elasticsearch
except ImportError:
    Elasticsearch = None


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging
    
    Formats log records as JSON for easy parsing by ELK stack
    """
    
    def __init__(self, extra_fields: Optional[Dict] = None):
        """
        Initialize JSON formatter
        
        Args:
            extra_fields: Additional fields to include in all log records
        """
        super().__init__()
        self.extra_fields = extra_fields or {}
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread': record.thread,
            'thread_name': record.threadName,
        }
        
        # Add exception information if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields
        log_data.update(self.extra_fields)
        
        # Add custom fields from log record
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename', 'funcName',
                          'levelname', 'levelno', 'lineno', 'module', 'msecs',
                          'message', 'pathname', 'process', 'processName', 'relativeCreated',
                          'thread', 'threadName', 'exc_info', 'exc_text', 'stack_info']:
                log_data[key] = value
        
        return json.dumps(log_data)


class LogstashTCPHandler(logging.handlers.SocketHandler):
    """
    TCP handler for sending logs to Logstash
    
    Sends JSON-formatted logs over TCP to Logstash
    """
    
    def __init__(self, host: str = 'localhost', port: int = 5000):
        """
        Initialize Logstash TCP handler
        
        Args:
            host: Logstash host
            port: Logstash TCP port
        """
        super().__init__(host, port)
        self.formatter = JSONFormatter()
    
    def makePickle(self, record):
        """
        Format record as JSON bytes
        
        Override to send JSON instead of pickled data
        """
        message = self.formatter.format(record) + '\n'
        return message.encode('utf-8')


class ElasticsearchHandler(logging.Handler):
    """
    Direct Elasticsearch handler
    
    Sends logs directly to Elasticsearch (bypasses Logstash)
    """
    
    def __init__(
        self,
        hosts: list = None,
        index_pattern: str = 'trading-system-logs-{date}',
        extra_fields: Optional[Dict] = None
    ):
        """
        Initialize Elasticsearch handler
        
        Args:
            hosts: List of Elasticsearch hosts
            index_pattern: Index name pattern (supports {date} placeholder)
            extra_fields: Additional fields to include
        """
        super().__init__()
        
        if Elasticsearch is None:
            raise ImportError("elasticsearch package required: pip install elasticsearch")
        
        self.hosts = hosts or ['http://localhost:9200']
        self.index_pattern = index_pattern
        self.extra_fields = extra_fields or {}
        
        # Initialize Elasticsearch client
        self.es_client = Elasticsearch(self.hosts)
        self.formatter = JSONFormatter(extra_fields)
    
    def emit(self, record):
        """Send log record to Elasticsearch"""
        try:
            # Format record
            log_entry = json.loads(self.formatter.format(record))
            
            # Determine index name
            index_name = self.index_pattern.format(
                date=datetime.now(timezone.utc).strftime('%Y.%m.%d')
            )
            
            # Index document
            self.es_client.index(index=index_name, document=log_entry)
            
        except Exception as e:
            self.handleError(record)


class TradingSystemLogger:
    """
    Enhanced logger for trading system
    
    Provides structured logging with multiple handlers and formatters
    """
    
    def __init__(
        self,
        name: str = 'trading_system',
        level: int = logging.INFO,
        log_dir: str = 'logs',
        enable_elk: bool = False,
        elk_host: str = 'localhost',
        elk_port: int = 5000,
        enable_elasticsearch: bool = False,
        es_hosts: list = None,
        extra_fields: Optional[Dict] = None
    ):
        """
        Initialize trading system logger
        
        Args:
            name: Logger name
            level: Log level
            log_dir: Directory for log files
            enable_elk: Enable ELK stack integration
            elk_host: Logstash host
            elk_port: Logstash port
            enable_elasticsearch: Enable direct Elasticsearch logging
            es_hosts: Elasticsearch hosts
            extra_fields: Additional fields for all logs
        """
        self.name = name
        self.level = level
        self.log_dir = Path(log_dir)
        self.extra_fields = extra_fields or {}
        
        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.logger.handlers = []  # Clear existing handlers
        
        # Console handler (human-readable)
        self._add_console_handler()
        
        # File handler (JSON)
        self._add_file_handler()
        
        # ELK handler (TCP to Logstash)
        if enable_elk:
            self._add_elk_handler(elk_host, elk_port)
        
        # Direct Elasticsearch handler
        if enable_elasticsearch:
            self._add_elasticsearch_handler(es_hosts)
    
    def _add_console_handler(self):
        """Add console handler with colored output"""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.level)
        
        # Colored formatter for console
        console_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        console_formatter = logging.Formatter(console_format)
        console_handler.setFormatter(console_formatter)
        
        self.logger.addHandler(console_handler)
    
    def _add_file_handler(self):
        """Add rotating file handler with JSON format"""
        log_file = self.log_dir / f'{self.name}.json'
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10 MB
            backupCount=5
        )
        file_handler.setLevel(self.level)
        file_handler.setFormatter(JSONFormatter(self.extra_fields))
        
        self.logger.addHandler(file_handler)
    
    def _add_elk_handler(self, host: str, port: int):
        """Add Logstash TCP handler"""
        try:
            elk_handler = LogstashTCPHandler(host, port)
            elk_handler.setLevel(self.level)
            self.logger.addHandler(elk_handler)
            self.logger.info(f"ELK handler enabled: {host}:{port}")
        except Exception as e:
            self.logger.warning(f"Failed to add ELK handler: {e}")
    
    def _add_elasticsearch_handler(self, hosts: list):
        """Add direct Elasticsearch handler"""
        try:
            es_handler = ElasticsearchHandler(
                hosts=hosts,
                extra_fields=self.extra_fields
            )
            es_handler.setLevel(self.level)
            self.logger.addHandler(es_handler)
            self.logger.info(f"Elasticsearch handler enabled: {hosts}")
        except Exception as e:
            self.logger.warning(f"Failed to add Elasticsearch handler: {e}")
    
    def get_logger(self) -> logging.Logger:
        """Get the configured logger"""
        return self.logger
    
    # Convenience methods with additional context
    def log_trade(
        self,
        symbol: str,
        action: str,
        quantity: int,
        price: float,
        **kwargs
    ):
        """Log a trade execution"""
        self.logger.info(
            f"Trade executed: {action} {quantity} {symbol} @ ₹{price}",
            extra={
                'event_type': 'trade',
                'symbol': symbol,
                'action': action,
                'quantity': quantity,
                'price': price,
                **kwargs
            }
        )
    
    def log_performance(
        self,
        operation: str,
        latency_ms: float,
        **kwargs
    ):
        """Log performance metrics"""
        self.logger.info(
            f"Performance: {operation} took {latency_ms:.2f}ms",
            extra={
                'event_type': 'performance',
                'operation': operation,
                'latency_ms': latency_ms,
                **kwargs
            }
        )
    
    def log_pnl(
        self,
        symbol: str,
        pnl: float,
        pnl_pct: float,
        **kwargs
    ):
        """Log P&L information"""
        self.logger.info(
            f"P&L: {symbol} {pnl:+.2f} ({pnl_pct:+.2f}%)",
            extra={
                'event_type': 'pnl',
                'symbol': symbol,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                **kwargs
            }
        )
    
    def log_error(
        self,
        message: str,
        error: Exception,
        **kwargs
    ):
        """Log an error with full context"""
        self.logger.error(
            message,
            exc_info=True,
            extra={
                'event_type': 'error',
                'error_type': type(error).__name__,
                'error_message': str(error),
                **kwargs
            }
        )


# Global logger instance
_global_logger = None


def get_logger(
    name: str = 'trading_system',
    **kwargs
) -> logging.Logger:
    """
    Get or create global logger instance
    
    Args:
        name: Logger name
        **kwargs: Additional arguments for TradingSystemLogger
    
    Returns:
        Configured logger instance
    """
    global _global_logger
    
    if _global_logger is None:
        _global_logger = TradingSystemLogger(name, **kwargs)
    
    return _global_logger.get_logger()


if __name__ == "__main__":
    print("ELK Logging Module")
    print("=" * 50)
    
    # Example usage
    logger_instance = TradingSystemLogger(
        name='trading_system',
        level=logging.INFO,
        enable_elk=False,  # Set to True if Logstash is running
        extra_fields={
            'environment': 'development',
            'version': '4.0'
        }
    )
    
    logger = logger_instance.get_logger()
    
    # Test logging
    logger.info("System started")
    logger.debug("Debug message")
    logger.warning("Warning message")
    
    # Test specialized logging methods
    logger_instance.log_trade('RELIANCE', 'BUY', 10, 2500.50)
    logger_instance.log_performance('order_execution', 45.2)
    logger_instance.log_pnl('TCS', 1250.00, 2.5)
    
    # Test error logging
    try:
        raise ValueError("Test error")
    except Exception as e:
        logger_instance.log_error("Test error occurred", e)
    
    print("\n" + "=" * 50)
    print("Logging module loaded successfully!")
    print(f"Logs directory: {logger_instance.log_dir}")
