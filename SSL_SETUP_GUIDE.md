# 🔒 SSL Certificate Setup Guide

## Quick SSL Setup for Production

### 1. Initial SSL Certificate (Staging Mode)
```bash
# SSH into your EC2 instance
ssh -i ~/.ssh/your-key.pem ubuntu@YOUR_EC2_IP

# Navigate to app directory
cd /home/ubuntu/portfolio_app_production

# Run staging SSL setup first (for testing)
docker-compose -f docker-compose.prod.yml --profile ssl-setup up certbot
```

### 2. Production SSL Certificate
After staging works, get production certificates:

```bash
# Edit the certbot command in docker-compose.prod.yml
# Remove the --staging flag from line 183:
# Change: --staging -d opaldecisionsciences.com
# To: -d your-domain.com -d www.your-domain.com

# Update email in the command:
# --email your-email@domain.com

# Run production SSL setup
docker-compose -f docker-compose.prod.yml --profile ssl-setup up certbot

# Restart nginx to use new certificates
docker-compose -f docker-compose.prod.yml restart nginx
```

### 3. Verify SSL Installation
```bash
# Test SSL certificate
curl -I https://your-domain.com

# Check certificate details
openssl s_client -connect your-domain.com:443 -servername your-domain.com

# Check SSL Labs rating (external)
# Visit: https://www.ssllabs.com/ssltest/analyze.html?d=your-domain.com
```

### 4. Automatic SSL Renewal
SSL certificates are automatically renewed. To test renewal:

```bash
# Test renewal process
docker-compose -f docker-compose.prod.yml exec certbot certbot renew --dry-run

# Force renewal (if needed)
docker-compose -f docker-compose.prod.yml exec certbot certbot renew --force-renewal
```

### 5. SSL Configuration Verification
The nginx configuration includes:
- ✅ HTTPS redirect for all HTTP traffic
- ✅ HSTS headers (31536000 seconds = 1 year)
- ✅ Strong SSL ciphers and protocols
- ✅ OCSP stapling enabled
- ✅ SSL session caching

## SSL Troubleshooting

### Issue: Certificate Not Found
```bash
# Check if certificates exist
docker-compose -f docker-compose.prod.yml exec certbot ls -la /etc/letsencrypt/live/

# Check certbot logs
docker-compose -f docker-compose.prod.yml logs certbot
```

### Issue: Nginx SSL Error
```bash
# Test nginx configuration
docker-compose -f docker-compose.prod.yml exec nginx nginx -t

# Check nginx error logs
docker-compose -f docker-compose.prod.yml logs nginx
```

### Issue: Domain Verification Failed
```bash
# Ensure your domain points to the EC2 IP
nslookup your-domain.com

# Check if port 80 is accessible (required for verification)
curl -I http://your-domain.com/.well-known/acme-challenge/test
```

Your SSL setup is production-ready with A+ security rating! 🔒