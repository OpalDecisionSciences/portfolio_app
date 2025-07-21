#!/bin/bash

# Production Deployment Script for AWS EC2
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DOMAIN_NAME=${1:-"your-domain.com"}
EMAIL=${2:-"your-email@domain.com"}
BACKUP_ENABLED=${3:-"true"}

echo -e "${BLUE}=== Portfolio App Production Deployment ===${NC}"
echo -e "${YELLOW}Domain: $DOMAIN_NAME${NC}"
echo -e "${YELLOW}Email: $EMAIL${NC}"

# Function to print status
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root for security reasons"
   exit 1
fi

# Check if .env.prod exists
if [ ! -f ".env.prod" ]; then
    print_error ".env.prod file not found!"
    print_status "Creating .env.prod from template..."
    cp .env.prod.example .env.prod
    print_warning "Please edit .env.prod with your production values before continuing"
    read -p "Press enter after editing .env.prod to continue..."
fi

# Update system packages
print_status "Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    print_status "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
fi

# Install Docker Compose if not present
if ! command -v docker-compose &> /dev/null; then
    print_status "Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# Create necessary directories
print_status "Creating directories..."
mkdir -p logs/nginx ssl ssl-challenges

# Set up log rotation
print_status "Setting up log rotation..."
sudo tee /etc/logrotate.d/portfolio-app > /dev/null <<EOF
/home/$USER/portfolio_app/logs/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 $USER $USER
    postrotate
        docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload
    endscript
}
EOF

# Update domain in nginx config
print_status "Updating domain configuration..."
sed -i "s/your-domain.com/$DOMAIN_NAME/g" docker/nginx.prod.conf
sed -i "s/your-email@domain.com/$EMAIL/g" docker-compose.prod.yml

# Build and start services (without SSL first)
print_status "Building Docker images..."
docker-compose -f docker-compose.prod.yml build

print_status "Starting services for SSL setup..."
# Temporarily use HTTP-only nginx config for SSL verification
cp docker/nginx.prod.conf docker/nginx.prod.conf.backup
cat > docker/nginx.temp.conf << EOF
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    server {
        listen 80;
        server_name $DOMAIN_NAME www.$DOMAIN_NAME;

        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        location / {
            proxy_pass http://web:8000;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
        }
    }
}
EOF

# Update docker-compose to use temporary nginx config
cp docker-compose.prod.yml docker-compose.prod.yml.backup
sed -i 's|nginx.prod.conf|nginx.temp.conf|g' docker-compose.prod.yml

# Start services
docker-compose -f docker-compose.prod.yml up -d

# Wait for services to be ready
print_status "Waiting for services to start..."
sleep 30

# Setup SSL with Let's Encrypt
print_status "Setting up SSL certificates..."
docker-compose -f docker-compose.prod.yml --profile ssl-setup run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email $EMAIL \
    --agree-tos \
    --no-eff-email \
    --force-renewal \
    -d $DOMAIN_NAME \
    -d www.$DOMAIN_NAME

# Restore original configurations
print_status "Applying SSL configuration..."
cp docker/nginx.prod.conf.backup docker/nginx.prod.conf
cp docker-compose.prod.yml.backup docker-compose.prod.yml

# Clean up temporary files
rm docker/nginx.temp.conf docker/nginx.prod.conf.backup docker-compose.prod.yml.backup

# Restart with SSL configuration
print_status "Restarting services with SSL..."
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d

# Set up SSL certificate renewal
print_status "Setting up SSL certificate auto-renewal..."
sudo tee /etc/cron.d/certbot-renewal > /dev/null <<EOF
0 12 * * * root cd /home/$USER/portfolio_app && docker-compose -f docker-compose.prod.yml run --rm certbot renew --quiet && docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload
EOF

# Set up monitoring and alerting (optional)
if [ "$BACKUP_ENABLED" = "true" ]; then
    print_status "Setting up database backups..."
    mkdir -p backups
    
    sudo tee /etc/cron.d/portfolio-backup > /dev/null <<EOF
0 2 * * * root cd /home/$USER/portfolio_app && docker-compose -f docker-compose.prod.yml exec -T db pg_dump -U \$POSTGRES_USER \$POSTGRES_DB > backups/backup_\$(date +\%Y\%m\%d_\%H\%M\%S).sql
0 3 * * 0 root find /home/$USER/portfolio_app/backups -name "*.sql" -type f -mtime +30 -delete
EOF
fi

# Install monitoring tools
print_status "Installing system monitoring..."
sudo apt-get install -y htop iotop nethogs

# Set up UFW firewall
print_status "Configuring firewall..."
sudo ufw --force enable
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Final health check
print_status "Performing health check..."
sleep 10

if curl -f -s http://localhost/health/ > /dev/null; then
    print_status "✅ Application is running successfully!"
else
    print_error "❌ Health check failed. Check logs with: docker-compose -f docker-compose.prod.yml logs"
fi

print_status "Deployment completed!"
echo -e "${GREEN}=== Next Steps ===${NC}"
echo -e "${YELLOW}1. Point your domain DNS A record to this server's IP address${NC}"
echo -e "${YELLOW}2. Test your application at https://$DOMAIN_NAME${NC}"
echo -e "${YELLOW}3. Monitor logs: docker-compose -f docker-compose.prod.yml logs -f${NC}"
echo -e "${YELLOW}4. Access admin at: https://$DOMAIN_NAME/admin/${NC}"
echo -e "${YELLOW}5. Monitor Celery tasks at: http://localhost:5555 (from server only)${NC}"

print_warning "Remember to:"
echo "- Update your .env.prod file with actual production values"
echo "- Configure your domain's DNS to point to this server"
echo "- Set up monitoring and alerting for production use"
echo "- Review and customize security settings"