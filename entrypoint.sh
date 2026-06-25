#!/bin/sh

echo "═══════════════════════════════════════════════"
echo "  Optimum WiFi Portal — Starting Up"
echo "═══════════════════════════════════════════════"

# ── Wait for database to be ready ─────────────────────
echo "Waiting for database..."
while ! nc -z db 5432; do
    sleep 1
done
echo "✅ Database is ready"

# ── Run migrations and start Gunicorn for web only ────
# Celery containers skip this and run their own command
if [ "$SERVICE" = "web" ]; then
    echo "Running migrations..."
    python manage.py migrate --noinput
    echo "✅ Migrations complete"

    echo "Collecting static files..."
    python manage.py collectstatic --noinput
    echo "✅ Static files collected"

    echo "Starting Gunicorn..."
    exec gunicorn wifiportal.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers 4 \
        --timeout 120 \
        --access-logfile - \
        --error-logfile -
else
    # Celery worker and beat — execute the docker-compose command
    exec "$@"
fi