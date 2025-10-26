# Terraform Variables for Trading System Infrastructure

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "trading-system"
}

variable "environment" {
  description = "Environment name (staging, production)"
  type        = string

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "Environment must be staging or production."
  }
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

# VPC Configuration
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.11.0/24", "10.0.12.0/24", "10.0.13.0/24"]
}

# Database Configuration
variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.medium"
}

variable "db_allocated_storage" {
  description = "Allocated storage for RDS (GB)"
  type        = number
  default     = 100
}

variable "db_max_allocated_storage" {
  description = "Maximum allocated storage for RDS (GB)"
  type        = number
  default     = 500
}

variable "db_master_username" {
  description = "Master username for RDS"
  type        = string
  default     = "admin"
  sensitive   = true
}

# Redis Configuration
variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.medium"
}

variable "redis_num_nodes" {
  description = "Number of cache nodes"
  type        = number
  default     = 2
}

# Application Configuration
variable "trading_system_image" {
  description = "Docker image for trading system"
  type        = string
  default     = "trading-system:latest"
}

variable "trading_system_desired_count" {
  description = "Desired number of trading system tasks"
  type        = number
  default     = 2
}

variable "trading_system_min_capacity" {
  description = "Minimum number of trading system tasks"
  type        = number
  default     = 1
}

variable "trading_system_max_capacity" {
  description = "Maximum number of trading system tasks"
  type        = number
  default     = 10
}

variable "dashboard_image" {
  description = "Docker image for dashboard"
  type        = string
  default     = "trading-dashboard:latest"
}

variable "dashboard_desired_count" {
  description = "Desired number of dashboard tasks"
  type        = number
  default     = 2
}

variable "dashboard_min_capacity" {
  description = "Minimum number of dashboard tasks"
  type        = number
  default     = 1
}

variable "dashboard_max_capacity" {
  description = "Maximum number of dashboard tasks"
  type        = number
  default     = 5
}

# SSL Configuration
variable "ssl_certificate_arn" {
  description = "ARN of SSL certificate"
  type        = string
  default     = ""
}

# Monitoring Configuration
variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "log_level" {
  description = "Application log level"
  type        = string
  default     = "INFO"

  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR"], var.log_level)
    error_message = "Log level must be DEBUG, INFO, WARNING, or ERROR."
  }
}

# Alerting Configuration
variable "alert_email" {
  description = "Email address for alerts"
  type        = string
}

# DNS Configuration
variable "manage_dns" {
  description = "Whether to manage DNS with Route53"
  type        = bool
  default     = false
}

variable "domain_name" {
  description = "Domain name for the application"
  type        = string
  default     = ""
}

# Tags
variable "additional_tags" {
  description = "Additional tags to apply to resources"
  type        = map(string)
  default     = {}
}
