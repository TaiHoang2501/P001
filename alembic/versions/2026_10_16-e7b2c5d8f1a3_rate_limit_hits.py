"""rate_limit_hits: chat rate limits counted in the database, shared by every API instance

Revision ID: e7b2c5d8f1a3
Revises: d1f3a9c7e2b4
Create Date: 2026-10-16 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7b2c5d8f1a3"
down_revision: str | Sequence[str] | None = "d1f3a9c7e2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_hits",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rate_limit_hits")),
    )
    op.create_index("ix_rate_limit_hits_key_created", "rate_limit_hits", ["key", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_rate_limit_hits_key_created", table_name="rate_limit_hits")
    op.drop_table("rate_limit_hits")
