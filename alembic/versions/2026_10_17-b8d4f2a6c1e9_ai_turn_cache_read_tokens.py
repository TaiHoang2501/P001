"""ai_turns.cache_read_tokens: the part of a turn's input tokens read from the model's prompt cache

Revision ID: b8d4f2a6c1e9
Revises: a3c9e1f5b7d2
Create Date: 2026-10-17 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8d4f2a6c1e9"
down_revision: str | Sequence[str] | None = "a3c9e1f5b7d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ai_turns", sa.Column("cache_read_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_turns", "cache_read_tokens")
