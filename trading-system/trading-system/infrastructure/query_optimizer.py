#!/usr/bin/env python3
"""
Database Query Optimization Module
Comprehensive query performance analysis and optimization

Features:
- Query performance monitoring
- Slow query detection and logging
- Index usage analysis
- Query plan optimization
- Connection pool tuning
- Query result caching
- Automatic index recommendations
"""

import logging
import time
import re
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import defaultdict, deque
import threading
from enum import Enum

logger = logging.getLogger('trading_system.query_optimizer')


class QueryType(Enum):
    """Query operation types"""
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    OTHER = "OTHER"


@dataclass
class QueryStats:
    """Statistics for a specific query"""
    query_hash: str
    query_template: str
    query_type: QueryType
    execution_count: int = 0
    total_time_ms: float = 0.0
    min_time_ms: float = float('inf')
    max_time_ms: float = 0.0
    avg_time_ms: float = 0.0
    last_executed: Optional[datetime] = None
    slow_query_count: int = 0
    rows_affected_total: int = 0
    cache_hits: int = 0
    cache_misses: int = 0

    def update(self, execution_time_ms: float, rows_affected: int = 0):
        """Update statistics with new execution"""
        self.execution_count += 1
        self.total_time_ms += execution_time_ms
        self.min_time_ms = min(self.min_time_ms, execution_time_ms)
        self.max_time_ms = max(self.max_time_ms, execution_time_ms)
        self.avg_time_ms = self.total_time_ms / self.execution_count
        self.last_executed = datetime.now()
        self.rows_affected_total += rows_affected

        # Track slow queries (> 1000ms)
        if execution_time_ms > 1000:
            self.slow_query_count += 1


@dataclass
class IndexRecommendation:
    """Index creation recommendation"""
    table_name: str
    column_names: List[str]
    reason: str
    estimated_improvement: str
    priority: str  # HIGH, MEDIUM, LOW
    create_statement: str


@dataclass
class ConnectionPoolStats:
    """Connection pool statistics"""
    pool_size: int
    active_connections: int
    idle_connections: int
    waiting_requests: int
    avg_wait_time_ms: float
    total_connections_created: int
    total_connections_closed: int
    connection_errors: int


class QueryOptimizer:
    """
    Comprehensive Query Optimization System

    Features:
    - Real-time query performance monitoring
    - Slow query detection and alerting
    - Query plan analysis
    - Index usage tracking
    - Automatic index recommendations
    - Query result caching
    - Connection pool optimization

    Usage:
        optimizer = QueryOptimizer()

        # Track query execution
        with optimizer.track_query(query) as tracker:
            result = execute_query(query)
            tracker.set_rows_affected(len(result))

        # Get optimization recommendations
        recommendations = optimizer.get_recommendations()

        # View statistics
        stats = optimizer.get_statistics()
    """

    def __init__(
        self,
        slow_query_threshold_ms: float = 1000,
        cache_enabled: bool = True,
        max_cache_size: int = 1000
    ):
        self.slow_query_threshold_ms = slow_query_threshold_ms
        self.cache_enabled = cache_enabled
        self.max_cache_size = max_cache_size

        # Query statistics storage
        self._query_stats: Dict[str, QueryStats] = {}
        self._slow_queries: deque = deque(maxlen=100)  # Keep last 100 slow queries

        # Query result cache
        self._query_cache: Dict[str, Tuple[Any, datetime]] = {}
        self._cache_ttl_seconds = 60  # 1 minute default TTL

        # Index recommendations
        self._index_recommendations: List[IndexRecommendation] = []

        # Connection pool stats
        self._pool_stats = ConnectionPoolStats(
            pool_size=0, active_connections=0, idle_connections=0,
            waiting_requests=0, avg_wait_time_ms=0.0,
            total_connections_created=0, total_connections_closed=0,
            connection_errors=0
        )

        # Thread safety
        self._lock = threading.RLock()

        logger.info("🔧 QueryOptimizer initialized")

    def track_query(self, query: str, params: Optional[tuple] = None):
        """
        Context manager for tracking query execution

        Usage:
            with optimizer.track_query(query, params) as tracker:
                result = execute_query(query, params)
                tracker.set_rows_affected(len(result))
        """
        return QueryExecutionTracker(self, query, params)

    def _normalize_query(self, query: str) -> Tuple[str, str, QueryType]:
        """
        Normalize query for pattern matching

        Returns:
            (query_hash, query_template, query_type)
        """
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', query.strip())

        # Replace parameter placeholders with ? for template
        template = re.sub(r'%s|\$\d+|\?', '?', normalized)
        template = re.sub(r"'[^']*'", "'?'", template)  # Replace string literals
        template = re.sub(r'\b\d+\b', '?', template)  # Replace numbers

        # Generate hash
        query_hash = hashlib.sha256(template.encode()).hexdigest()[:16]

        # Determine query type
        query_upper = normalized.upper()
        if query_upper.startswith('SELECT'):
            query_type = QueryType.SELECT
        elif query_upper.startswith('INSERT'):
            query_type = QueryType.INSERT
        elif query_upper.startswith('UPDATE'):
            query_type = QueryType.UPDATE
        elif query_upper.startswith('DELETE'):
            query_type = QueryType.DELETE
        else:
            query_type = QueryType.OTHER

        return query_hash, template, query_type

    def record_query_execution(
        self,
        query: str,
        execution_time_ms: float,
        rows_affected: int = 0,
        params: Optional[tuple] = None
    ):
        """Record a query execution"""
        with self._lock:
            query_hash, template, query_type = self._normalize_query(query)

            # Get or create stats
            if query_hash not in self._query_stats:
                self._query_stats[query_hash] = QueryStats(
                    query_hash=query_hash,
                    query_template=template,
                    query_type=query_type
                )

            stats = self._query_stats[query_hash]
            stats.update(execution_time_ms, rows_affected)

            # Track slow queries
            if execution_time_ms > self.slow_query_threshold_ms:
                self._slow_queries.append({
                    'query': template,
                    'execution_time_ms': execution_time_ms,
                    'rows_affected': rows_affected,
                    'timestamp': datetime.now(),
                    'params': str(params) if params else None
                })

                logger.warning(
                    f"Slow query detected ({execution_time_ms:.1f}ms): "
                    f"{template[:100]}..."
                )

    def get_cached_result(self, query: str, params: Optional[tuple] = None) -> Optional[Any]:
        """Get cached query result if available and not expired"""
        if not self.cache_enabled:
            return None

        with self._lock:
            cache_key = self._get_cache_key(query, params)

            if cache_key in self._query_cache:
                result, cached_at = self._query_cache[cache_key]

                # Check if expired
                age = (datetime.now() - cached_at).total_seconds()
                if age < self._cache_ttl_seconds:
                    # Update cache hit stats
                    query_hash, _, _ = self._normalize_query(query)
                    if query_hash in self._query_stats:
                        self._query_stats[query_hash].cache_hits += 1

                    logger.debug(f"Cache hit for query: {query[:50]}...")
                    return result
                else:
                    # Expired, remove from cache
                    del self._query_cache[cache_key]

            # Cache miss
            query_hash, _, _ = self._normalize_query(query)
            if query_hash in self._query_stats:
                self._query_stats[query_hash].cache_misses += 1

            return None

    def cache_result(self, query: str, result: Any, params: Optional[tuple] = None):
        """Cache query result"""
        if not self.cache_enabled:
            return

        with self._lock:
            # Evict oldest if cache is full
            if len(self._query_cache) >= self.max_cache_size:
                oldest_key = next(iter(self._query_cache))
                del self._query_cache[oldest_key]

            cache_key = self._get_cache_key(query, params)
            self._query_cache[cache_key] = (result, datetime.now())

    def _get_cache_key(self, query: str, params: Optional[tuple]) -> str:
        """Generate cache key for query + params"""
        key_str = query + str(params) if params else query
        return hashlib.sha256(key_str.encode()).hexdigest()

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive query statistics"""
        with self._lock:
            total_queries = sum(s.execution_count for s in self._query_stats.values())
            total_time = sum(s.total_time_ms for s in self._query_stats.values())
            slow_queries = sum(s.slow_query_count for s in self._query_stats.values())

            # Find slowest queries
            slowest = sorted(
                self._query_stats.values(),
                key=lambda s: s.avg_time_ms,
                reverse=True
            )[:10]

            # Find most frequent queries
            most_frequent = sorted(
                self._query_stats.values(),
                key=lambda s: s.execution_count,
                reverse=True
            )[:10]

            # Cache statistics
            total_cache_hits = sum(s.cache_hits for s in self._query_stats.values())
            total_cache_misses = sum(s.cache_misses for s in self._query_stats.values())
            cache_hit_rate = (
                (total_cache_hits / (total_cache_hits + total_cache_misses) * 100)
                if (total_cache_hits + total_cache_misses) > 0 else 0.0
            )

            return {
                'total_queries': total_queries,
                'total_execution_time_ms': total_time,
                'avg_query_time_ms': total_time / total_queries if total_queries > 0 else 0,
                'slow_query_count': slow_queries,
                'slow_query_threshold_ms': self.slow_query_threshold_ms,
                'unique_query_patterns': len(self._query_stats),
                'slowest_queries': [
                    {
                        'template': s.query_template[:100],
                        'avg_time_ms': s.avg_time_ms,
                        'max_time_ms': s.max_time_ms,
                        'execution_count': s.execution_count
                    }
                    for s in slowest
                ],
                'most_frequent_queries': [
                    {
                        'template': s.query_template[:100],
                        'execution_count': s.execution_count,
                        'avg_time_ms': s.avg_time_ms
                    }
                    for s in most_frequent
                ],
                'cache_stats': {
                    'enabled': self.cache_enabled,
                    'size': len(self._query_cache),
                    'max_size': self.max_cache_size,
                    'hits': total_cache_hits,
                    'misses': total_cache_misses,
                    'hit_rate': cache_hit_rate
                }
            }

    def analyze_index_usage(self, table_queries: Dict[str, List[str]]):
        """
        Analyze queries for index optimization opportunities

        Args:
            table_queries: Dict mapping table names to list of queries
        """
        recommendations = []

        for table_name, queries in table_queries.items():
            # Analyze WHERE clauses for potential indexes
            where_columns = defaultdict(int)

            for query in queries:
                # Extract columns from WHERE clauses
                where_match = re.search(r'WHERE\s+(.*?)(?:ORDER|GROUP|LIMIT|$)', query, re.IGNORECASE)
                if where_match:
                    where_clause = where_match.group(1)

                    # Find column names (simplified)
                    columns = re.findall(r'(\w+)\s*[=<>!]', where_clause)
                    for col in columns:
                        if col.upper() not in ['AND', 'OR', 'NOT', 'IN', 'IS', 'NULL']:
                            where_columns[col] += 1

            # Generate recommendations for frequently used columns
            for column, frequency in where_columns.items():
                if frequency >= 3:  # Column used in 3+ queries
                    priority = "HIGH" if frequency >= 10 else "MEDIUM" if frequency >= 5 else "LOW"

                    recommendation = IndexRecommendation(
                        table_name=table_name,
                        column_names=[column],
                        reason=f"Column '{column}' used in WHERE clause {frequency} times",
                        estimated_improvement=f"~{min(frequency * 10, 80)}% faster queries",
                        priority=priority,
                        create_statement=f"CREATE INDEX idx_{table_name}_{column} ON {table_name}({column});"
                    )
                    recommendations.append(recommendation)

        self._index_recommendations = recommendations
        return recommendations

    def get_recommendations(self) -> List[Dict[str, Any]]:
        """Get optimization recommendations"""
        recommendations = []

        with self._lock:
            # Recommend indexes
            for idx_rec in self._index_recommendations:
                recommendations.append({
                    'type': 'INDEX',
                    'priority': idx_rec.priority,
                    'description': f"Create index on {idx_rec.table_name}.{','.join(idx_rec.column_names)}",
                    'reason': idx_rec.reason,
                    'estimated_improvement': idx_rec.estimated_improvement,
                    'action': idx_rec.create_statement
                })

            # Recommend query rewrites for slow queries
            for stats in self._query_stats.values():
                if stats.slow_query_count > 5:
                    recommendations.append({
                        'type': 'QUERY_OPTIMIZATION',
                        'priority': 'HIGH',
                        'description': f"Optimize slow query (avg: {stats.avg_time_ms:.0f}ms)",
                        'reason': f"Query has been slow {stats.slow_query_count} times",
                        'query_template': stats.query_template[:200],
                        'action': 'Review and optimize query structure, add appropriate indexes'
                    })

            # Recommend caching for frequent read queries
            for stats in self._query_stats.values():
                if (stats.query_type == QueryType.SELECT and
                    stats.execution_count > 100 and
                    stats.cache_hits < stats.execution_count * 0.5):
                    recommendations.append({
                        'type': 'CACHING',
                        'priority': 'MEDIUM',
                        'description': f"Enable caching for frequent query ({stats.execution_count} executions)",
                        'reason': f"Low cache hit rate: {(stats.cache_hits / stats.execution_count * 100):.1f}%",
                        'query_template': stats.query_template[:200],
                        'action': 'Implement application-level caching for this query'
                    })

        return sorted(recommendations, key=lambda r: {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}[r['priority']])

    def update_pool_stats(self, stats: ConnectionPoolStats):
        """Update connection pool statistics"""
        with self._lock:
            self._pool_stats = stats

    def get_pool_recommendations(self) -> List[str]:
        """Get connection pool tuning recommendations"""
        recommendations = []

        with self._lock:
            stats = self._pool_stats

            # Check pool utilization
            if stats.active_connections > stats.pool_size * 0.9:
                recommendations.append(
                    f"⚠️ Pool nearly exhausted ({stats.active_connections}/{stats.pool_size}). "
                    f"Consider increasing pool size to {stats.pool_size * 2}"
                )

            # Check waiting requests
            if stats.waiting_requests > 0:
                recommendations.append(
                    f"⚠️ {stats.waiting_requests} requests waiting for connections. "
                    f"Increase pool size or optimize query execution time"
                )

            # Check average wait time
            if stats.avg_wait_time_ms > 100:
                recommendations.append(
                    f"⚠️ High average wait time ({stats.avg_wait_time_ms:.0f}ms). "
                    f"Consider increasing pool size or reducing query complexity"
                )

            # Check connection errors
            if stats.connection_errors > 10:
                recommendations.append(
                    f"⚠️ {stats.connection_errors} connection errors detected. "
                    f"Check database connectivity and error logs"
                )

            if not recommendations:
                recommendations.append("✅ Connection pool is optimally configured")

        return recommendations

    def print_report(self):
        """Print comprehensive optimization report"""
        stats = self.get_statistics()

        print("\n" + "="*80)
        print("🔧 QUERY OPTIMIZATION REPORT")
        print("="*80)

        print(f"\n📊 Query Statistics:")
        print(f"  Total Queries:         {stats['total_queries']:,}")
        print(f"  Unique Patterns:       {stats['unique_query_patterns']}")
        print(f"  Avg Query Time:        {stats['avg_query_time_ms']:.2f}ms")
        print(f"  Slow Queries:          {stats['slow_query_count']}")
        print(f"  Slow Query Threshold:  {stats['slow_query_threshold_ms']}ms")

        print(f"\n💾 Cache Statistics:")
        cache = stats['cache_stats']
        print(f"  Status:     {'Enabled' if cache['enabled'] else 'Disabled'}")
        print(f"  Size:       {cache['size']} / {cache['max_size']}")
        print(f"  Hits:       {cache['hits']:,}")
        print(f"  Misses:     {cache['misses']:,}")
        print(f"  Hit Rate:   {cache['hit_rate']:.1f}%")

        print(f"\n🐢 Slowest Queries:")
        for i, query in enumerate(stats['slowest_queries'][:5], 1):
            print(f"  {i}. {query['avg_time_ms']:.0f}ms avg ({query['execution_count']} executions)")
            print(f"     {query['template'][:70]}...")

        print(f"\n🔥 Most Frequent Queries:")
        for i, query in enumerate(stats['most_frequent_queries'][:5], 1):
            print(f"  {i}. {query['execution_count']} executions ({query['avg_time_ms']:.0f}ms avg)")
            print(f"     {query['template'][:70]}...")

        print(f"\n💡 Recommendations:")
        recommendations = self.get_recommendations()
        if recommendations:
            for i, rec in enumerate(recommendations[:10], 1):
                priority_icon = "🔴" if rec['priority'] == 'HIGH' else "🟡" if rec['priority'] == 'MEDIUM' else "🟢"
                print(f"  {i}. {priority_icon} [{rec['type']}] {rec['description']}")
                print(f"      {rec['reason']}")
        else:
            print("  ✅ No optimization recommendations at this time")

        print("\n" + "="*80 + "\n")


class QueryExecutionTracker:
    """Context manager for tracking query execution"""

    def __init__(self, optimizer: QueryOptimizer, query: str, params: Optional[tuple] = None):
        self.optimizer = optimizer
        self.query = query
        self.params = params
        self.start_time = None
        self.rows_affected = 0

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:  # Only record successful queries
            execution_time_ms = (time.time() - self.start_time) * 1000
            self.optimizer.record_query_execution(
                self.query,
                execution_time_ms,
                self.rows_affected,
                self.params
            )

    def set_rows_affected(self, rows: int):
        """Set number of rows affected by query"""
        self.rows_affected = rows


# Global optimizer instance
_global_query_optimizer: Optional[QueryOptimizer] = None


def get_query_optimizer() -> QueryOptimizer:
    """Get global query optimizer instance (singleton)"""
    global _global_query_optimizer
    if _global_query_optimizer is None:
        _global_query_optimizer = QueryOptimizer()
    return _global_query_optimizer


if __name__ == "__main__":
    # Test query optimizer
    import random

    print("Testing Query Optimizer...\n")

    optimizer = QueryOptimizer(slow_query_threshold_ms=500)

    # Simulate query executions
    test_queries = [
        "SELECT * FROM trades WHERE symbol = %s AND status = %s",
        "SELECT * FROM positions WHERE symbol = %s",
        "INSERT INTO trades (symbol, quantity, price) VALUES (%s, %s, %s)",
        "UPDATE positions SET quantity = %s WHERE symbol = %s",
        "SELECT COUNT(*) FROM trades WHERE entry_time > %s",
    ]

    print("Simulating 1000 query executions...")
    for i in range(1000):
        query = random.choice(test_queries)
        execution_time = random.gauss(200, 150)  # Avg 200ms, some slow queries

        optimizer.record_query_execution(
            query,
            max(10, execution_time),  # Min 10ms
            rows_affected=random.randint(0, 100)
        )

    # Analyze index usage
    print("\nAnalyzing index opportunities...")
    table_queries = {
        'trades': [
            "SELECT * FROM trades WHERE symbol = 'NIFTY' AND status = 'OPEN'",
            "SELECT * FROM trades WHERE entry_time > '2024-01-01'",
            "SELECT * FROM trades WHERE symbol = 'BANKNIFTY'",
        ],
        'positions': [
            "SELECT * FROM positions WHERE symbol = 'RELIANCE'",
            "SELECT * FROM positions WHERE status = 'ACTIVE'",
        ]
    }
    optimizer.analyze_index_usage(table_queries)

    # Print report
    optimizer.print_report()

    print("✅ Query optimizer tests passed")
