# Production Environment Configuration

environment = "production"
aws_region  = "us-east-1"

# Production-grade instance sizes
db_instance_class = "db.r6g.xlarge"
db_allocated_storage = 500
db_max_allocated_storage = 2000

redis_node_type = "cache.r6g.large"
redis_num_nodes = 3

# Production capacity
trading_system_desired_count = 3
trading_system_min_capacity  = 2
trading_system_max_capacity  = 20

dashboard_desired_count = 2
dashboard_min_capacity  = 2
dashboard_max_capacity  = 10

# Production log retention
log_retention_days = 90

# Alert configuration
alert_email = "alerts@example.com"  # Update with actual email

# DNS management
manage_dns = true
domain_name = "trading.example.com"  # Update with actual domain
