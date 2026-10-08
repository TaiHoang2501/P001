"""owner-level viewing overlap: pending requests may overlap, confirmed viewings of one owner may not

The owner decides whom to receive, so several buyers may ask for the same time (on the same home or on
different homes of one owner). Only confirmed viewings take the owner's time: an owner can never have two
confirmed viewings at overlapping times, on any of their homes.

`bookings.owner_id` copies the home's owner (filled by a trigger) so the exclusion constraint can use it.

Revision ID: f1a6c0d2b8e4
Revises: b9e4c2a17d53
Create Date: 2026-10-07 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a6c0d2b8e4"
down_revision: str | Sequence[str] | None = "b9e4c2a17d53"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("bookings", sa.Column("owner_id", sa.BigInteger(), nullable=True))
    op.execute("UPDATE bookings b SET owner_id = p.owner_id FROM properties p WHERE p.id = b.property_id")
    op.alter_column("bookings", "owner_id", nullable=False)
    op.create_foreign_key(
        op.f("fk_bookings_owner_id_users"), "bookings", "users", ["owner_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_index("ix_bookings_owner", "bookings", ["owner_id"])
    op.execute(
        """
        CREATE FUNCTION bookings_set_owner() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            SELECT owner_id INTO NEW.owner_id FROM properties WHERE id = NEW.property_id;
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_bookings_set_owner BEFORE INSERT OR UPDATE OF property_id ON bookings
        FOR EACH ROW EXECUTE FUNCTION bookings_set_owner();
        """
    )
    _resolve_existing_overlaps()
    op.execute("ALTER TABLE bookings DROP CONSTRAINT ex_bookings_no_overlap")
    op.execute(
        """
        ALTER TABLE bookings ADD CONSTRAINT ex_bookings_owner_no_overlap
        EXCLUDE USING gist (owner_id WITH =, period WITH &&)
        WHERE (status IN ('CONFIRMED', 'RESCHEDULE_REQUESTED'));
        """
    )


def _resolve_existing_overlaps() -> None:
    """Older data may already have one owner confirmed twice at the same time (on two homes): keep the earlier
    viewing, cancel the later one and release its hold, so the new constraint can be created."""
    conn = op.get_bind()
    while True:
        later = conn.execute(
            sa.text(
                """
                SELECT b.id FROM bookings a
                JOIN bookings b ON b.owner_id = a.owner_id AND b.id <> a.id AND a.period && b.period
                WHERE a.status IN ('CONFIRMED', 'RESCHEDULE_REQUESTED')
                  AND b.status IN ('CONFIRMED', 'RESCHEDULE_REQUESTED')
                  AND (a.created_at, a.id) < (b.created_at, b.id)
                LIMIT 1
                """
            )
        ).scalar()
        if later is None:
            return
        conn.execute(
            sa.text(
                "UPDATE bookings SET status = 'CANCELLED', cancelled_at = now(), proposed_start_at = NULL, "
                "proposed_end_at = NULL WHERE id = :id"
            ),
            {"id": later},
        )
        conn.execute(
            sa.text(
                "UPDATE property_holds SET status = 'RELEASED', released_at = now(), release_reason = 'owner_overlap' "
                "WHERE booking_id = :id AND status = 'ACTIVE'"
            ),
            {"id": later},
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE bookings DROP CONSTRAINT ex_bookings_owner_no_overlap")
    op.execute(
        """
        ALTER TABLE bookings ADD CONSTRAINT ex_bookings_no_overlap
        EXCLUDE USING gist (property_id WITH =, period WITH &&)
        WHERE (status IN ('REQUESTED', 'CONFIRMED', 'RESCHEDULE_REQUESTED'));
        """
    )
    op.execute("DROP TRIGGER trg_bookings_set_owner ON bookings")
    op.execute("DROP FUNCTION bookings_set_owner()")
    op.drop_index("ix_bookings_owner", table_name="bookings")
    op.drop_constraint(op.f("fk_bookings_owner_id_users"), "bookings", type_="foreignkey")
    op.drop_column("bookings", "owner_id")
