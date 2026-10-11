"""owner suggests other times: a request the owner cannot take can carry up to three times that suit them

- bookings.suggested_starts: start times the owner offered when declining (the buyer books one in a tap)

Revision ID: f3c8a1d2b4e7
Revises: e5b9c3d7a281
Create Date: 2026-10-09 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3c8a1d2b4e7"
down_revision: str | Sequence[str] | None = "e5b9c3d7a281"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("suggested_starts", postgresql.ARRAY(sa.DateTime(timezone=True)), nullable=True))


def downgrade() -> None:
    op.drop_column("bookings", "suggested_starts")
