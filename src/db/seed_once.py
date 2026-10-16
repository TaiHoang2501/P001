"""Load the demo data once per database, not on every server start (scripts/start.sh).

The database remembers which version of the demo data it has (system_settings "seed.version"). A start-up on a
database that already has it reads that one row and goes on (plain psycopg: no app models or services are
loaded). Only a new database, or one seeded by an older version, runs the seed steps, then records the version.
Bump SEED_VERSION when the demo data changes, so every database loads what is new on its next start.

The steps keep their own guards (markers, "add what is missing"), so a version bump never adds anything twice.
Viewing slots are kept 14 days ahead by the daily job in src/jobs.py, not here.
"""

import json

import psycopg

from src.config import get_settings

SEED_VERSION = "2026-10-17.all-cases"
SETTING_KEY = "seed.version"
# Two instances starting together: one seeds, the other waits for it and then sees the version
_LOCK_ID = 7_420_190


def _conninfo() -> str:
    return get_settings().database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def _seeded_version(conn: psycopg.Connection) -> str | None:
    row = conn.execute("SELECT value->>'version' FROM system_settings WHERE key = %s", (SETTING_KEY,)).fetchone()
    return row[0] if row else None


def run_seed_steps() -> None:
    """What start-up used to run every time, plus every case of each role's pages (ensure_all_cases)."""
    from src.db import seed
    from src.db.session import get_sessionmaker

    with get_sessionmaker()() as db:
        if not seed.has_data(db):
            seed.seed(db)
        print(f"Added {seed.ensure_red_books(db)} red book(s).")
        print(f"Added {seed.ensure_listings(db)} demo listing(s).")
        print(f"Seller story: {seed.ensure_seller_story(db)}.")
        # After the seller story, which links Lan's listings to her own red books
        print(f"Red books: {seed.ensure_red_book_units(db)}.")
        print(f"Verified {seed.ensure_sellers_verified(db)} seller(s) by their red book.")
        # Before the slots, so the homes moved to a demo seller get theirs
        print(f"Demo accounts only: {seed.ensure_demo_accounts_only(db)}.")
        print(f"Added photos to {seed.ensure_photos(db)} listing(s).")
        print(f"Added {seed.ensure_slots(db, 14)} demo viewing slot(s).")
        # Last: the cases book the slots topped up above
        print(f"All cases: {seed.ensure_all_cases(db)}.")


def main() -> None:
    with psycopg.connect(_conninfo(), autocommit=True) as conn:
        if _seeded_version(conn) == SEED_VERSION:
            print(f"Demo data {SEED_VERSION} already loaded; skipping seed.")
            return
        conn.execute("SELECT pg_advisory_lock(%s)", (_LOCK_ID,))
        try:
            if _seeded_version(conn) == SEED_VERSION:
                print(f"Demo data {SEED_VERSION} loaded by another instance; skipping seed.")
                return
            run_seed_steps()
            conn.execute(
                "INSERT INTO system_settings (key, value) VALUES (%s, %s::jsonb) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()",
                (SETTING_KEY, json.dumps({"version": SEED_VERSION})),
            )
            print(f"Demo data {SEED_VERSION} loaded.")
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (_LOCK_ID,))


if __name__ == "__main__":
    main()
