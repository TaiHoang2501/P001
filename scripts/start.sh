#!/bin/sh
# Container start-up: bring the schema up to date, load demo data on first start, add demo red books and
# listings missing from an older database, keep demo viewing slots in the future, then serve the API on $PORT.
#   SEED_DEMO_DATA=false   skips all demo seeding (e.g. for a real, non-demo database)
#   DB_SETUP_ON_START=false  serves straight away, skipping migrations and seeding (~18s of a cold start); Cloud Run
#                          does this and runs `sh scripts/start.sh setup` once per deploy instead (deploy-cloudrun.yml)
#   sh scripts/start.sh setup  migrations and seeding only, without serving
set -e

if [ "$1" = "setup" ] || [ "${DB_SETUP_ON_START:-true}" = "true" ]; then
  alembic upgrade head

  if [ "${SEED_DEMO_DATA:-true}" = "true" ]; then
    python -m src.db.seed --if-empty --ensure-red-books --ensure-listings --ensure-seller-story --ensure-red-book-units --ensure-sellers-verified --ensure-photos --ensure-slots 14 --ensure-requests --ensure-showcase --ensure-rich-demo
  fi
fi

[ "$1" = "setup" ] && exit 0

exec uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
