"""escalations: operator exception queue

Revision ID: 4530e22c63a4
Revises: 83c0378cf434
Create Date: 2026-09-29 14:50:07.125076

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4530e22c63a4"
down_revision: str | Sequence[str] | None = "83c0378cf434"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "escalations",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "SELLER_NO_RESPONSE",
                "NO_COMMON_SLOT",
                "SCHEDULE_CONFLICT",
                "PROPERTY_ISSUE",
                "MULTI_BUYER",
                "SYSTEM_FAILURE",
                "OTHER",
                name="escalation_type",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "OPEN",
                "IN_PROGRESS",
                "RESOLVED",
                "DISMISSED",
                name="escalation_status",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "raised_by",
            sa.Enum(
                "USER", "AI_AGENT", "SYSTEM", name="actor_type", native_enum=False, create_constraint=False, length=32
            ),
            nullable=False,
        ),
        sa.Column("requester_id", sa.BigInteger(), nullable=True),
        sa.Column("deal_id", sa.BigInteger(), nullable=True),
        sa.Column("booking_id", sa.BigInteger(), nullable=True),
        sa.Column("property_id", sa.BigInteger(), nullable=True),
        sa.Column("conversation_id", sa.BigInteger(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("assigned_to", sa.BigInteger(), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("raised_by IN ('USER', 'AI_AGENT', 'SYSTEM')", name=op.f("ck_escalations_actor_type")),
        sa.CheckConstraint(
            "status IN ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'DISMISSED')", name=op.f("ck_escalations_escalation_status")
        ),
        sa.CheckConstraint(
            "type IN ('SELLER_NO_RESPONSE', 'NO_COMMON_SLOT', 'SCHEDULE_CONFLICT', 'PROPERTY_ISSUE', 'MULTI_BUYER', 'SYSTEM_FAILURE', 'OTHER')",
            name=op.f("ck_escalations_escalation_type"),
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to"], ["users.id"], name=op.f("fk_escalations_assigned_to_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["booking_id"], ["bookings.id"], name=op.f("fk_escalations_booking_id_bookings"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["ai_conversations.id"],
            name=op.f("fk_escalations_conversation_id_ai_conversations"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["deal_id"], ["deals.id"], name=op.f("fk_escalations_deal_id_deals"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["property_id"], ["properties.id"], name=op.f("fk_escalations_property_id_properties"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["requester_id"], ["users.id"], name=op.f("fk_escalations_requester_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_escalations")),
    )
    op.create_index("ix_escalations_requester", "escalations", ["requester_id"], unique=False)
    op.create_index("ix_escalations_status_created", "escalations", ["status", "created_at"], unique=False)
    op.create_index(
        "uq_escalations_open_booking_type",
        "escalations",
        ["booking_id", "type"],
        unique=True,
        postgresql_where=sa.text("status IN ('OPEN', 'IN_PROGRESS') AND booking_id IS NOT NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "uq_escalations_open_booking_type",
        table_name="escalations",
        postgresql_where=sa.text("status IN ('OPEN', 'IN_PROGRESS') AND booking_id IS NOT NULL"),
    )
    op.drop_index("ix_escalations_status_created", table_name="escalations")
    op.drop_index("ix_escalations_requester", table_name="escalations")
    op.drop_table("escalations")
