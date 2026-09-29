"""notifications: in-app events and scheduled viewing reminders

Revision ID: 83c0378cf434
Revises: 804164f7b922
Create Date: 2026-09-29 14:42:51.251919

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "83c0378cf434"
down_revision: str | Sequence[str] | None = "804164f7b922"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column(
            "channel",
            sa.Enum(
                "IN_APP",
                "SMS",
                "ZALO",
                "EMAIL",
                name="notification_channel",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("deal_id", sa.BigInteger(), nullable=True),
        sa.Column("booking_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "SENT",
                "FAILED",
                "CANCELLED",
                name="notification_status",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "channel IN ('IN_APP', 'SMS', 'ZALO', 'EMAIL')", name=op.f("ck_notifications_notification_channel")
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'SENT', 'FAILED', 'CANCELLED')", name=op.f("ck_notifications_notification_status")
        ),
        sa.ForeignKeyConstraint(
            ["booking_id"], ["bookings.id"], name=op.f("fk_notifications_booking_id_bookings"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["deal_id"], ["deals.id"], name=op.f("fk_notifications_deal_id_deals"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_notifications_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
        sa.UniqueConstraint("dedupe_key", name=op.f("uq_notifications_dedupe_key")),
    )
    op.create_index("ix_notifications_booking", "notifications", ["booking_id"], unique=False)
    op.create_index("ix_notifications_status_scheduled", "notifications", ["status", "scheduled_at"], unique=False)
    op.create_index("ix_notifications_user_created", "notifications", ["user_id", "created_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_index("ix_notifications_status_scheduled", table_name="notifications")
    op.drop_index("ix_notifications_booking", table_name="notifications")
    op.drop_table("notifications")
