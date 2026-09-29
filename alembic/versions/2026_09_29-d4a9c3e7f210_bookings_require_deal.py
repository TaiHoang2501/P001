"""bookings.deal_id becomes required; older bookings get a backfilled deal

Revision ID: d4a9c3e7f210
Revises: 8b3d6f2e1a45
Create Date: 2026-09-29 16:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4a9c3e7f210"
down_revision: str | Sequence[str] | None = "8b3d6f2e1a45"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # One deal per (buyer, property) that has bookings without a deal; status follows those bookings
    op.execute(
        """
        INSERT INTO deals (buyer_id, seller_id, property_id, status, disclosure_level)
        SELECT b.customer_id, p.owner_id, b.property_id,
               CASE
                   WHEN bool_or(b.status = 'COMPLETED') THEN 'VIEWED'
                   WHEN bool_or(b.status = 'CONFIRMED') THEN 'VIEWING_CONFIRMED'
                   WHEN bool_or(b.status IN ('REQUESTED', 'RESCHEDULE_REQUESTED')) THEN 'VIEWING_REQUESTED'
                   ELSE 'MATCHED'
               END,
               1
        FROM bookings b
        JOIN properties p ON p.id = b.property_id
        WHERE b.deal_id IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM deals d
              WHERE d.buyer_id = b.customer_id AND d.property_id = b.property_id
                AND d.status NOT IN ('COMPLETED', 'CLOSED')
          )
        GROUP BY b.customer_id, p.owner_id, b.property_id
        """
    )
    op.execute(
        """
        UPDATE bookings b
        SET deal_id = d.id
        FROM deals d
        WHERE b.deal_id IS NULL
          AND d.buyer_id = b.customer_id AND d.property_id = b.property_id
          AND d.status NOT IN ('COMPLETED', 'CLOSED')
        """
    )
    op.alter_column("bookings", "deal_id", existing_type=sa.BigInteger(), nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("bookings", "deal_id", existing_type=sa.BigInteger(), nullable=True)
