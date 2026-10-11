"""booking EXPIRED: a request whose viewing time passed before the owner answered closes by itself

Revision ID: c4e8b1a6d2f0
Revises: a7d4e2f9c1b3
Create Date: 2026-10-10 19:30:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4e8b1a6d2f0"
down_revision: str | Sequence[str] | None = "a7d4e2f9c1b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BOOKING = (
    "'REQUESTED', 'CONFIRMED', 'REJECTED', 'CANCELLED', 'COMPLETED', 'RESCHEDULE_REQUESTED', 'NO_SHOW', "
    "'OWNER_ABSENT', 'UNREPORTED'"
)


def _check(values: str) -> None:
    op.drop_constraint(op.f("ck_bookings_booking_status"), "bookings", type_="check")
    op.create_check_constraint(op.f("ck_bookings_booking_status"), "bookings", f"status IN ({values})")


def upgrade() -> None:
    _check(f"{BOOKING}, 'EXPIRED'")


def downgrade() -> None:
    op.execute("UPDATE bookings SET status = 'REJECTED' WHERE status = 'EXPIRED'")
    _check(BOOKING)
