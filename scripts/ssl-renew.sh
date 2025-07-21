#!/bin/bash

# SSL Certificate Renewal Script
set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Change to app directory
cd /home/$(whoami)/portfolio_app

print_status "Starting SSL certificate renewal..."

# Renew certificates
if docker-compose -f docker-compose.prod.yml run --rm certbot renew --quiet; then
    print_status "Certificate renewal check completed"
    
    # Reload nginx to use new certificates
    if docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload; then
        print_status "Nginx reloaded successfully"
    else
        print_error "Failed to reload Nginx"
        exit 1
    fi
    
    # Log successful renewal
    echo "$(date): SSL certificates renewed successfully" >> logs/ssl-renewal.log
    
else
    print_error "Certificate renewal failed"
    echo "$(date): SSL certificate renewal failed" >> logs/ssl-renewal.log
    exit 1
fi

print_status "SSL renewal process completed"