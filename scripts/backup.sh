#!/bin/bash

# Database Backup Script
set -e

# Configuration
BACKUP_DIR="/home/$(whoami)/portfolio_app/backups"
DATE=$(date +"%Y%m%d_%H%M%S")
CONTAINER_NAME="portfolio_db_prod"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Load environment variables
if [ -f ".env.prod" ]; then
    source .env.prod
else
    print_error ".env.prod file not found!"
    exit 1
fi

print_status "Starting database backup..."

# Create database backup
docker-compose -f docker-compose.prod.yml exec -T db pg_dump \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    --clean \
    --if-exists \
    --verbose > "$BACKUP_DIR/portfolio_backup_$DATE.sql"

if [ $? -eq 0 ]; then
    print_status "Database backup completed: portfolio_backup_$DATE.sql"
    
    # Compress the backup
    gzip "$BACKUP_DIR/portfolio_backup_$DATE.sql"
    print_status "Backup compressed: portfolio_backup_$DATE.sql.gz"
    
    # Remove backups older than 30 days
    find "$BACKUP_DIR" -name "*.sql.gz" -type f -mtime +30 -delete
    print_status "Old backups cleaned up (>30 days)"
    
    # Display backup size
    BACKUP_SIZE=$(du -h "$BACKUP_DIR/portfolio_backup_$DATE.sql.gz" | cut -f1)
    print_status "Backup size: $BACKUP_SIZE"
    
else
    print_error "Database backup failed!"
    exit 1
fi