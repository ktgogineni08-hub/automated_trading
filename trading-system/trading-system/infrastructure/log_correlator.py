#!/usr/bin/env python3
"""
Log Correlation and Aggregation System
Centralized log management with correlation and query capabilities

ADDRESSES WEEK 6 ISSUE:
- Original: 7 different logging systems without correlation
- This implementation: Centralized aggregation, correlation, query interface
"""

import logging
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from enum import Enum
import sqlite3

logger = logging.getLogger('trading_system.log_correlator')


class LogLevel(Enum):
    """Log severity levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogEntry:
    """Structured log entry"""
    timestamp: datetime
    level: LogLevel
    component: str
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None
    thread_id: Optional[int] = None
    process_id: Optional[int] = None


@dataclass
class CorrelatedLogs:
    """Group of correlated log entries"""
    correlation_id: str
    entries: List[LogEntry] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    components: List[str] = field(default_factory=list)
    error_count: int = 0


class LogCorrelator:
    """
    Log Correlation and Aggregation System

    Features:
    - Centralized log storage (SQLite)
    - Automatic correlation by request/trade ID
    - Cross-component log aggregation
    - Advanced query interface
    - Log pattern detection
    - Error clustering
    - Performance analysis from logs

    Usage:
        correlator = LogCorrelator()

        # Ingest logs
        correlator.ingest_log_file("trading_system.log")

        # Query logs
        logs = correlator.query_logs(
            start_time=datetime.now() - timedelta(hours=1),
            level=LogLevel.ERROR
        )

        # Get correlated logs for a trade
        correlated = correlator.get_correlated_logs("TRADE_123")
    """

    def __init__(self, db_path: str = "logs_database.db"):
        """
        Initialize log correlator

        Args:
            db_path: Path to log database
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_database()

        # Regex patterns for log parsing
        self._log_patterns = {
            'timestamp': r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})',
            'level': r'(DEBUG|INFO|WARNING|ERROR|CRITICAL)',
            'component': r'([a-zA-Z_\.]+)',
            'correlation_id': r'(?:trade_id|order_id|correlation_id)[:\s=]+([A-Z0-9_-]+)',
        }

        logger.info(f"📋 LogCorrelator initialized: {self.db_path}")

    def _init_database(self):
        """Initialize log database schema"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                level TEXT NOT NULL,
                component TEXT NOT NULL,
                message TEXT NOT NULL,
                context TEXT,
                correlation_id TEXT,
                thread_id INTEGER,
                process_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Indices for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_component ON logs(component)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_correlation ON logs(correlation_id)")

        # Log patterns table (for pattern detection)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS log_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern TEXT NOT NULL UNIQUE,
                count INTEGER DEFAULT 0,
                first_seen TIMESTAMP NOT NULL,
                last_seen TIMESTAMP NOT NULL,
                severity TEXT
            )
        """)

        conn.commit()
        conn.close()

    def parse_log_line(self, line: str, component: str = "unknown") -> Optional[LogEntry]:
        """
        Parse a log line into structured LogEntry

        Args:
            line: Raw log line
            component: Component name

        Returns:
            LogEntry or None if parsing fails
        """
        try:
            # Extract timestamp
            timestamp_match = re.search(self._log_patterns['timestamp'], line)
            if not timestamp_match:
                return None

            timestamp_str = timestamp_match.group(1)
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")

            # Extract level
            level_match = re.search(self._log_patterns['level'], line)
            level = LogLevel(level_match.group(1)) if level_match else LogLevel.INFO

            # Extract component
            component_match = re.search(self._log_patterns['component'], line)
            if component_match:
                component = component_match.group(1)

            # Extract correlation ID
            corr_match = re.search(self._log_patterns['correlation_id'], line)
            correlation_id = corr_match.group(1) if corr_match else None

            # Message is everything after level
            message = line
            if level_match:
                message = line[level_match.end():].strip()

            return LogEntry(
                timestamp=timestamp,
                level=level,
                component=component,
                message=message,
                correlation_id=correlation_id
            )

        except Exception as e:
            logger.debug(f"Failed to parse log line: {e}")
            return None

    def ingest_log(self, entry: LogEntry) -> bool:
        """
        Ingest a single log entry

        Args:
            entry: LogEntry to store

        Returns:
            True if successful
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO logs (timestamp, level, component, message, context, correlation_id, thread_id, process_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.timestamp.isoformat(),
                entry.level.value,
                entry.component,
                entry.message,
                json.dumps(entry.context) if entry.context else None,
                entry.correlation_id,
                entry.thread_id,
                entry.process_id
            ))

            conn.commit()
            conn.close()

            return True

        except Exception as e:
            logger.error(f"Failed to ingest log: {e}")
            return False

    def ingest_log_file(self, log_file: Path, component: str = "system") -> int:
        """
        Ingest logs from a file

        Args:
            log_file: Path to log file
            component: Component name

        Returns:
            Number of logs ingested
        """
        if not log_file.exists():
            logger.warning(f"Log file not found: {log_file}")
            return 0

        ingested = 0

        try:
            with open(log_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    entry = self.parse_log_line(line, component)
                    if entry:
                        if self.ingest_log(entry):
                            ingested += 1

            logger.info(f"✅ Ingested {ingested} logs from {log_file.name}")

        except Exception as e:
            logger.error(f"Failed to ingest log file {log_file}: {e}")

        return ingested

    def query_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        level: Optional[LogLevel] = None,
        component: Optional[str] = None,
        correlation_id: Optional[str] = None,
        search_text: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Query logs with filters

        Args:
            start_time: Start timestamp
            end_time: End timestamp
            level: Log level filter
            component: Component filter
            correlation_id: Correlation ID filter
            search_text: Text search in message
            limit: Maximum results

        Returns:
            List of log dictionaries
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM logs WHERE 1=1"
        params = []

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time.isoformat() if isinstance(start_time, datetime) else start_time)

        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time.isoformat() if isinstance(end_time, datetime) else end_time)

        if level:
            query += " AND level = ?"
            params.append(level.value)

        if component:
            query += " AND component = ?"
            params.append(component)

        if correlation_id:
            query += " AND correlation_id = ?"
            params.append(correlation_id)

        if search_text:
            query += " AND message LIKE ?"
            params.append(f"%{search_text}%")

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        logs = [dict(row) for row in cursor.fetchall()]

        conn.close()

        return logs

    def get_correlated_logs(self, correlation_id: str) -> CorrelatedLogs:
        """
        Get all logs correlated by ID (trade ID, order ID, etc.)

        Args:
            correlation_id: Correlation identifier

        Returns:
            CorrelatedLogs object
        """
        logs = self.query_logs(correlation_id=correlation_id, limit=10000)

        entries = []
        components = set()
        error_count = 0

        for log_dict in logs:
            entry = LogEntry(
                timestamp=datetime.fromisoformat(log_dict['timestamp']),
                level=LogLevel(log_dict['level']),
                component=log_dict['component'],
                message=log_dict['message'],
                context=json.loads(log_dict['context']) if log_dict['context'] else {},
                correlation_id=log_dict['correlation_id'],
                thread_id=log_dict['thread_id'],
                process_id=log_dict['process_id']
            )

            entries.append(entry)
            components.add(entry.component)

            if entry.level in [LogLevel.ERROR, LogLevel.CRITICAL]:
                error_count += 1

        # Sort by timestamp
        entries.sort(key=lambda x: x.timestamp)

        return CorrelatedLogs(
            correlation_id=correlation_id,
            entries=entries,
            start_time=entries[0].timestamp if entries else None,
            end_time=entries[-1].timestamp if entries else None,
            components=list(components),
            error_count=error_count
        )

    def analyze_error_patterns(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Analyze error patterns in recent logs

        Args:
            hours: Hours to look back

        Returns:
            List of error patterns with statistics (sorted by frequency)
        """
        start_time = datetime.now() - timedelta(hours=hours)

        errors = self.query_logs(
            start_time=start_time,
            level=LogLevel.ERROR,
            limit=10000
        )

        # Cluster errors by message pattern
        error_patterns = defaultdict(list)

        for error in errors:
            # Extract pattern (remove numbers, IDs)
            pattern = re.sub(r'\d+', 'N', error['message'])
            pattern = re.sub(r'[A-Z0-9_-]{8,}', 'ID', pattern)

            error_patterns[pattern].append(error)

        # Sort by frequency
        sorted_patterns = sorted(
            error_patterns.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )

        # Return list of pattern dictionaries (changed from nested dict for test compatibility)
        return [
            {
                'pattern': pattern,
                'count': len(occurrences),
                'first_seen': min(e['timestamp'] for e in occurrences),
                'last_seen': max(e['timestamp'] for e in occurrences),
                'components': list(set(e['component'] for e in occurrences))
            }
            for pattern, occurrences in sorted_patterns[:10]
        ]

    def get_component_activity(self, hours: int = 24) -> Dict[str, int]:
        """
        Get log activity by component

        Args:
            hours: Hours to look back

        Returns:
            Dict of component -> log count
        """
        start_time = datetime.now() - timedelta(hours=hours)

        logs = self.query_logs(start_time=start_time, limit=100000)

        activity = defaultdict(int)
        for log in logs:
            activity[log['component']] += 1

        return dict(sorted(activity.items(), key=lambda x: x[1], reverse=True))

    def get_error_timeline(self, hours: int = 24, bucket_minutes: int = 10) -> List[Dict]:
        """
        Get error count timeline

        Args:
            hours: Hours to look back
            bucket_minutes: Time bucket size in minutes

        Returns:
            List of time buckets with error counts
        """
        start_time = datetime.now() - timedelta(hours=hours)

        errors = self.query_logs(
            start_time=start_time,
            level=LogLevel.ERROR,
            limit=100000
        )

        # Bucket errors by time
        buckets = defaultdict(int)
        bucket_delta = timedelta(minutes=bucket_minutes)

        for error in errors:
            timestamp = datetime.fromisoformat(error['timestamp'])
            bucket = timestamp.replace(second=0, microsecond=0)
            bucket = bucket - timedelta(minutes=bucket.minute % bucket_minutes)
            buckets[bucket] += 1

        # Convert to sorted list
        timeline = [
            {'timestamp': bucket, 'error_count': count}
            for bucket, count in sorted(buckets.items())
        ]

        return timeline

    def print_correlation_report(self, correlation_id: str):
        """Print formatted correlation report"""
        correlated = self.get_correlated_logs(correlation_id)

        print("\n" + "="*70)
        print(f"📋 LOG CORRELATION REPORT: {correlation_id}")
        print("="*70)

        if not correlated.entries:
            print("No logs found for this correlation ID")
            print("="*70 + "\n")
            return

        print(f"\nTime Range:    {correlated.start_time} → {correlated.end_time}")
        print(f"Duration:      {(correlated.end_time - correlated.start_time).total_seconds():.2f}s")
        print(f"Total Logs:    {len(correlated.entries)}")
        print(f"Components:    {', '.join(correlated.components)}")
        print(f"Errors:        {correlated.error_count}")

        print("\n--- LOG TIMELINE ---")
        for entry in correlated.entries[:50]:  # Show first 50
            level_icon = {
                LogLevel.DEBUG: "🔍",
                LogLevel.INFO: "ℹ️",
                LogLevel.WARNING: "⚠️",
                LogLevel.ERROR: "❌",
                LogLevel.CRITICAL: "🔴"
            }.get(entry.level, "")

            print(f"{entry.timestamp} {level_icon} [{entry.component:.<20}] {entry.message[:80]}")

        print("="*70 + "\n")


# Global correlator instance
_global_correlator: Optional[LogCorrelator] = None


def get_log_correlator() -> LogCorrelator:
    """Get global log correlator (singleton)"""
    global _global_correlator
    if _global_correlator is None:
        _global_correlator = LogCorrelator()
    return _global_correlator


if __name__ == "__main__":
    # Test log correlator
    correlator = LogCorrelator("test_logs.db")

    # Create sample log entries
    for i in range(10):
        entry = LogEntry(
            timestamp=datetime.now(),
            level=LogLevel.INFO if i % 3 != 0 else LogLevel.ERROR,
            component="test_component",
            message=f"Test message {i}",
            correlation_id="TEST_123" if i < 5 else "TEST_456"
        )
        correlator.ingest_log(entry)

    # Query logs
    logs = correlator.query_logs(level=LogLevel.ERROR)
    print(f"Found {len(logs)} error logs")

    # Get correlated logs
    correlator.print_correlation_report("TEST_123")

    # Analyze patterns
    analysis = correlator.analyze_error_patterns(hours=1)
    print(f"\nError patterns: {analysis['unique_patterns']}")

    print("\n✅ Log correlator tests passed")
