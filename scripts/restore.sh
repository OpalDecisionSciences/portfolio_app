#!/bin/bash

# Database Restore Script
set -e

# Configuration
BACKUP_DIR="/home/$(whoami)/portfolio_app/backups"
BACKUP_FILE=$1

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

# Check if backup file is provided
if [ -z "$BACKUP_FILE" ]; then
    print_error "Usage: $0 <backup_file>"
    print_status "Available backups:"
    ls -la "$BACKUP_DIR"/*.sql.gz 2>/dev/null || echo "No backups found"
    exit 1
fi

# Check if backup file exists
if [ ! -f "$BACKUP_DIR/$BACKUP_FILE" ]; then
    print_error "Backup file not found: $BACKUP_DIR/$BACKUP_FILE"
    exit 1
fi

# Load environment variables
if [ -f ".env.prod" ]; then
    source .env.prod
else
    print_error ".env.prod file not found!"
    exit 1
fi

print_warning "This will restore the database and overwrite existing data!"
read -p "Are you sure you want to continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_status "Restore cancelled."
    exit 0
fi

print_status "Starting database restore from: $BACKUP_FILE"

# Stop web services to prevent database conflicts
print_status "Stopping web services..."
docker-compose -f docker-compose.prod.yml stop web celery celery-beat

# Decompress if needed
TEMP_FILE=""
if [[ $BACKUP_FILE == *.gz ]]; then
    print_status "Decompressing backup file..."
    TEMP_FILE="$BACKUP_DIR/temp_restore.sql"
    gunzip -c "$BACKUP_DIR/$BACKUP_FILE" > "$TEMP_FILE"
    RESTORE_FILE="$TEMP_FILE"
else
    RESTORE_FILE="$BACKUP_DIR/$BACKUP_FILE"
fi

# Restore database
print_status "Restoring database..."
docker-compose -f docker-compose.prod.yml exec -T db psql \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" < "$RESTORE_FILE"

if [ $? -eq 0 ]; then
    print_status "Database restore completed successfully!"
    
    # Clean up temporary file
    if [ ! -z "$TEMP_FILE" ]; then
        rm "$TEMP_FILE"
    fi
    
    # Restart web services
    print_status "Restarting web services..."
    docker-compose -f docker-compose.prod.yml start web celery celery-beat
    
    print_status "Restore process completed!"
    
else
    print_error "Database restore failed!"
    
    # Clean up temporary file
    if [ ! -z "$TEMP_FILE" ]; then
        rm "$TEMP_FILE"
    fi
    
    # Restart web services anyway
    print_status "Restarting web services..."
    docker-compose -f docker-compose.prod.yml start web celery celery-beat
    
    exit 1
fi