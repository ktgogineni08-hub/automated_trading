# ELK Stack for Trading System
Phase 4 Tier 3: Advanced Observability

## Overview

Complete ELK (Elasticsearch, Logstash, Kibana) stack for centralized logging and monitoring of the trading system.

## Components

### Elasticsearch
- **Version:** 8.11.0
- **Port:** 9200 (HTTP), 9300 (Transport)
- **Purpose:** Log storage and full-text search
- **Data:** Stored in Docker volume `elasticsearch-data`

### Logstash
- **Version:** 8.11.0
- **Port:** 5000 (TCP/UDP), 9600 (API)
- **Purpose:** Log aggregation, parsing, and enrichment
- **Configuration:** `logstash/pipeline/trading-system.conf`

### Kibana
- **Version:** 8.11.0
- **Port:** 5601
- **Purpose:** Visualization and dashboard interface
- **Access:** http://localhost:5601

## Quick Start

### 1. Start ELK Stack

```bash
# Navigate to ELK directory
cd infrastructure/elk

# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### 2. Verify Services

```bash
# Test Elasticsearch
curl http://localhost:9200

# Test Logstash
curl http://localhost:9600

# Access Kibana
open http://localhost:5601
```

### 3. Configure Python Logging

```python
from utilities.elk_logging import TradingSystemLogger

# Initialize logger with ELK support
logger_instance = TradingSystemLogger(
    name='trading_system',
    enable_elk=True,
    elk_host='localhost',
    elk_port=5000
)

logger = logger_instance.get_logger()

# Use logger
logger.info("Trading system started")
logger_instance.log_trade('RELIANCE', 'BUY', 10, 2500.50)
```

## Features

### Structured Logging
- JSON-formatted logs
- Automatic field enrichment
- Exception tracking with full traceback
- Performance metrics tracking

### Log Parsing
- Automatic extraction of trading events
- Symbol, price, quantity parsing
- P&L calculation tracking
- Error classification

### Alerting
- Critical error indexing to separate index
- Real-time error notifications
- Performance degradation alerts

## Log Types

### Trade Logs
```json
{
  "timestamp": "2025-10-22T10:30:00Z",
  "level": "INFO",
  "event_type": "trade",
  "symbol": "RELIANCE",
  "action": "BUY",
  "quantity": 10,
  "price": 2500.50,
  "message": "Trade executed"
}
```

### Performance Logs
```json
{
  "timestamp": "2025-10-22T10:30:00Z",
  "level": "INFO",
  "event_type": "performance",
  "operation": "order_execution",
  "latency_ms": 45.2,
  "message": "Performance: order_execution took 45.20ms"
}
```

### Error Logs
```json
{
  "timestamp": "2025-10-22T10:30:00Z",
  "level": "ERROR",
  "event_type": "error",
  "error_type": "ValueError",
  "error_message": "Invalid price",
  "exception": {
    "type": "ValueError",
    "message": "Invalid price",
    "traceback": ["..."]
  }
}
```

## Kibana Setup

### 1. Create Index Pattern

1. Open Kibana: http://localhost:5601
2. Navigate to Stack Management > Index Patterns
3. Click "Create index pattern"
4. Enter pattern: `trading-system-logs-*`
5. Select timestamp field: `@timestamp`
6. Click "Create"

### 2. Discover Logs

1. Navigate to Discover
2. Select index pattern: `trading-system-logs-*`
3. Add fields: `level`, `event_type`, `symbol`, `message`
4. Save search

### 3. Create Visualizations

**Example: Trade Volume by Symbol**
1. Navigate to Visualize
2. Create new visualization > Bar chart
3. Select index pattern
4. Y-axis: Count
5. X-axis: Terms aggregation on `symbol`
6. Save

**Example: Error Rate Over Time**
1. Create new visualization > Line chart
2. Y-axis: Count with filter `level:ERROR`
3. X-axis: Date histogram on `@timestamp`
4. Save

### 4. Create Dashboard

1. Navigate to Dashboard
2. Create new dashboard
3. Add visualizations:
   - Trade volume by symbol
   - Error rate over time
   - P&L distribution
   - Performance metrics
4. Save dashboard

## Management

### Stop Services

```bash
docker-compose down
```

### Stop and Remove Data

```bash
docker-compose down -v
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f elasticsearch
docker-compose logs -f logstash
docker-compose logs -f kibana
```

### Resource Management

**Memory Settings:**
- Elasticsearch: 512MB heap (adjustable in docker-compose.yml)
- Logstash: 256MB heap (adjustable in docker-compose.yml)
- Kibana: Default (typically 1GB)

**Disk Usage:**
- Logs are stored in Docker volume
- Monitor disk usage: `docker system df`
- Clean old data: Configure index lifecycle management in Elasticsearch

## Troubleshooting

### Elasticsearch Won't Start

```bash
# Check if port 9200 is in use
lsof -i :9200

# Increase virtual memory (Linux/Mac)
sysctl -w vm.max_map_count=262144

# Check logs
docker-compose logs elasticsearch
```

### Logstash Not Receiving Logs

```bash
# Test TCP connection
telnet localhost 5000

# Send test log
echo '{"message": "test"}' | nc localhost 5000

# Check Logstash logs
docker-compose logs logstash
```

### Kibana Not Accessible

```bash
# Check if service is running
docker-compose ps

# Wait for Elasticsearch to be healthy
docker-compose logs kibana

# Check Elasticsearch connection
curl http://localhost:9200/_cat/health
```

## Performance Tuning

### Logstash Pipeline

Edit `logstash/config/logstash.yml`:

```yaml
pipeline.workers: 4  # Increase for higher throughput
pipeline.batch.size: 250
pipeline.batch.delay: 50
```

### Elasticsearch Indexing

```bash
# Increase refresh interval for better performance
curl -X PUT "localhost:9200/trading-system-logs-*/_settings" \
  -H 'Content-Type: application/json' \
  -d '{"index": {"refresh_interval": "30s"}}'

# Optimize index for search
curl -X POST "localhost:9200/trading-system-logs-*/_forcemerge?max_num_segments=1"
```

## Security (Production)

### Enable Authentication

Edit `docker-compose.yml`:

```yaml
elasticsearch:
  environment:
    - xpack.security.enabled=true
    - ELASTIC_PASSWORD=your_password

kibana:
  environment:
    - ELASTICSEARCH_USERNAME=elastic
    - ELASTICSEARCH_PASSWORD=your_password
```

### Enable TLS

1. Generate certificates
2. Mount certificates in containers
3. Configure TLS in Elasticsearch
4. Update Kibana and Logstash configs

## Monitoring

### Cluster Health

```bash
curl http://localhost:9200/_cluster/health?pretty
```

### Index Statistics

```bash
curl http://localhost:9200/_cat/indices?v
```

### Logstash API

```bash
curl http://localhost:9600/_node/stats?pretty
```

## Integration Examples

### Python Application

```python
from utilities.elk_logging import get_logger

logger = get_logger(
    enable_elk=True,
    elk_host='localhost',
    elk_port=5000
)

logger.info("Application started")
```

### Bash Scripts

```bash
# Send log to Logstash
echo '{"level":"INFO","message":"Backup completed"}' | \
  nc localhost 5000
```

## Resources

- Elasticsearch Docs: https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html
- Logstash Docs: https://www.elastic.co/guide/en/logstash/current/index.html
- Kibana Docs: https://www.elastic.co/guide/en/kibana/current/index.html

## Support

For issues with the ELK stack:
1. Check docker-compose logs
2. Verify network connectivity
3. Check resource availability (memory, disk)
4. Review configuration files
5. Consult official Elastic documentation
