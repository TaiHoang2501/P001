#!/bin/sh
# Container start-up: bring the schema up to date, load the demo data once per database (and again only when its
# version changes), then serve the API on $PORT. The daily job keeps demo viewing slots in the future.
#   SEED_DEMO_DATA=false   skips all demo seeding (e.g. for a real, non-demo database)
#   DB_SETUP_ON_START=false  serves straight away, skipping migrations and seeding (~18s of a cold start); Cloud Run
#                          does this and runs `sh scripts/start.sh setup` once per deploy instead (deploy-cloudrun.yml)
#   sh scripts/start.sh setup  migrations and seeding only, without serving
set -e

if [ "$1" = "setup" ] || [ "${DB_SETUP_ON_START:-true}" = "true" ]; then
  alembic upgrade head

  if [ "${SEED_DEMO_DATA:-true}" = "true" ]; then
    # Once per database, not on every start: a database that has this version of the demo data skips in a
    # moment (see src/db/seed_once.py; bump SEED_VERSION there when the demo data changes)
    python -m src.db.seed_once
  fi
fi

[ "$1" = "setup" ] && exit 0

exec uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
