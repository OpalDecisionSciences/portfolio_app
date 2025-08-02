# 🚀 Production Deployment Guide - Portfolio Restaurant App

## Overview
This guide will walk you through deploying your restaurant discovery application to AWS EC2 with SSL certificates, production security, and full monitoring.

## Prerequisites
- AWS EC2 instance (t3.large or larger recommended)
- Domain name pointed to your EC2 IP
- SSH key pair for EC2 access

## 📋 Pre-Deployment Checklist

### 1. Update Environment Variables
Edit `.env` file and replace placeholder values:

```bash
# Update these required fields:
DATABASE_PASSWORD=your-secure-database-password-here
REDIS_PASSWORD=your-redis-password-here
OPENAI_API_KEY=your-actual-openai-api-key
GOOGLE_MAPS_API_KEY=your-google-maps-api-key
OPENWEATHER_API_KEY=your-openweather-api-key
SECRET_KEY=generate-new-secret-key-here
```

### 2. Update Domain Configuration
In `.env`, update:
```bash
ALLOWED_HOSTS=your-domain.com,www.your-domain.com,YOUR_EC2_IP
DOMAIN_NAME=www.your-domain.com
ACME_EMAIL=your-email@domain.com
```

### 3. Update Deployment Script
Edit `deploy-to-ec2.sh`:
```bash
EC2_IP="YOUR_ACTUAL_EC2_IP"
KEY_FILE="~/.ssh/your-actual-key-file.pem"
```

## 🏗️ Infrastructure Files Validation

All infrastructure files are already created and validated:

✅ **Docker Configuration**
- `docker-compose.prod.yml` - Production services with health checks
- `docker-compose.celery.yml` - Background task processing
- `docker/Dockerfile.django.prod` - Optimized Django container
- `docker/Dockerfile.nginx` - Nginx reverse proxy
- `docker/Dockerfile.rag` - RAG service container

✅ **Nginx Configuration**
- `docker/nginx.prod.conf` - Production nginx with SSL, rate limiting, security headers
- HTTP to HTTPS redirect configured
- Let's Encrypt integration ready

✅ **Environment Configuration**
- `.env` - Production environment variables with security settings
- SSL, HSTS, and security headers configured

✅ **Deployment Scripts**
- `deploy-to-ec2.sh` - Automated deployment to EC2
- SSL certificate automation included

## 🚀 Deployment Steps

### Step 1: Launch EC2 Instance
1. **Launch Instance:**
   ```bash
   # Recommended: t3.large (2 vCPU, 8GB RAM)
   # OS: Ubuntu 22.04 LTS
   # Storage: 30GB+ GP3
   # Security Groups: HTTP (80), HTTPS (443), SSH (22)
   ```

2. **Update Security Groups:**
   - Port 80 (HTTP): 0.0.0.0/0
   - Port 443 (HTTPS): 0.0.0.0/0
   - Port 22 (SSH): Your IP only
   - Optional Port 5555 (Flower): Your IP only

### Step 2: Update DNS
Point your domain to the EC2 IP:
```bash
# DNS A Records:
your-domain.com -> EC2_IP_ADDRESS
www.your-domain.com -> EC2_IP_ADDRESS
```

### Step 3: Deploy Application
```bash
# Make deployment script executable
chmod +x deploy-to-ec2.sh

# Run deployment
./deploy-to-ec2.sh
```

### Step 4: Set Up SSL Certificates
SSH into your server and run:
```bash
# Connect to EC2
ssh -i ~/.ssh/your-key.pem ubuntu@YOUR_EC2_IP

# Navigate to app directory
cd /home/ubuntu/portfolio_app_production

# Set up SSL certificates (staging first for testing)
docker-compose -f docker-compose.prod.yml --profile ssl-setup up certbot

# If staging works, get production certificates:
# Edit docker-compose.prod.yml and remove --staging flag
# Then run:
docker-compose -f docker-compose.prod.yml --profile ssl-setup up certbot

# Restart nginx with SSL
docker-compose -f docker-compose.prod.yml restart nginx
```

### Step 5: Verify Deployment
```bash
# Check all services are running
docker-compose -f docker-compose.prod.yml ps

# Check logs
docker-compose -f docker-compose.prod.yml logs -f

# Test endpoints
curl -I https://your-domain.com/health/
curl -I https://your-domain.com/admin/
```

## 🔧 Production Services Architecture

Your production deployment includes:

### Core Services
- **Django Web App** (`web`): Main application on port 8000
- **PostgreSQL** (`db`): Database with pgvector extension
- **Redis** (`redis`): Caching and session storage
- **RAG Service** (`rag`): AI search service on port 8001
- **Nginx** (`nginx`): Reverse proxy on ports 80/443

### Background Processing
- **Celery Worker** (`celery`): Background task processing
- **Celery Beat** (`celery-beat`): Scheduled task execution
- **Flower** (`flower`): Task monitoring (optional)

### Scheduled Tasks (via Celery Beat)
- **cleanup-old-images**: Daily at 2 AM
- **process-pending-ai-images**: Every 4 hours
- **update-recent-embeddings**: Every 6 hours  
- **warm-restaurant-cache**: Every hour
- **system-health-check**: Every 30 minutes

## 📊 Monitoring & Maintenance

### Health Checks
```bash
# System health
docker-compose -f docker-compose.prod.yml exec web python manage.py check --deploy

# Cache management
docker-compose -f docker-compose.prod.yml exec web python manage.py cache_management --action health

# Task monitoring
docker-compose -f docker-compose.prod.yml exec web python manage.py task_management --action status

# Database backup
docker-compose -f docker-compose.prod.yml exec db pg_dump -U portfolio_user portfolio_prod > backup.sql
```

### Log Monitoring
```bash
# Application logs
docker-compose -f docker-compose.prod.yml logs -f web

# Nginx logs
docker-compose -f docker-compose.prod.yml logs -f nginx

# Celery logs
docker-compose -f docker-compose.prod.yml logs -f celery

# System logs
sudo journalctl -u docker -f
```

### Performance Monitoring
- **Flower Dashboard**: `https://your-domain.com:5555` (if enabled)
- **Admin Panel**: `https://your-domain.com/admin/`
- **Health Endpoint**: `https://your-domain.com/health/`

## 🔒 Security Features Enabled

### SSL/TLS Security
- ✅ Let's Encrypt SSL certificates
- ✅ HTTP to HTTPS redirect
- ✅ HSTS headers (31536000 seconds)
- ✅ SSL session caching

### Application Security
- ✅ Django security middleware
- ✅ CSRF protection
- ✅ XSS protection headers
- ✅ Content type nosniff
- ✅ Frame options sameorigin

### Rate Limiting
- ✅ API endpoints: 10 requests/second
- ✅ General pages: 1 request/second
- ✅ Admin panel: 5 requests/burst

### Infrastructure Security
- ✅ Non-root user in containers
- ✅ Read-only filesystem mounts where possible
- ✅ Security groups configured
- ✅ Secret management via environment variables

## 🛠️ Troubleshooting

### Common Issues

1. **SSL Certificate Issues**:
   ```bash
   # Check certificate status
   docker-compose -f docker-compose.prod.yml exec certbot certbot certificates
   
   # Renew certificates
   docker-compose -f docker-compose.prod.yml exec certbot certbot renew
   ```

2. **Database Connection Issues**:
   ```bash
   # Check database health
   docker-compose -f docker-compose.prod.yml exec db pg_isready -U portfolio_user
   
   # View database logs
   docker-compose -f docker-compose.prod.yml logs db
   ```

3. **Application Not Starting**:
   ```bash
   # Check Django migrations
   docker-compose -f docker-compose.prod.yml exec web python manage.py showmigrations
   
   # Run migrations
   docker-compose -f docker-compose.prod.yml exec web python manage.py migrate
   
   # Collect static files
   docker-compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput
   ```

4. **Background Tasks Not Running**:
   ```bash
   # Check Celery worker status
   docker-compose -f docker-compose.prod.yml exec celery celery -A portfolio_project inspect ping
   
   # Check scheduled tasks
   docker-compose -f docker-compose.prod.yml exec celery-beat celery -A portfolio_project inspect scheduled
   ```

### Performance Optimization

1. **Database Performance**:
   ```bash
   # Analyze slow queries
   docker-compose -f docker-compose.prod.yml exec web python manage.py shell
   # Then run: from django.db import connection; print(connection.queries)
   ```

2. **Cache Performance**:
   ```bash
   # Check cache statistics
   docker-compose -f docker-compose.prod.yml exec web python manage.py cache_management --action stats --format json
   ```

3. **Memory Usage**:
   ```bash
   # Monitor container resources
   docker stats
   ```

## 🔄 Updates & Maintenance

### Deploying Updates
```bash
# 1. Update code locally and test
# 2. Run deployment script again
./deploy-to-ec2.sh

# 3. Or manually update on server:
ssh -i ~/.ssh/your-key.pem ubuntu@YOUR_EC2_IP
cd /home/ubuntu/portfolio_app_production
git pull  # if using git
docker-compose -f docker-compose.prod.yml build --no-cache
docker-compose -f docker-compose.prod.yml up -d
```

### Certificate Renewal
```bash
# Certificates auto-renew, but to manually renew:
docker-compose -f docker-compose.prod.yml exec certbot certbot renew --dry-run
docker-compose -f docker-compose.prod.yml exec certbot certbot renew
docker-compose -f docker-compose.prod.yml restart nginx
```

### Database Backup
```bash
# Create backup
docker-compose -f docker-compose.prod.yml exec db pg_dump -U portfolio_user -h localhost portfolio_prod > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore backup
docker-compose -f docker-compose.prod.yml exec -T db psql -U portfolio_user -h localhost portfolio_prod < backup_file.sql
```

## 🎯 Final Checklist

Before going live:

- [ ] Domain DNS pointing to EC2 IP
- [ ] SSL certificates installed and working
- [ ] All environment variables configured
- [ ] Database migrations applied
- [ ] Static files collected
- [ ] Admin user created
- [ ] Health checks passing
- [ ] Backup strategy in place
- [ ] Monitoring configured
- [ ] Rate limiting tested
- [ ] Security headers verified

## 📞 Support

If you run into issues:

1. Check the troubleshooting section above
2. Review Docker logs: `docker-compose -f docker-compose.prod.yml logs`
3. Check system resources: `htop`, `df -h`, `free -m`
4. Verify network connectivity and DNS resolution

Your production-ready restaurant discovery application is now deployed with enterprise-level security, monitoring, and scalability! 🎉