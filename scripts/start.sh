#!/bin/sh
# Container start-up: bring the schema up to date, load demo data on first start, add demo red books
# missing from an older database, keep demo viewing slots in the future, then serve the API on $PORT.
#   SEED_DEMO_DATA=false  skips all demo seeding (e.g. for a real, non-demo database)
set -e

alembic upgrade head

if [ "${SEED_DEMO_DATA:-true}" = "true" ]; then
  python -m src.db.seed --if-empty --ensure-slots 7 --ensure-red-books
fi

exec uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
