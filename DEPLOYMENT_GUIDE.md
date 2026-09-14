# Cloud Deployment Guide

## AWS Setup
1. **ECS Cluster**
   ```bash
   aws ecs create-cluster --cluster-name healthcare-cluster
   ```
2. **RDS PostgreSQL**
   - Enable Multi-AZ deployment
   - Set storage autoscaling
   - Enable automated backups

3. **ElastiCache Redis**
   ```bash
   aws elasticache create-cache-cluster \
     --cache-cluster-id healthcare-redis \
     --engine redis \
     --cache-node-type cache.t3.micro
   ```

## Docker Configuration
```dockerfile
# Production Dockerfile
FROM python:3.11-slim

RUN pip install gunicorn==20.1.0
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker"]
```

## SSL Configuration
1. Obtain Let's Encrypt certificate:
   ```bash
   certbot certonly --standalone -d api.healthcare.com
   ```
2. Nginx config:
   ```nginx
   ssl_certificate /etc/letsencrypt/live/api.healthcare.com/fullchain.pem;
   ssl_certificate_key /etc/letsencrypt/live/api.healthcare.com/privkey.pem;
   ```

## Monitoring
- Liveness/readiness endpoint: `/health` (a Prometheus `/metrics` endpoint is not implemented yet)
- CloudWatch alarms for:
  - Database connection pool usage
  - API error rate (>5%)
  - CPU utilization (>75%)
