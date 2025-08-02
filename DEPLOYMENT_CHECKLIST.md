# ✅ Production Deployment Checklist

## Pre-Deployment Setup

### 📋 Required Updates Before Deployment

1. **Environment Variables (.env file)**
   - [ ] Update `DATABASE_PASSWORD` with secure password
   - [ ] Update `REDIS_PASSWORD` with secure password  
   - [ ] Add real `OPENAI_API_KEY`
   - [ ] Add real `GOOGLE_MAPS_API_KEY`
   - [ ] Add real `OPENWEATHER_API_KEY`
   - [ ] Generate new `SECRET_KEY` (50+ characters)
   - [ ] Update `ALLOWED_HOSTS` with your domain
   - [ ] Update `DOMAIN_NAME` with your domain
   - [ ] Update `ACME_EMAIL` with your email

2. **Deployment Script (deploy-to-ec2.sh)**
   - [ ] Update `EC2_IP` with your actual EC2 IP address
   - [ ] Update `KEY_FILE` path to your SSH key
   - [ ] Verify `EC2_USER` is correct (usually ubuntu)

3. **Docker Compose SSL (docker-compose.prod.yml)**
   - [ ] Update certbot command domain (line 183)
   - [ ] Update certbot email (line 183)
   - [ ] Remove `--staging` flag for production SSL

## AWS EC2 Setup

### 🖥️ EC2 Instance Requirements
- [ ] **Instance Type**: t3.large or larger (2+ vCPU, 8+ GB RAM)
- [ ] **OS**: Ubuntu 22.04 LTS
- [ ] **Storage**: 30GB+ GP3 SSD
- [ ] **Security Groups**:
  - [ ] Port 22 (SSH): Your IP only
  - [ ] Port 80 (HTTP): 0.0.0.0/0
  - [ ] Port 443 (HTTPS): 0.0.0.0/0
  - [ ] Port 5555 (Flower): Your IP only (optional)

### 🌐 DNS Configuration
- [ ] Create A record: `your-domain.com` → `EC2_IP`
- [ ] Create A record: `www.your-domain.com` → `EC2_IP`
- [ ] Verify DNS propagation: `nslookup your-domain.com`

## Deployment Process

### 🚀 Step-by-Step Deployment

1. **Prepare Local Environment**
   ```bash
   # Make deployment script executable
   chmod +x deploy-to-ec2.sh
   
   # Test connection to EC2
   ssh -i ~/.ssh/your-key.pem ubuntu@YOUR_EC2_IP "echo 'Connection successful'"
   ```
   - [ ] SSH connection successful

2. **Run Deployment**
   ```bash
   # Deploy application
   ./deploy-to-ec2.sh
   ```
   - [ ] Deployment script completed without errors
   - [ ] All Docker containers started successfully

3. **Initial Application Setup**
   ```bash
   # SSH into server
   ssh -i ~/.ssh/your-key.pem ubuntu@YOUR_EC2_IP
   cd /home/ubuntu/portfolio_app_production
   
   # Run database migrations
   docker-compose -f docker-compose.prod.yml exec web python manage.py migrate
   
   # Create superuser
   docker-compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
   
   # Collect static files
   docker-compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput
   ```
   - [ ] Database migrations completed
   - [ ] Superuser created
   - [ ] Static files collected

4. **SSL Certificate Setup**
   ```bash
   # Set up SSL certificates (staging first)
   docker-compose -f docker-compose.prod.yml --profile ssl-setup up certbot
   
   # If staging works, edit docker-compose.prod.yml:
   # - Remove --staging flag
   # - Update domain and email
   # Then run production SSL:
   docker-compose -f docker-compose.prod.yml --profile ssl-setup up certbot
   
   # Restart nginx with SSL
   docker-compose -f docker-compose.prod.yml restart nginx
   ```
   - [ ] Staging SSL certificate obtained
   - [ ] Production SSL certificate obtained
   - [ ] Nginx restarted with SSL

## Verification Tests

### 🧪 Health Checks

1. **Service Status**
   ```bash
   # Check all services are running
   docker-compose -f docker-compose.prod.yml ps
   ```
   - [ ] All services show "Up" status
   - [ ] Health checks passing

2. **Application Access**
   ```bash
   # Test HTTP redirect to HTTPS
   curl -I http://your-domain.com
   
   # Test HTTPS access
   curl -I https://your-domain.com
   
   # Test admin panel
   curl -I https://your-domain.com/admin/
   
   # Test API health
   curl -I https://your-domain.com/health/
   ```
   - [ ] HTTP redirects to HTTPS (301 response)
   - [ ] HTTPS returns 200 OK
   - [ ] Admin panel accessible
   - [ ] Health endpoint returns OK

3. **SSL Verification**
   ```bash
   # Check SSL certificate
   openssl s_client -connect your-domain.com:443 -servername your-domain.com
   ```
   - [ ] SSL certificate valid
   - [ ] Certificate matches domain
   - [ ] No SSL errors in browser

4. **Security Headers**
   ```bash
   # Check security headers
   curl -I https://your-domain.com
   ```
   - [ ] HSTS header present
   - [ ] X-Frame-Options present
   - [ ] X-Content-Type-Options present
   - [ ] X-XSS-Protection present

### 🔍 Application Testing

1. **Core Functionality**
   - [ ] Home page loads correctly
   - [ ] Restaurant list page works
   - [ ] Restaurant detail pages work
   - [ ] Search functionality works
   - [ ] Admin panel accessible

2. **Background Tasks**
   ```bash
   # Test Celery worker
   docker-compose -f docker-compose.prod.yml exec celery celery -A portfolio_project inspect ping
   
   # Test scheduled tasks
   docker-compose -f docker-compose.prod.yml exec web python manage.py task_management --action status
   ```
   - [ ] Celery workers responding
   - [ ] Scheduled tasks configured
   - [ ] Task monitoring accessible (Flower)

3. **Cache Performance**
   ```bash
   # Test cache system
   docker-compose -f docker-compose.prod.yml exec web python manage.py cache_management --action health
   ```
   - [ ] Redis cache working
   - [ ] Cache hit rates reasonable
   - [ ] No cache errors

4. **Database Performance**
   ```bash
   # Test database connection
   docker-compose -f docker-compose.prod.yml exec web python manage.py check --database default
   ```
   - [ ] Database connection healthy
   - [ ] No migration issues
   - [ ] Query performance acceptable

## Post-Deployment Setup

### 🛠️ Production Configuration

1. **Monitoring Setup**
   - [ ] Set up log rotation
   - [ ] Configure error alerting
   - [ ] Monitor disk space usage
   - [ ] Set up backup automation

2. **Performance Optimization**
   - [ ] Enable CloudFlare (optional)
   - [ ] Configure CDN for static files
   - [ ] Set up database connection pooling
   - [ ] Optimize Docker resource limits

3. **Security Hardening**
   - [ ] Disable root login
   - [ ] Configure fail2ban
   - [ ] Set up automatic security updates
   - [ ] Regular security audits

### 📊 Ongoing Maintenance

1. **Daily Checks**
   - [ ] Monitor application logs
   - [ ] Check system resources
   - [ ] Verify backup completion
   - [ ] Review security alerts

2. **Weekly Tasks**
   - [ ] Update system packages
   - [ ] Review performance metrics
   - [ ] Check SSL certificate expiry
   - [ ] Database maintenance

3. **Monthly Tasks**
   - [ ] Security audit
   - [ ] Performance optimization review
   - [ ] Backup integrity testing
   - [ ] Disaster recovery testing

## Emergency Procedures

### 🚨 Rollback Process
```bash
# If deployment fails, rollback:
cd /home/ubuntu/portfolio_app_production
docker-compose -f docker-compose.prod.yml down
# Restore from backup
docker-compose -f docker-compose.prod.yml up -d
```

### 📞 Contact Information
- **Technical Support**: [Your contact info]
- **DNS Provider**: [Provider contact info]
- **SSL Certificate**: Let's Encrypt (auto-renewal)
- **Hosting**: AWS EC2

---

## 🎉 Deployment Complete!

Once all items are checked off, your production deployment is complete and ready for users!

**Live URLs:**
- Application: https://your-domain.com
- Admin Panel: https://your-domain.com/admin/
- Task Monitor: https://your-domain.com:5555 (if enabled)
- Health Check: https://your-domain.com/health/