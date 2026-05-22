#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "Waiting for postgres..."

# Simple check to see if Postgres is ready
# We use the environment variables from docker-compose
while ! nc -z $POSTGRES_SERVER 5432; do
  sleep 0.1
done

echo "PostgreSQL started"

# Run migrations
echo "Running database migrations..."
alembic upgrade head

# Start application
echo "Starting application..."
exec uvicorn src.main:app --host 0.0.0.0 --port 8000
