#!/bin/sh
set -eu

if [ "${AUTO_MIGRATE:-true}" = "true" ]; then
    echo "Applying database migrations..."
    python manage.py migrate --noinput
fi

if [ "${CHECK_DEPLOY:-false}" = "true" ]; then
    python manage.py check_production_security
fi

echo "Collecting static files..."
python manage.py collectstatic --noinput

exec "$@"

