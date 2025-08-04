#!/bin/bash
set -e

# Unified Django entrypoint script - environment-aware
# Adapts behavior based on DEBUG environment variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    echo -e "${GREEN}[DJANGO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[DJANGO]${NC} $1"
}

print_error() {
    echo -e "${RED}[DJANGO]${NC} $1"
}

# Determine environment based on DEBUG setting
DEBUG=${DEBUG:-False}
if [[ "$DEBUG" == "True" || "$DEBUG" == "true" || "$DEBUG" == "1" ]]; then
    ENVIRONMENT="development"
else
    ENVIRONMENT="production"
fi

print_status "Starting Django application in $ENVIRONMENT mode..."

# Wait for database to be ready
print_status "Waiting for database to be ready..."
until python -c "
import os
import psycopg
try:
    conn = psycopg.connect(
        host=os.environ.get('DATABASE_HOST', 'db'),
        port=os.environ.get('DATABASE_PORT', '5432'),
        user=os.environ.get('DATABASE_USER', 'postgres'),
        password=os.environ.get('DATABASE_PASSWORD', ''),
        dbname=os.environ.get('DATABASE_NAME', 'postgres')
    )
    conn.close()
    print('Database connection successful with psycopg3!')
    exit(0)
except psycopg.OperationalError as e:
    print(f'Database not ready: {e}')
    exit(1)
except Exception as e:
    print(f'Database connection error: {e}')
    exit(1)
"; do
    print_warning "Database not ready, retrying in 2 seconds..."
    sleep 2
done

print_status "Database is ready!"

# Production setup - simplified for docker-compose.prod.yml
print_status "Setting up production environment..."

# Create necessary directories
mkdir -p /app/logs /app/media /app/staticfiles /app/celery-data

# Run migrations
print_status "Running database migrations..."
python manage.py migrate --noinput

# Collect static files
print_status "Collecting static files..."
python manage.py collectstatic --noinput --clear

# Create superuser if specified
if [[ -n "$DJANGO_SUPERUSER_USERNAME" && -n "$DJANGO_SUPERUSER_EMAIL" && -n "$DJANGO_SUPERUSER_PASSWORD" ]]; then
    print_status "Creating superuser..."
    python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists():
    User.objects.create_superuser('$DJANGO_SUPERUSER_USERNAME', '$DJANGO_SUPERUSER_EMAIL', '$DJANGO_SUPERUSER_PASSWORD')
    print('Superuser created successfully')
else:
    print('Superuser already exists')
"
fi

# Start production server with gunicorn
print_status "Starting production server with gunicorn..."
exec gunicorn portfolio_project.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --worker-class uvicorn.workers.UvicornWorker \
    --worker-connections 1000 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --timeout 30 \
    --keep-alive 5 \
    --access-logfile /app/logs/gunicorn-access.log \
    --error-logfile /app/logs/gunicorn-error.log \
    --log-level info \
    --preload