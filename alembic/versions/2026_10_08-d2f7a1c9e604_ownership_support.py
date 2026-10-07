"""ownership support: sellers ask the investor for help verifying a red book; private uploaded documents

- escalations.type gains OWNERSHIP_SUPPORT (the investor's exception queue handles these cases)
- media_files.is_private: identity / authorisation documents only the uploader and the investor can open

Revision ID: d2f7a1c9e604
Revises: c4e8b2a6d913
Create Date: 2026-10-08 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d2f7a1c9e604"
down_revision: str | Sequence[str] | None = "c4e8b2a6d913"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_TYPES = "'SELLER_NO_RESPONSE', 'NO_COMMON_SLOT', 'SCHEDULE_CONFLICT', 'PROPERTY_ISSUE', 'MULTI_BUYER', 'SYSTEM_FAILURE', 'OTHER'"


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(op.f("ck_escalations_escalation_type"), "escalations", type_="check")
    op.create_check_constraint(
        op.f("ck_escalations_escalation_type"), "escalations", f"type IN ({OLD_TYPES}, 'OWNERSHIP_SUPPORT')"
    )
    op.add_column("media_files", sa.Column("is_private", sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("media_files", "is_private")
    op.execute("UPDATE escalations SET type = 'OTHER' WHERE type = 'OWNERSHIP_SUPPORT'")
    op.drop_constraint(op.f("ck_escalations_escalation_type"), "escalations", type_="check")
    op.create_check_constraint(op.f("ck_escalations_escalation_type"), "escalations", f"type IN ({OLD_TYPES})")
