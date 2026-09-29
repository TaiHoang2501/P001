"""otp-only accounts: users.password_hash becomes nullable

Revision ID: 5e1f0c8a7b62
Revises: c7d2e91b4f38
Create Date: 2026-09-29 14:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5e1f0c8a7b62"
down_revision: str | Sequence[str] | None = "c7d2e91b4f38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # OTP-only accounts get an unusable hash (verify_password always fails on it)
    op.execute("UPDATE users SET password_hash = '!' WHERE password_hash IS NULL")
    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=False)
