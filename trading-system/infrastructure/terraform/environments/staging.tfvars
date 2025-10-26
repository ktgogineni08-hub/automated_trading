# Staging Environment Configuration

environment = "staging"
aws_region  = "us-east-1"

# Smaller instance sizes for staging
db_instance_class = "db.t3.small"
redis_node_type   = "cache.t3.small"
redis_num_nodes   = 1

# Lower capacity for staging
trading_system_desired_count = 1
trading_system_min_capacity  = 1
trading_system_max_capacity  = 3

dashboard_desired_count = 1
dashboard_min_capacity  = 1
dashboard_max_capacity  = 2

# Shorter log retention
log_retention_days = 7

# Alert configuration
alert_email = "devops@example.com"  # Update with actual email
