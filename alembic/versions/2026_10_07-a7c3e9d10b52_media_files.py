"""media_files: photos sellers upload from their device, stored in the database

Revision ID: a7c3e9d10b52
Revises: f1a6c0d2b8e4
Create Date: 2026-10-07 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c3e9d10b52"
down_revision: str | Sequence[str] | None = "f1a6c0d2b8e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "media_files",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_media_files_owner_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_files")),
    )
    op.create_index("ix_media_files_owner", "media_files", ["owner_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_media_files_owner", table_name="media_files")
    op.drop_table("media_files")
