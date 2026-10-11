"""ai turn traces for developers: every chat turn (guests and failed turns included) with its steps

- ai_turns: one row per chat turn (trace id, buyer or guest, status / error, model, tokens, latency, steps)
- ai_messages.turn_id links the stored messages to their turn
- ai_conversations.buyer_id and recommendations.buyer_id become nullable: a guest's chat is stored too and is
  attached to the account when the guest signs up

Revision ID: a7d4e2f9c1b3
Revises: f3c8a1d2b4e7
Create Date: 2026-10-10 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7d4e2f9c1b3"
down_revision: str | Sequence[str] | None = "f3c8a1d2b4e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_turns",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("trace_id", sa.String(32), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=True),
        sa.Column("buyer_id", sa.BigInteger(), nullable=True),
        sa.Column("guest", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("streamed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(16), nullable=False, server_default="OK"),
        sa.Column("error_type", sa.String(128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("llm_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tool_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("steps", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["ai_conversations.id"], name=op.f("fk_ai_turns_conversation_id_ai_conversations"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["buyer_id"], ["users.id"], name=op.f("fk_ai_turns_buyer_id_users"), ondelete="SET NULL"
        ),
        sa.UniqueConstraint("trace_id", name=op.f("uq_ai_turns_trace_id")),
    )
    op.create_index("ix_ai_turns_created", "ai_turns", ["created_at"])
    op.create_index("ix_ai_turns_status", "ai_turns", ["status", "created_at"])
    op.add_column("ai_messages", sa.Column("turn_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        op.f("fk_ai_messages_turn_id_ai_turns"), "ai_messages", "ai_turns", ["turn_id"], ["id"], ondelete="SET NULL"
    )
    op.alter_column("ai_conversations", "buyer_id", nullable=True)
    op.alter_column("recommendations", "buyer_id", nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM recommendations WHERE buyer_id IS NULL")
    op.execute("DELETE FROM ai_conversations WHERE buyer_id IS NULL")
    op.alter_column("recommendations", "buyer_id", nullable=False)
    op.alter_column("ai_conversations", "buyer_id", nullable=False)
    op.drop_constraint(op.f("fk_ai_messages_turn_id_ai_turns"), "ai_messages", type_="foreignkey")
    op.drop_column("ai_messages", "turn_id")
    op.drop_index("ix_ai_turns_status", table_name="ai_turns")
    op.drop_index("ix_ai_turns_created", table_name="ai_turns")
    op.drop_table("ai_turns")
