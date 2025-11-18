# Load Balancer Setup Guide

## Overview

This guide explains how to set up a load balancer for production deployment of the trading system to eliminate single points of failure and improve reliability.

## Architecture

```
                                Internet
                                    |
                            [Load Balancer]
                             (NGINX/HAProxy)
                                    |
                  +-----------------+-----------------+
                  |                 |                 |
          [Trading System 1]  [Trading System 2]  [Trading System 3]
          (Primary Instance)  (Backup Instance)   (Backup Instance)
                  |                 |                 |
                  +-----------------+-----------------+
                                    |
                          [Shared State Database]
                          (SQLite with WAL mode)
```

## Option 1: NGINX Load Balancer (Recommended)

### 1. Install NGINX

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install nginx

# macOS
brew install nginx

# CentOS/RHEL
sudo yum install nginx
```

### 2. Configure NGINX

Create `/etc/nginx/conf.d/trading-system.conf`:

```nginx
# Upstream backend servers
upstream trading_backend {
    # Least connections load balancing
    least_conn;

    # Primary instance
    server localhost:8080 max_fails=3 fail_timeout=30s weight=2;

    # Backup instances
    server localhost:8081 max_fails=3 fail_timeout=30s weight=1;
    server localhost:8082 max_fails=3 fail_timeout=30s weight=1 backup;
}

# HTTP server (redirect to HTTPS)
server {
    listen 80;
    server_name trading-system.example.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name trading-system.example.com;

    # SSL configuration
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;

    # Dashboard location
    location / {
        proxy_pass http://trading_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Metrics endpoint (for Prometheus)
    location /metrics {
        proxy_pass http://trading_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # Restrict access to metrics
        allow 10.0.0.0/8;  # Internal network
        deny all;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://trading_backend;
        access_log off;
    }
}
```

### 3. Start Multiple Trading System Instances

```bash
# Instance 1 (Primary)
export DASHBOARD_PORT=8080
export INSTANCE_ID=1
python main.py &

# Instance 2 (Backup)
export DASHBOARD_PORT=8081
export INSTANCE_ID=2
python main.py &

# Instance 3 (Backup - only if needed)
export DASHBOARD_PORT=8082
export INSTANCE_ID=3
python main.py &
```

### 4. Test Configuration

```bash
# Test NGINX configuration
sudo nginx -t

# Reload NGINX
sudo nginx -s reload

# Test load balancer
curl -k https://trading-system.example.com/health
```

## Option 2: HAProxy Load Balancer

### 1. Install HAProxy

```bash
# Ubuntu/Debian
sudo apt-get install haproxy

# macOS
brew install haproxy
```

### 2. Configure HAProxy

Create `/etc/haproxy/haproxy.cfg`:

```haproxy
global
    log /dev/log local0
    log /dev/log local1 notice
    chroot /var/lib/haproxy
    stats socket /run/haproxy/admin.sock mode 660 level admin
    stats timeout 30s
    user haproxy
    group haproxy
    daemon

    # SSL/TLS configuration
    ssl-default-bind-ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256
    ssl-default-bind-options ssl-min-ver TLSv1.2 no-tls-tickets

defaults
    log     global
    mode    http
    option  httplog
    option  dontlognull
    timeout connect 5000
    timeout client  50000
    timeout server  50000

# Stats interface
listen stats
    bind *:8404
    stats enable
    stats uri /stats
    stats refresh 30s
    stats admin if TRUE

# Frontend - HTTPS
frontend https_front
    bind *:443 ssl crt /path/to/cert.pem
    mode http

    # Security headers
    http-response set-header Strict-Transport-Security "max-age=31536000; includeSubDomains"
    http-response set-header X-Frame-Options "DENY"

    # ACLs
    acl is_health path_beg /health
    acl is_metrics path_beg /metrics

    # Route to backends
    use_backend trading_backend

# Backend - Trading System Instances
backend trading_backend
    mode http
    balance leastconn

    # Health checks
    option httpchk GET /health
    http-check expect status 200

    # Servers
    server trading1 localhost:8080 check maxconn 100 weight 2
    server trading2 localhost:8081 check maxconn 100 weight 1
    server trading3 localhost:8082 check maxconn 100 weight 1 backup
```

### 3. Start HAProxy

```bash
# Test configuration
sudo haproxy -c -f /etc/haproxy/haproxy.cfg

# Start HAProxy
sudo systemctl start haproxy
sudo systemctl enable haproxy

# Check status
sudo systemctl status haproxy
```

## Shared State Configuration

### SQLite with WAL Mode (Recommended for < 10 instances)

```python
# In your trading system configuration
import sqlite3

conn = sqlite3.connect('state/shared_state.db')

# Enable WAL mode for better concurrency
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")
conn.execute("PRAGMA busy_timeout=30000")  # 30 seconds

# Use connection pooling from Phase 2
from core.connection_pool import get_db_pool
pool = get_db_pool('state/shared_state.db', min_size=5, max_size=20)
```

### File Locking for Coordination

```python
import fcntl
import contextlib

@contextlib.contextmanager
def file_lock(lock_file='state/trading.lock'):
    """Ensure only one instance processes at a time"""
    with open(lock_file, 'w') as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        except IOError:
            raise RuntimeError("Another instance is already running")
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
```

## Monitoring & Health Checks

### Health Check Endpoint

Add to your dashboard server:

```python
# In enhanced_dashboard_server.py
def do_GET(self):
    if self.path == '/health':
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'instance_id': os.getenv('INSTANCE_ID', '1'),
            'uptime_seconds': time.time() - START_TIME,
            'active_positions': len(get_active_positions()),
            'database_connected': check_database_connection()
        }

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(health_status).encode())
```

### Prometheus Metrics

```python
# Export metrics for load balancer health checks
from core.metrics_exporter import get_global_metrics

def do_GET(self):
    if self.path == '/metrics':
        metrics = get_global_metrics()
        content, content_type = metrics.export_metrics(), metrics.get_content_type()

        self.send_response(200)
        self.send_header('Content-type', content_type)
        self.end_headers()
        self.wfile.write(content)
```

## Production Deployment Checklist

- [ ] **Multiple instances configured** (minimum 2)
- [ ] **Load balancer installed and configured** (NGINX or HAProxy)
- [ ] **SSL/TLS certificates installed** (Let's Encrypt recommended)
- [ ] **Health check endpoint working** (`/health` returns 200)
- [ ] **Metrics endpoint configured** (`/metrics` for Prometheus)
- [ ] **Shared state database with WAL mode**
- [ ] **File locking for critical operations**
- [ ] **Monitoring alerts configured** (Prometheus + Alertmanager)
- [ ] **Backup instances tested** (failover scenario)
- [ ] **Log aggregation configured** (ELK stack or similar)
- [ ] **Security headers configured** (HSTS, CSP, etc.)

## Testing Failover

```bash
# Test 1: Stop primary instance
kill -9 <primary_pid>

# Verify load balancer redirects to backup
curl -k https://trading-system.example.com/health

# Test 2: Gradual rollout
# Stop instance, deploy new version, start instance
# Repeat for all instances (zero-downtime deployment)
```

## Cost Optimization

### Single Server, Multiple Processes
- **Good for:** Small-scale trading (< 100 trades/day)
- **Cost:** Minimal (1 server)
- **Reliability:** Medium (single point of failure)

### Multi-Server with Load Balancer
- **Good for:** Production trading (100+ trades/day)
- **Cost:** Moderate (2-3 servers + load balancer)
- **Reliability:** High (99.9%+ uptime)

### Cloud Auto-Scaling
- **Good for:** Variable load, enterprise-scale
- **Cost:** Variable (pay for what you use)
- **Reliability:** Very High (99.99%+ uptime)

## Troubleshooting

### Load Balancer Not Distributing Traffic

```bash
# Check NGINX/HAProxy logs
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/haproxy.log

# Verify backend servers are reachable
curl http://localhost:8080/health
curl http://localhost:8081/health

# Check load balancer status
# NGINX: Check error logs
# HAProxy: Visit http://localhost:8404/stats
```

### Database Locking Issues

```bash
# Check SQLite WAL mode is enabled
sqlite3 state/shared_state.db "PRAGMA journal_mode;"

# Should return: wal

# If not, enable it:
sqlite3 state/shared_state.db "PRAGMA journal_mode=WAL;"
```

### Instance Not Starting

```bash
# Check if port is already in use
lsof -i :8080

# Check logs
tail -f logs/trading_errors_*.log

# Verify environment variables
env | grep -E 'DASHBOARD_PORT|INSTANCE_ID'
```

## Conclusion

Load balancing provides:
- **99.9%+ uptime** (eliminates single point of failure)
- **Horizontal scaling** (add instances as load increases)
- **Zero-downtime deployments** (gradual rollout)
- **Better performance** (distribute load across instances)

**Recommended Setup:**
- **Development:** Single instance (no load balancer)
- **Staging:** 2 instances + NGINX
- **Production:** 3+ instances + NGINX + monitoring

For questions or issues, refer to NGINX/HAProxy documentation or create an issue in the repository.
