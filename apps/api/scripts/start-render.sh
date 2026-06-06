#!/bin/sh

set -eu

MAX_ATTEMPTS="${DB_WAIT_MAX_ATTEMPTS:-30}"
SLEEP_SECONDS="${DB_WAIT_SLEEP_SECONDS:-2}"
ATTEMPT=1

echo "Waiting for Postgres and running migrations..."
until alembic upgrade head
do
  if [ "$ATTEMPT" -ge "$MAX_ATTEMPTS" ]; then
    echo "Database migrations failed after ${ATTEMPT} attempts."
    exit 1
  fi

  echo "Migration attempt ${ATTEMPT} failed. Retrying in ${SLEEP_SECONDS}s..."
  ATTEMPT=$((ATTEMPT + 1))
  sleep "$SLEEP_SECONDS"
done

echo "Seeding demo tenant..."
python -m app.scripts.seed_demo

echo "Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
