#!/bin/bash
set -e

echo "Starting production Django application..."

# Wait for database to be ready
echo "Waiting for database..."
until python -c "
import os
import psycopg2
try:
    conn = psycopg2.connect(
        host=os.environ['DATABASE_HOST'],
        port=os.environ['DATABASE_PORT'],
        user=os.environ['DATABASE_USER'],
        password=os.environ['DATABASE_PASSWORD'],
        dbname=os.environ['DATABASE_NAME']
    )
    conn.close()
    print('Database is ready!')
    exit(0)
except psycopg2.OperationalError:
    print('Database not ready, retrying...')
    exit(1)
"; do
  sleep 2
done

# Run migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start gunicorn
echo "Starting gunicorn..."
exec gunicorn portfolio_project.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --worker-class gevent \
    --worker-connections 1000 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --timeout 30 \
    --keep-alive 5 \
    --access-logfile /app/logs/gunicorn-access.log \
    --error-logfile /app/logs/gunicorn-error.log \
    --log-level info