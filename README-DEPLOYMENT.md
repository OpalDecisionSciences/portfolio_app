# Production Deployment Guide for AWS EC2

This guide will help you deploy your Portfolio App to AWS EC2 with SSL, monitoring, and production-ready configurations.

## 📋 Prerequisites

- AWS EC2 instance (t3.medium or larger recommended)
- Domain name pointing to your EC2 instance
- SSH access to your EC2 instance
- Git installed on the server

## 🚀 Quick Deployment

### 1. Server Setup

```bash
# Connect to your EC2 instance
ssh -i your-key.pem ubuntu@your-ec2-ip

# Update system
sudo apt update && sudo apt upgrade -y

# Clone your repository
git clone https://github.com/your-username/portfolio_app.git
cd portfolio_app
```

### 2. Configure Environment

```bash
# Copy and edit production environment file
cp .env.prod.example .env.prod
nano .env.prod  # Edit with your production values
```

**Important environment variables to update:**
- `DOMAIN_NAME`: Your domain (e.g., example.com)
- `SECRET_KEY`: Generate a new secret key
- `POSTGRES_PASSWORD`: Strong database password
- `REDIS_PASSWORD`: Strong Redis password
- `EMAIL_*`: Email configuration for notifications
- `OPENAI_API_KEY`: Your OpenAI API key
- `GOOGLE_MAPS_API_KEY`: Your Google Maps API key

### 3. Run Deployment Script

```bash
# Make the script executable
chmod +x deploy.sh

# Run deployment (replace with your domain and email)
./deploy.sh your-domain.com your-email@domain.com
```

This script will:
- Install Docker and Docker Compose
- Set up SSL certificates with Let's Encrypt
- Configure Nginx reverse proxy
- Start all services in production mode
- Set up log rotation and backups
- Configure firewall settings

## 🔧 Manual Configuration

If you prefer manual setup or need to customize the deployment:

### 1. Build and Start Services

```bash
# Build production images
docker-compose -f docker-compose.prod.yml build

# Start services
docker-compose -f docker-compose.prod.yml up -d
```

### 2. SSL Certificate Setup

```bash
# Generate SSL certificates
docker-compose -f docker-compose.prod.yml --profile ssl-setup run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email your-email@domain.com \
    --agree-tos \
    --no-eff-email \
    -d your-domain.com \
    -d www.your-domain.com

# Restart with SSL
docker-compose -f docker-compose.prod.yml restart nginx
```

## 📁 File Structure

```
portfolio_app/
├── docker/
│   ├── Dockerfile.django.prod      # Production Django container
│   ├── nginx.prod.conf            # Production Nginx config
│   └── config/
│       └── redis.conf             # Redis production config
├── scripts/
│   ├── backup.sh                  # Database backup script
│   ├── restore.sh                 # Database restore script
│   └── ssl-renew.sh              # SSL renewal script
├── docker-compose.prod.yml        # Production services
├── .env.prod.example             # Environment template
├── deploy.sh                     # Automated deployment
└── README-DEPLOYMENT.md          # This file
```

## 🔍 Service Management

### Check Service Status
```bash
docker-compose -f docker-compose.prod.yml ps
```

### View Logs
```bash
# All services
docker-compose -f docker-compose.prod.yml logs

# Specific service
docker-compose -f docker-compose.prod.yml logs web
docker-compose -f docker-compose.prod.yml logs nginx
```

### Restart Services
```bash
# Restart all
docker-compose -f docker-compose.prod.yml restart

# Restart specific service
docker-compose -f docker-compose.prod.yml restart web
```

## 🗄️ Database Management

### Create Backup
```bash
./scripts/backup.sh
```

### Restore Database
```bash
./scripts/restore.sh backup_filename.sql.gz
```

### Run Migrations
```bash
docker-compose -f docker-compose.prod.yml exec web python manage.py migrate
```

## 🔒 SSL Management

### Renew Certificates
```bash
./scripts/ssl-renew.sh
```

### Check Certificate Status
```bash
docker-compose -f docker-compose.prod.yml run --rm certbot certificates
```

## 📊 Monitoring

### System Resources
```bash
# CPU and memory usage
htop

# Docker containers
docker stats

# Disk usage
df -h
```

### Application Monitoring
- **Celery Tasks**: http://your-domain.com:5555 (from server only)
- **Application Logs**: `logs/` directory
- **Nginx Logs**: `logs/nginx/` directory

## 🔧 Maintenance Tasks

### Update Application
```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d
```

### Scale Services
```bash
# Scale web workers
docker-compose -f docker-compose.prod.yml up -d --scale web=3

# Scale Celery workers
docker-compose -f docker-compose.prod.yml up -d --scale celery=2
```

## 🛡️ Security Features

### Implemented Security Measures
- **HTTPS/SSL**: Automatic SSL with Let's Encrypt
- **Firewall**: UFW configured for essential ports only
- **Rate Limiting**: Nginx rate limiting for API endpoints
- **Security Headers**: HSTS, XSS protection, content type nosniff
- **Non-root Containers**: Services run as non-root users
- **Secret Management**: Environment-based secrets
- **Database Security**: Strong passwords, limited connections

### Additional Security Recommendations
1. **Regular Updates**: Keep system and dependencies updated
2. **Monitoring**: Set up log monitoring and alerts
3. **Backup Strategy**: Regular automated backups
4. **Access Control**: Limit SSH access, use key-based authentication
5. **Vulnerability Scanning**: Regular security scans

## 🚨 Troubleshooting

### Common Issues

**Services won't start:**
```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs

# Check system resources
free -h
df -h
```

**SSL certificate issues:**
```bash
# Check certificate status
docker-compose -f docker-compose.prod.yml run --rm certbot certificates

# Manual renewal
./scripts/ssl-renew.sh
```

**Database connection errors:**
```bash
# Check database logs
docker-compose -f docker-compose.prod.yml logs db

# Test database connection
docker-compose -f docker-compose.prod.yml exec db psql -U $POSTGRES_USER -d $POSTGRES_DB
```

**High memory usage:**
```bash
# Check container memory usage
docker stats

# Restart services to clear memory
docker-compose -f docker-compose.prod.yml restart
```

## 📞 Support

For issues or questions:
1. Check the logs first: `docker-compose -f docker-compose.prod.yml logs`
2. Review this documentation
3. Check service status: `docker-compose -f docker-compose.prod.yml ps`
4. Ensure environment variables are correctly set in `.env.prod`

## 🔄 CI/CD Integration

For automated deployments, you can integrate with GitHub Actions or other CI/CD platforms:

```yaml
# Example GitHub Actions workflow
name: Deploy to Production
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to server
        uses: appleboy/ssh-action@v0.1.5
        with:
          host: ${{ secrets.HOST }}
          username: ${{ secrets.USERNAME }}
          key: ${{ secrets.KEY }}
          script: |
            cd /home/ubuntu/portfolio_app
            git pull origin main
            docker-compose -f docker-compose.prod.yml build
            docker-compose -f docker-compose.prod.yml up -d
```