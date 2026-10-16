"""properties.sold_to_user_id: the BookingBot buyer a sold home went to

Revision ID: a3c9e1f5b7d2
Revises: e7b2c5d8f1a3
Create Date: 2026-10-17 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3c9e1f5b7d2"
down_revision: str | Sequence[str] | None = "e7b2c5d8f1a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("sold_to_user_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        op.f("fk_properties_sold_to_user_id_users"), "properties", "users", ["sold_to_user_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_properties_sold_to_user_id_users"), "properties", type_="foreignkey")
    op.drop_column("properties", "sold_to_user_id")
