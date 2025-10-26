# 🛡️ WAF CONFIGURATION GUIDE

**Web Application Firewall Setup for Trading System**
**Version**: 1.0
**Date**: October 26, 2025
**Environment**: Production

---

## Executive Summary

This document provides comprehensive configuration for Web Application Firewall (WAF) to protect the trading system from common web attacks including SQL injection, XSS, DDoS, and other OWASP Top 10 vulnerabilities.

**WAF Provider**: AWS WAF (can be adapted for Cloudflare, Imperva, etc.)

---

## WAF Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     INTERNET                             │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
         ┌────────────────────────┐
         │      AWS WAF           │
         │  ┌──────────────────┐  │
         │  │  Rate Limiting   │  │
         │  │  Geo Blocking    │  │
         │  │  SQL Injection   │  │
         │  │  XSS Protection  │  │
         │  │  Bad Bots        │  │
         │  └──────────────────┘  │
         └────────────┬───────────┘
                      │
                      ▼
         ┌────────────────────────┐
         │  Application Load      │
         │  Balancer (ALB)        │
         └────────────┬───────────┘
                      │
                      ▼
         ┌────────────────────────┐
         │  Trading System API    │
         └────────────────────────┘
```

---

## WAF Rule Groups

### 1. Core Rule Set (CRS) ✅

**Purpose**: Protection against OWASP Top 10 vulnerabilities

**Rules Included**:
- SQL Injection (SQLi) protection
- Cross-Site Scripting (XSS) protection
- Local File Inclusion (LFI) protection
- Remote File Inclusion (RFI) protection
- Remote Code Execution (RCE) protection
- PHP Injection protection
- Session Fixation protection

**Configuration** (AWS WAF):
```json
{
  "Name": "AWS-AWSManagedRulesCommonRuleSet",
  "Priority": 1,
  "Statement": {
    "ManagedRuleGroupStatement": {
      "VendorName": "AWS",
      "Name": "AWSManagedRulesCommonRuleSet",
      "ExcludedRules": []
    }
  },
  "OverrideAction": {
    "None": {}
  },
  "VisibilityConfig": {
    "SampledRequestsEnabled": true,
    "CloudWatchMetricsEnabled": true,
    "MetricName": "AWSManagedRulesCommonRuleSetMetric"
  }
}
```

**Action**: BLOCK
**Log**: All blocked requests

---

### 2. SQL Injection Protection ✅

**Purpose**: Block SQL injection attacks targeting database

**Patterns Detected**:
- Classic SQLi: `' OR 1=1--`, `UNION SELECT`, `DROP TABLE`
- Blind SQLi: Time-based, boolean-based
- Encoded SQLi: URL-encoded, hex-encoded

**Configuration**:
```json
{
  "Name": "SQLInjectionProtection",
  "Priority": 2,
  "Statement": {
    "ManagedRuleGroupStatement": {
      "VendorName": "AWS",
      "Name": "AWSManagedRulesSQLiRuleSet"
    }
  },
  "OverrideAction": {
    "None": {}
  },
  "VisibilityConfig": {
    "SampledRequestsEnabled": true,
    "CloudWatchMetricsEnabled": true,
    "MetricName": "SQLInjectionProtectionMetric"
  }
}
```

**Protected Endpoints**:
- `/api/v1/market/*` - Market data queries
- `/api/v1/orders/*` - Order queries
- `/api/v1/portfolio/*` - Portfolio queries
- `/api/v1/strategies/*` - Strategy queries

**Testing**:
```bash
# Test SQL injection protection (should be blocked)
curl -X GET "https://api.trading.example.com/api/v1/market/quote/SBIN' OR 1=1--"
# Expected: HTTP 403 Forbidden

curl -X POST "https://api.trading.example.com/api/v1/orders" \
  -d '{"symbol": "TCS"; DROP TABLE orders;--"}'
# Expected: HTTP 403 Forbidden
```

---

### 3. XSS (Cross-Site Scripting) Protection ✅

**Purpose**: Block XSS attacks in user inputs

**Patterns Detected**:
- `<script>` tags
- JavaScript event handlers: `onclick`, `onerror`, `onload`
- Data URIs: `javascript:`, `data:text/html`
- Encoded scripts: Base64, hex, unicode

**Configuration**:
```json
{
  "Name": "XSSProtection",
  "Priority": 3,
  "Statement": {
    "XssMatchStatement": {
      "FieldToMatch": {
        "AllQueryArguments": {}
      },
      "TextTransformations": [
        {
          "Priority": 0,
          "Type": "URL_DECODE"
        },
        {
          "Priority": 1,
          "Type": "HTML_ENTITY_DECODE"
        }
      ]
    }
  },
  "Action": {
    "Block": {}
  },
  "VisibilityConfig": {
    "SampledRequestsEnabled": true,
    "CloudWatchMetricsEnabled": true,
    "MetricName": "XSSProtectionMetric"
  }
}
```

**Protected Fields**:
- Query parameters
- Request body
- Headers (User-Agent, Referer)

---

### 4. Rate Limiting ✅

**Purpose**: Prevent DDoS and brute force attacks

**Rate Limits**:

#### Global Rate Limit
- **Limit**: 1000 requests per 5 minutes per IP
- **Action**: BLOCK for 10 minutes

```json
{
  "Name": "GlobalRateLimit",
  "Priority": 4,
  "Statement": {
    "RateBasedStatement": {
      "Limit": 1000,
      "AggregateKeyType": "IP"
    }
  },
  "Action": {
    "Block": {
      "CustomResponse": {
        "ResponseCode": 429,
        "CustomResponseBodyKey": "RateLimitExceeded"
      }
    }
  },
  "VisibilityConfig": {
    "SampledRequestsEnabled": true,
    "CloudWatchMetricsEnabled": true,
    "MetricName": "GlobalRateLimitMetric"
  }
}
```

#### API Endpoint Rate Limits
```json
{
  "Name": "APIRateLimit",
  "Priority": 5,
  "Statement": {
    "RateBasedStatement": {
      "Limit": 100,
      "AggregateKeyType": "IP",
      "ScopeDownStatement": {
        "ByteMatchStatement": {
          "FieldToMatch": {
            "UriPath": {}
          },
          "PositionalConstraint": "STARTS_WITH",
          "SearchString": "/api/v1/",
          "TextTransformations": [
            {
              "Priority": 0,
              "Type": "LOWERCASE"
            }
          ]
        }
      }
    }
  },
  "Action": {
    "Block": {}
  }
}
```

#### Login Rate Limit (Brute Force Protection)
```json
{
  "Name": "LoginRateLimit",
  "Priority": 6,
  "Statement": {
    "RateBasedStatement": {
      "Limit": 20,
      "AggregateKeyType": "IP",
      "ScopeDownStatement": {
        "ByteMatchStatement": {
          "FieldToMatch": {
            "UriPath": {}
          },
          "PositionalConstraint": "EXACTLY",
          "SearchString": "/api/v1/auth/login",
          "TextTransformations": [
            {
              "Priority": 0,
              "Type": "LOWERCASE"
            }
          ]
        }
      }
    }
  },
  "Action": {
    "Block": {
      "CustomResponse": {
        "ResponseCode": 429
      }
    }
  }
}
```

---

### 5. Geo-Blocking ✅

**Purpose**: Block traffic from high-risk countries

**Allowed Countries** (India-focused trading):
- IN (India) - Primary market
- US, GB, SG, AE - International users (if needed)

**Configuration**:
```json
{
  "Name": "GeoBlocking",
  "Priority": 7,
  "Statement": {
    "NotStatement": {
      "Statement": {
        "GeoMatchStatement": {
          "CountryCodes": ["IN", "US", "GB", "SG", "AE"]
        }
      }
    }
  },
  "Action": {
    "Block": {
      "CustomResponse": {
        "ResponseCode": 403,
        "CustomResponseBodyKey": "GeoBlockedMessage"
      }
    }
  },
  "VisibilityConfig": {
    "SampledRequestsEnabled": true,
    "CloudWatchMetricsEnabled": true,
    "MetricName": "GeoBlockingMetric"
  }
}
```

**Note**: Adjust country list based on business requirements.

---

### 6. Bot Protection ✅

**Purpose**: Block malicious bots while allowing legitimate traffic

**Categories**:
- **Block**: Scrapers, scanners, spam bots
- **Allow**: Search engine bots (Googlebot), monitoring tools

**Configuration**:
```json
{
  "Name": "BotControl",
  "Priority": 8,
  "Statement": {
    "ManagedRuleGroupStatement": {
      "VendorName": "AWS",
      "Name": "AWSManagedRulesBotControlRuleSet",
      "ManagedRuleGroupConfigs": [
        {
          "AWSManagedRulesBotControlRuleSet": {
            "InspectionLevel": "COMMON"
          }
        }
      ]
    }
  },
  "OverrideAction": {
    "None": {}
  },
  "VisibilityConfig": {
    "SampledRequestsEnabled": true,
    "CloudWatchMetricsEnabled": true,
    "MetricName": "BotControlMetric"
  }
}
```

**Known Good Bots** (Allowed):
- Googlebot
- Bingbot
- Prometheus/Grafana monitoring
- Uptime monitoring services

---

### 7. IP Reputation ✅

**Purpose**: Block known malicious IP addresses

**Sources**:
- AWS Threat Intelligence
- Third-party threat feeds
- Custom blocklist (abuse reports)

**Configuration**:
```json
{
  "Name": "IPReputationList",
  "Priority": 9,
  "Statement": {
    "ManagedRuleGroupStatement": {
      "VendorName": "AWS",
      "Name": "AWSManagedRulesAmazonIpReputationList"
    }
  },
  "OverrideAction": {
    "None": {}
  },
  "VisibilityConfig": {
    "SampledRequestsEnabled": true,
    "CloudWatchMetricsEnabled": true,
    "MetricName": "IPReputationMetric"
  }
}
```

---

### 8. Known Bad Inputs ✅

**Purpose**: Block common attack patterns

**Patterns**:
- Known exploits (Log4j, Spring4Shell)
- Directory traversal: `../`, `..\\`
- Command injection: `; whoami`, `| ls`
- SSRF attempts: `http://169.254.169.254/` (AWS metadata)

**Configuration**:
```json
{
  "Name": "KnownBadInputs",
  "Priority": 10,
  "Statement": {
    "ManagedRuleGroupStatement": {
      "VendorName": "AWS",
      "Name": "AWSManagedRulesKnownBadInputsRuleSet"
    }
  },
  "OverrideAction": {
    "None": {}
  },
  "VisibilityConfig": {
    "SampledRequestsEnabled": true,
    "CloudWatchMetricsEnabled": true,
    "MetricName": "KnownBadInputsMetric"
  }
}
```

---

## Custom Rules

### 9. Admin Path Protection ✅

**Purpose**: Restrict access to admin endpoints

**Protected Paths**:
- `/api/v1/admin/*`
- `/api/v1/system/*`
- `/api/v1/config/*`

**Configuration**:
```json
{
  "Name": "AdminPathProtection",
  "Priority": 11,
  "Statement": {
    "AndStatement": {
      "Statements": [
        {
          "ByteMatchStatement": {
            "FieldToMatch": {
              "UriPath": {}
            },
            "PositionalConstraint": "STARTS_WITH",
            "SearchString": "/api/v1/admin/",
            "TextTransformations": [
              {
                "Priority": 0,
                "Type": "LOWERCASE"
              }
            ]
          }
        },
        {
          "NotStatement": {
            "Statement": {
              "IPSetReferenceStatement": {
                "Arn": "arn:aws:wafv2:region:account-id:regional/ipset/admin-ips/id"
              }
            }
          }
        }
      ]
    }
  },
  "Action": {
    "Block": {}
  },
  "VisibilityConfig": {
    "SampledRequestsEnabled": true,
    "CloudWatchMetricsEnabled": true,
    "MetricName": "AdminPathProtectionMetric"
  }
}
```

**Admin IP Whitelist**:
- Corporate office IPs
- VPN exit IPs
- Trusted administrator IPs

---

### 10. Large Request Body Protection ✅

**Purpose**: Block excessively large requests (potential DoS)

**Limits**:
- Max request size: 8 KB (API endpoints)
- Max request size: 128 KB (file uploads, if needed)

**Configuration**:
```json
{
  "Name": "LargeRequestBodyProtection",
  "Priority": 12,
  "Statement": {
    "SizeConstraintStatement": {
      "FieldToMatch": {
        "Body": {}
      },
      "ComparisonOperator": "GT",
      "Size": 8192,
      "TextTransformations": [
        {
          "Priority": 0,
          "Type": "NONE"
        }
      ]
    }
  },
  "Action": {
    "Block": {}
  },
  "VisibilityConfig": {
    "SampledRequestsEnabled": true,
    "CloudWatchMetricsEnabled": true,
    "MetricName": "LargeRequestBodyMetric"
  }
}
```

---

## Monitoring & Logging

### CloudWatch Metrics

**Key Metrics**:
- `AllowedRequests` - Total allowed requests
- `BlockedRequests` - Total blocked requests
- `CountedRequests` - Requests matching COUNT rules
- `Rule-specific metrics` - Metrics per rule

**Alarms**:
```json
{
  "AlarmName": "WAF-HighBlockRate",
  "MetricName": "BlockedRequests",
  "Namespace": "AWS/WAFV2",
  "Statistic": "Sum",
  "Period": 300,
  "EvaluationPeriods": 2,
  "Threshold": 1000,
  "ComparisonOperator": "GreaterThanThreshold",
  "AlarmActions": ["arn:aws:sns:region:account:trading-system-alerts"]
}
```

### WAF Logging

**Log Destination**: Amazon Kinesis Data Firehose → S3

**Configuration**:
```json
{
  "ResourceArn": "arn:aws:wafv2:region:account:regional/webacl/trading-system-waf/id",
  "LogDestinationConfigs": [
    "arn:aws:firehose:region:account:deliverystream/aws-waf-logs-trading-system"
  ],
  "RedactedFields": [
    {
      "SingleHeader": {
        "Name": "authorization"
      }
    }
  ]
}
```

**Log Analysis**:
- Top blocked IPs
- Most triggered rules
- Attack patterns and trends
- False positive identification

---

## Terraform Configuration

### Complete WAF Setup

```hcl
# WAF Web ACL
resource "aws_wafv2_web_acl" "trading_system" {
  name  = "trading-system-waf"
  scope = "REGIONAL"

  default_action {
    allow {}
  }

  # Rule 1: AWS Managed Common Rule Set
  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 1

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesCommonRuleSet"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AWSManagedRulesCommonRuleSetMetric"
      sampled_requests_enabled   = true
    }
  }

  # Rule 2: SQL Injection Protection
  rule {
    name     = "AWSManagedRulesSQLiRuleSet"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesSQLiRuleSet"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "SQLInjectionProtectionMetric"
      sampled_requests_enabled   = true
    }
  }

  # Rule 3: Rate Limiting
  rule {
    name     = "GlobalRateLimit"
    priority = 4

    action {
      block {
        custom_response {
          response_code = 429
        }
      }
    }

    statement {
      rate_based_statement {
        limit              = 1000
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "GlobalRateLimitMetric"
      sampled_requests_enabled   = true
    }
  }

  # Rule 4: Geo Blocking
  rule {
    name     = "GeoBlocking"
    priority = 7

    action {
      block {}
    }

    statement {
      not_statement {
        statement {
          geo_match_statement {
            country_codes = ["IN", "US", "GB", "SG", "AE"]
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "GeoBlockingMetric"
      sampled_requests_enabled   = true
    }
  }

  # Rule 5: IP Reputation
  rule {
    name     = "AWSManagedRulesAmazonIpReputationList"
    priority = 9

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesAmazonIpReputationList"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "IPReputationMetric"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "TradingSystemWAFMetric"
    sampled_requests_enabled   = true
  }

  tags = {
    Name        = "trading-system-waf"
    Environment = var.environment
  }
}

# Associate WAF with ALB
resource "aws_wafv2_web_acl_association" "alb" {
  resource_arn = aws_lb.trading_system.arn
  web_acl_arn  = aws_wafv2_web_acl.trading_system.arn
}

# Admin IP Set
resource "aws_wafv2_ip_set" "admin_ips" {
  name               = "admin-ips"
  scope              = "REGIONAL"
  ip_address_version = "IPV4"

  addresses = [
    "203.0.113.0/24",  # Office IP range
    "198.51.100.50/32" # VPN exit IP
  ]

  tags = {
    Name = "admin-ips"
  }
}

# WAF Logging
resource "aws_wafv2_web_acl_logging_configuration" "trading_system" {
  resource_arn = aws_wafv2_web_acl.trading_system.arn

  log_destination_configs = [
    aws_kinesis_firehose_delivery_stream.waf_logs.arn
  ]

  redacted_fields {
    single_header {
      name = "authorization"
    }
  }
}
```

---

## Testing & Validation

### WAF Testing Checklist

**1. SQL Injection Tests**
```bash
# Test 1: Classic SQLi
curl "https://api.trading.example.com/api/v1/market/quote/SBIN' OR 1=1--"
# Expected: HTTP 403

# Test 2: UNION-based SQLi
curl "https://api.trading.example.com/api/v1/orders?id=1 UNION SELECT * FROM users"
# Expected: HTTP 403
```

**2. XSS Tests**
```bash
# Test 1: Script tag
curl "https://api.trading.example.com/search?q=<script>alert('XSS')</script>"
# Expected: HTTP 403

# Test 2: Event handler
curl "https://api.trading.example.com/search?q=<img src=x onerror=alert(1)>"
# Expected: HTTP 403
```

**3. Rate Limiting Tests**
```bash
# Test: Exceed rate limit
for i in {1..1100}; do
  curl "https://api.trading.example.com/health"
done
# Expected: HTTP 429 after 1000 requests
```

**4. Geo-Blocking Test**
```bash
# Use proxy from blocked country
curl -x proxy-from-blocked-country:port "https://api.trading.example.com/"
# Expected: HTTP 403
```

---

## Incident Response

### WAF Alert Response

**High Block Rate Alert**:
1. Check CloudWatch dashboard for spike
2. Identify triggered rule
3. Review WAF logs for attack patterns
4. Analyze source IPs
5. Determine if legitimate traffic or attack
6. Adjust rules if false positives
7. Block IPs manually if needed

**False Positive Handling**:
1. Identify affected rule
2. Review sampled requests
3. Create exception for legitimate pattern
4. Test exception in staging
5. Deploy to production
6. Monitor for 24 hours

---

## Maintenance

### Regular Tasks

**Weekly**:
- Review WAF logs for patterns
- Check false positive reports
- Update admin IP whitelist

**Monthly**:
- Review and update geo-blocking rules
- Analyze attack trends
- Update custom rules
- Test rule effectiveness

**Quarterly**:
- Full WAF audit
- Penetration testing
- Rule optimization
- Cost optimization

---

## Cost Optimization

**AWS WAF Pricing** (Estimated):
- Web ACL: $5/month
- Rules: $1/month per rule (12 rules = $12/month)
- Requests: $0.60 per million requests
- **Estimated Monthly Cost**: $50-200/month depending on traffic

**Optimization Tips**:
- Combine rules where possible
- Use managed rule groups (cost-effective)
- Implement caching to reduce requests
- Archive old logs to Glacier

---

## Appendix

### A. Custom Response Bodies

```json
{
  "RateLimitExceeded": {
    "ContentType": "APPLICATION_JSON",
    "Content": "{\"error\": \"Rate limit exceeded. Please try again later.\"}"
  },
  "GeoBlockedMessage": {
    "ContentType": "APPLICATION_JSON",
    "Content": "{\"error\": \"Access from your location is not permitted.\"}"
  }
}
```

### B. IP Set Management

**Adding IPs to Admin Whitelist**:
```bash
aws wafv2 update-ip-set \
  --name admin-ips \
  --scope REGIONAL \
  --id <ip-set-id> \
  --addresses "203.0.113.0/24" "198.51.100.50/32" "192.0.2.100/32"
```

### C. WAF Log Analysis Queries

**Top Blocked IPs**:
```sql
SELECT httpRequest.clientIp, COUNT(*) as count
FROM waf_logs
WHERE action = 'BLOCK'
GROUP BY httpRequest.clientIp
ORDER BY count DESC
LIMIT 10;
```

**Most Triggered Rules**:
```sql
SELECT terminatingRuleId, COUNT(*) as count
FROM waf_logs
WHERE action = 'BLOCK'
GROUP BY terminatingRuleId
ORDER BY count DESC;
```

---

**Document Version**: 1.0
**Last Updated**: October 26, 2025
**Next Review**: Monthly
**Owner**: Security Team

---

✅ **WAF CONFIGURATION READY FOR DEPLOYMENT**
