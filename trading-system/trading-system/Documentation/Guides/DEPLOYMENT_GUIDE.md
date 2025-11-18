# Deployment Guide
Phase 3 Tier 3: DevOps & Cloud Infrastructure

This guide covers deploying the trading system to production using Docker and Kubernetes.

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development with Docker](#local-development-with-docker)
3. [Production Deployment with Kubernetes](#production-deployment-with-kubernetes)
4. [CI/CD Pipeline](#cicd-pipeline)
5. [Monitoring & Observability](#monitoring--observability)
6. [Security Best Practices](#security-best-practices)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Tools
- Docker 24.0+ and Docker Compose 2.0+
- Kubernetes 1.28+ (for production)
- kubectl CLI
- Helm 3.0+ (optional but recommended)
- Git

### Cloud Provider Requirements
- AWS EKS, Google GKE, or Azure AKS cluster
- Container registry (DockerHub, ECR, GCR, or ACR)
- Persistent storage (EBS, Persistent Disks, or Azure Disks)

### Credentials Needed
- Zerodha API key and access token
- Encryption key (32-byte random string)
- Cloud provider credentials

---

## Local Development with Docker

### 1. Quick Start

```bash
# Clone repository
git clone <repository-url>
cd trading-system

# Create .env file
cp .env.example .env
# Edit .env and add your credentials

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f trading-system

# Access services
# - Trading Dashboard: http://localhost:8000
# - Prometheus: http://localhost:9091
# - Grafana: http://localhost:3000
```

### 2. Build Docker Image

```bash
# Build image
docker build -t trading-system:latest .

# Test image locally
docker run -it --rm \
  -e DEVELOPMENT_MODE=true \
  -e ZERODHA_API_KEY=your_key \
  -e ZERODHA_ACCESS_TOKEN=your_token \
  trading-system:latest

# Push to registry
docker tag trading-system:latest your-registry/trading-system:v3.0
docker push your-registry/trading-system:v3.0
```

### 3. Docker Compose Services

The `docker-compose.yml` includes:
- **trading-system**: Main application
- **prometheus**: Metrics collection
- **grafana**: Visualization dashboards
- **redis**: Caching layer
- **nginx**: Reverse proxy

```bash
# Start specific service
docker-compose up -d trading-system

# Scale service
docker-compose up -d --scale trading-system=3

# Stop all services
docker-compose down

# Remove volumes (⚠️  deletes data!)
docker-compose down -v
```

---

## Production Deployment with Kubernetes

### 1. Cluster Setup

#### AWS EKS Example

```bash
# Install eksctl
brew install eksctl  # macOS
# or download from https://eksctl.io

# Create EKS cluster
eksctl create cluster \
  --name trading-prod \
  --version 1.28 \
  --region us-east-1 \
  --nodegroup-name trading-nodes \
  --node-type m5.xlarge \
  --nodes 3 \
  --nodes-min 3 \
  --nodes-max 10 \
  --managed \
  --with-oidc

# Configure kubectl
aws eks update-kubeconfig --name trading-prod --region us-east-1
```

#### GKE Example

```bash
# Create GKE cluster
gcloud container clusters create trading-prod \
  --region us-central1 \
  --num-nodes 3 \
  --machine-type n1-standard-4 \
  --enable-autoscaling \
  --min-nodes 3 \
  --max-nodes 10 \
  --enable-autorepair \
  --enable-autoupgrade

# Configure kubectl
gcloud container clusters get-credentials trading-prod --region us-central1
```

### 2. Deploy to Kubernetes

```bash
# Step 1: Create namespace
kubectl apply -f k8s/namespace.yml

# Step 2: Create secrets (⚠️  replace placeholders first!)
# Copy template and edit with actual values
cp k8s/secrets-template.yml k8s/secrets.yml
# Edit k8s/secrets.yml with base64-encoded values
kubectl apply -f k8s/secrets.yml
rm k8s/secrets.yml  # Delete immediately!

# Step 3: Create ConfigMap
kubectl apply -f k8s/configmap.yml

# Step 4: Create storage
kubectl apply -f k8s/storage.yml

# Step 5: Deploy application
kubectl apply -f k8s/deployment.yml

# Step 6: Verify deployment
kubectl get pods -n trading
kubectl get svc -n trading
kubectl describe deployment trading-system -n trading
```

### 3. Verify Deployment

```bash
# Check pod status
kubectl get pods -n trading -w

# View logs
kubectl logs -f deployment/trading-system -n trading

# Check resource usage
kubectl top pods -n trading

# Get service endpoint
kubectl get svc trading-system-service -n trading

# Port forward for testing
kubectl port-forward svc/trading-system-service 8000:80 -n trading
# Access: http://localhost:8000
```

### 4. Horizontal Pod Autoscaling

The HPA is configured to:
- Min replicas: 3
- Max replicas: 10
- Scale up: When CPU > 70% or Memory > 80%
- Scale down: Gradual (5min cooldown)

```bash
# Check HPA status
kubectl get hpa -n trading

# View HPA details
kubectl describe hpa trading-system-hpa -n trading

# Manual scaling (overrides HPA temporarily)
kubectl scale deployment trading-system --replicas=5 -n trading
```

---

## CI/CD Pipeline

### GitHub Actions Workflow

The CI/CD pipeline (`.github/workflows/ci.yml`) automatically:

1. **On Pull Request:**
   - Runs linters (Black, isort, Flake8)
   - Executes unit tests on multiple Python versions
   - Performs security scans
   - Builds Docker image
   - Runs integration tests

2. **On Push to `develop`:**
   - All PR checks
   - Deploys to staging environment
   - Runs smoke tests

3. **On Push to `main` with tag:**
   - All checks
   - Deploys to production with canary (10% traffic)
   - Waits 10 minutes for validation
   - Rolls out to 100%
   - Creates GitHub release

### Manual Deployment

```bash
# Tag new version
git tag -a v3.0.1 -m "Release 3.0.1: Bug fixes"
git push origin v3.0.1

# Monitor CI/CD pipeline
# GitHub Actions will automatically deploy

# If needed, rollback
kubectl rollout undo deployment/trading-system -n trading

# Check rollout status
kubectl rollout status deployment/trading-system -n trading
```

### Canary Deployment

For zero-downtime deployments with gradual rollout:

```bash
# Update image to new version (10% traffic)
kubectl set image deployment/trading-system \
  trading-system=trading-system:v3.0.1 -n trading

# Monitor canary
kubectl get pods -n trading -l version=v3.0.1

# If successful, scale up
# (or rollback if issues detected)
kubectl rollout undo deployment/trading-system -n trading
```

---

## Monitoring & Observability

### Prometheus Metrics

Metrics are exposed on port 9090 at `/metrics`:

```bash
# Access Prometheus UI
kubectl port-forward svc/prometheus 9091:9090 -n trading
# Open: http://localhost:9091

# Key metrics to monitor:
# - trading_total_pnl: Total P&L
# - trading_trades_total: Trade count
# - trading_api_request_duration_seconds: API latency
# - trading_circuit_breaker_state: Circuit breaker status
```

### Grafana Dashboards

```bash
# Access Grafana
kubectl port-forward svc/grafana 3000:3000 -n trading
# Open: http://localhost:3000
# Default credentials: admin/admin

# Import dashboards from:
# infrastructure/grafana/dashboards/
```

### Logs

```bash
# View real-time logs
kubectl logs -f deployment/trading-system -n trading

# View logs from all pods
kubectl logs -l app=trading-system -n trading --tail=100

# Search logs
kubectl logs deployment/trading-system -n trading | grep ERROR

# Export logs
kubectl logs deployment/trading-system -n trading > trading.log
```

### Health Checks

```bash
# Check liveness
kubectl exec -it deployment/trading-system -n trading -- \
  python -c "import sys; sys.exit(0)"

# Check readiness
curl http://<service-ip>/health
```

---

## Security Best Practices

### 1. Secrets Management

**❌ Never commit secrets to Git!**

Use one of these approaches:

#### Option A: Kubernetes Secrets (Basic)

```bash
# Create secret from command line
kubectl create secret generic trading-secrets \
  --from-literal=api-key=YOUR_API_KEY \
  --from-literal=access-token=YOUR_TOKEN \
  --from-literal=encryption-key=$(openssl rand -base64 32) \
  -n trading
```

#### Option B: Sealed Secrets (Better)

```bash
# Install sealed-secrets controller
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.0/controller.yaml

# Create sealed secret
kubeseal -f secrets.yml -w sealed-secrets.yml
kubectl apply -f sealed-secrets.yml
```

#### Option C: External Secrets (Best)

Integrate with AWS Secrets Manager, Google Secret Manager, or HashiCorp Vault.

### 2. Network Security

```bash
# Apply network policies
kubectl apply -f k8s/namespace.yml  # Includes NetworkPolicy

# Verify policies
kubectl get networkpolicies -n trading
```

### 3. Pod Security

- Run as non-root user (UID 1000)
- Read-only root filesystem
- Drop all capabilities
- Use security contexts

### 4. Image Security

```bash
# Scan image for vulnerabilities
docker scan trading-system:v3.0

# Or use Trivy
trivy image trading-system:v3.0
```

---

## Troubleshooting

### Common Issues

#### 1. Pod Not Starting

```bash
# Check pod events
kubectl describe pod <pod-name> -n trading

# Common causes:
# - Image pull errors: Check image name and registry credentials
# - Resource limits: Increase CPU/memory in deployment.yml
# - Failed health checks: Check liveness/readiness probes
```

#### 2. Out of Memory (OOM)

```bash
# Check memory usage
kubectl top pods -n trading

# Solutions:
# - Increase memory limits in deployment.yml
# - Enable HPA to scale horizontally
# - Optimize ML model loading
```

#### 3. High Latency

```bash
# Check API metrics
kubectl exec -it deployment/trading-system -n trading -- \
  curl http://localhost:9090/metrics | grep latency

# Solutions:
# - Scale up replicas
# - Check network policies
# - Optimize database queries
# - Enable Redis caching
```

#### 4. Cannot Connect to Zerodha API

```bash
# Check secrets
kubectl get secret trading-secrets -n trading -o yaml

# Check network policies
kubectl get networkpolicy -n trading

# Verify egress is allowed on port 443
```

### Debug Commands

```bash
# Get shell in pod
kubectl exec -it deployment/trading-system -n trading -- /bin/bash

# Copy files from pod
kubectl cp trading/<pod-name>:/app/logs/trading.log ./trading.log

# Check resource quotas
kubectl describe resourcequota -n trading

# View events
kubectl get events -n trading --sort-by='.lastTimestamp'
```

---

## Performance Optimization

### 1. Resource Tuning

```yaml
# Adjust based on monitoring data
resources:
  requests:
    memory: "1Gi"      # Guaranteed
    cpu: "500m"
  limits:
    memory: "4Gi"      # Maximum
    cpu: "2000m"
```

### 2. Autoscaling Configuration

```bash
# Tune HPA based on actual usage
kubectl edit hpa trading-system-hpa -n trading

# Adjust:
# - averageUtilization thresholds
# - scaleUp/scaleDown policies
# - stabilizationWindowSeconds
```

### 3. Storage Performance

```yaml
# Use SSD for models and state
storageClassName: fast-ssd  # AWS: gp3, GCP: pd-ssd, Azure: Premium_LRS
```

---

## Disaster Recovery

### 1. Backup Strategy

```bash
# Backup PVCs
kubectl get pvc -n trading
# Use Velero or cloud-native backup solutions

# Backup secrets and ConfigMaps
kubectl get secret,configmap -n trading -o yaml > backup.yml
```

### 2. Restore Procedure

```bash
# Restore from backup
kubectl apply -f backup.yml

# Verify restoration
kubectl get all -n trading
```

### 3. High Availability

- Multi-zone deployment
- Regular backups
- Disaster recovery testing
- Monitoring and alerting

---

## Cost Optimization

### 1. Right-Sizing

```bash
# Monitor actual usage
kubectl top pods -n trading

# Adjust requests/limits accordingly
```

### 2. Spot Instances (AWS)

```bash
# Use spot instances for non-critical workloads
# Configure node groups with mixed instance types
```

### 3. Storage Optimization

```bash
# Clean up old logs
kubectl exec deployment/trading-system -n trading -- \
  find /app/logs -type f -mtime +30 -delete

# Compress models
kubectl exec deployment/trading-system -n trading -- \
  gzip /app/models/*.pkl
```

---

## Support & Resources

- **Documentation**: See `Documentation/` directory
- **Issues**: GitHub Issues
- **Logs**: Check `/app/logs/` in containers
- **Metrics**: Prometheus at `:9090/metrics`

---

## Appendix: Quick Reference

### Essential Commands

```bash
# Deploy
kubectl apply -f k8s/

# Status
kubectl get all -n trading

# Logs
kubectl logs -f deployment/trading-system -n trading

# Scale
kubectl scale deployment trading-system --replicas=5 -n trading

# Rollback
kubectl rollout undo deployment/trading-system -n trading

# Delete
kubectl delete -f k8s/
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `ZERODHA_API_KEY` | Zerodha API key | ✅ |
| `ZERODHA_ACCESS_TOKEN` | Zerodha access token | ✅ |
| `ENCRYPTION_KEY` | 32-byte encryption key | ✅ |
| `DEVELOPMENT_MODE` | Enable dev mode | ❌ (default: false) |
| `LOG_LEVEL` | Logging level | ❌ (default: INFO) |
| `REDIS_HOST` | Redis hostname | ❌ (default: redis-service) |

---

**Last Updated:** October 22, 2025
**Version:** 3.0
