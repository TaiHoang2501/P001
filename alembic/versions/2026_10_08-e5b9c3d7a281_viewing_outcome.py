"""viewing outcome: the owner records it, the buyer can dispute it, unrecorded viewings close by themselves

- bookings.status gains OWNER_ABSENT (the operator found the owner was not there) and UNREPORTED (nobody
  recorded the outcome within the deadline; nobody is blamed)
- escalations.type gains VIEWING_DISPUTE (the buyer disagrees with the recorded outcome)

Revision ID: e5b9c3d7a281
Revises: d2f7a1c9e604
Create Date: 2026-10-08 14:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5b9c3d7a281"
down_revision: str | Sequence[str] | None = "d2f7a1c9e604"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BOOKING = "'REQUESTED', 'CONFIRMED', 'REJECTED', 'CANCELLED', 'COMPLETED', 'RESCHEDULE_REQUESTED', 'NO_SHOW'"
ESCALATION = (
    "'SELLER_NO_RESPONSE', 'NO_COMMON_SLOT', 'SCHEDULE_CONFLICT', 'PROPERTY_ISSUE', 'MULTI_BUYER', "
    "'SYSTEM_FAILURE', 'OTHER', 'OWNERSHIP_SUPPORT'"
)


def _check(name: str, table: str, column: str, values: str) -> None:
    op.drop_constraint(op.f(name), table, type_="check")
    op.create_check_constraint(op.f(name), table, f"{column} IN ({values})")


def upgrade() -> None:
    """Upgrade schema."""
    _check("ck_bookings_booking_status", "bookings", "status", f"{BOOKING}, 'OWNER_ABSENT', 'UNREPORTED'")
    _check("ck_escalations_escalation_type", "escalations", "type", f"{ESCALATION}, 'VIEWING_DISPUTE'")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE bookings SET status = 'NO_SHOW' WHERE status IN ('OWNER_ABSENT', 'UNREPORTED')")
    op.execute("UPDATE escalations SET type = 'OTHER' WHERE type = 'VIEWING_DISPUTE'")
    _check("ck_bookings_booking_status", "bookings", "status", BOOKING)
    _check("ck_escalations_escalation_type", "escalations", "type", ESCALATION)
