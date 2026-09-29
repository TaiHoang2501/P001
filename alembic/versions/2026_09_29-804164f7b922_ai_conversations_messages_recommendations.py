"""ai conversations, messages and recommendations; deals.source_recommendation_id

Revision ID: 804164f7b922
Revises: d4a9c3e7f210
Create Date: 2026-09-29 14:37:12.005016

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "804164f7b922"
down_revision: str | Sequence[str] | None = "d4a9c3e7f210"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "ai_conversations",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("buyer_id", sa.BigInteger(), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("thread_id", sa.String(length=128), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "ACTIVE",
                "CLOSED",
                "ESCALATED",
                name="conversation_status",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("extracted_criteria", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'CLOSED', 'ESCALATED')", name=op.f("ck_ai_conversations_conversation_status")
        ),
        sa.ForeignKeyConstraint(
            ["buyer_id"], ["users.id"], name=op.f("fk_ai_conversations_buyer_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_conversations")),
        sa.UniqueConstraint("buyer_id", "client_id", name="uq_ai_conversations_buyer_client"),
        sa.UniqueConstraint("thread_id", name=op.f("uq_ai_conversations_thread_id")),
    )
    op.create_index("ix_ai_conversations_buyer_last", "ai_conversations", ["buyer_id", "last_message_at"], unique=False)
    op.create_table(
        "ai_messages",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "USER", "ASSISTANT", "TOOL", name="message_role", native_enum=False, create_constraint=False, length=32
            ),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_calls", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tool_name", sa.String(length=64), nullable=True),
        sa.Column("tool_args", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tool_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tool_ok", sa.Boolean(), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role IN ('USER', 'ASSISTANT', 'TOOL')", name=op.f("ck_ai_messages_message_role")),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["ai_conversations.id"],
            name=op.f("fk_ai_messages_conversation_id_ai_conversations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_messages")),
    )
    op.create_index("ix_ai_messages_conversation", "ai_messages", ["conversation_id", "id"], unique=False)
    op.create_table(
        "recommendations",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("ai_message_id", sa.BigInteger(), nullable=False),
        sa.Column("buyer_id", sa.BigInteger(), nullable=False),
        sa.Column("property_id", sa.BigInteger(), nullable=False),
        sa.Column("rank", sa.SmallInteger(), nullable=False),
        sa.Column("match_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("score_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("criteria_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["ai_message_id"],
            ["ai_messages.id"],
            name=op.f("fk_recommendations_ai_message_id_ai_messages"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["buyer_id"], ["users.id"], name=op.f("fk_recommendations_buyer_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["ai_conversations.id"],
            name=op.f("fk_recommendations_conversation_id_ai_conversations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
            name=op.f("fk_recommendations_property_id_properties"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recommendations")),
    )
    op.create_index("ix_recommendations_buyer_property", "recommendations", ["buyer_id", "property_id"], unique=False)
    op.create_index("ix_recommendations_conversation", "recommendations", ["conversation_id"], unique=False)
    op.add_column("deals", sa.Column("source_recommendation_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        op.f("fk_deals_source_recommendation_id_recommendations"),
        "deals",
        "recommendations",
        ["source_recommendation_id"],
        ["id"],
        ondelete="SET NULL",
        use_alter=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f("fk_deals_source_recommendation_id_recommendations"), "deals", type_="foreignkey")
    op.drop_column("deals", "source_recommendation_id")
    op.drop_index("ix_recommendations_conversation", table_name="recommendations")
    op.drop_index("ix_recommendations_buyer_property", table_name="recommendations")
    op.drop_table("recommendations")
    op.drop_index("ix_ai_messages_conversation", table_name="ai_messages")
    op.drop_table("ai_messages")
    op.drop_index("ix_ai_conversations_buyer_last", table_name="ai_conversations")
    op.drop_table("ai_conversations")
