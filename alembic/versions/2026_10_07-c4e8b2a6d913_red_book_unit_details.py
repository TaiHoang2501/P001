"""red book unit details: the investor's own record of the home behind each red book

A listing takes these facts (building, unit, type, area, rooms, floor, direction) from its verified red book,
so a seller cannot list them wrong; the uploaded "ownership document" is no longer needed.

Revision ID: c4e8b2a6d913
Revises: a7c3e9d10b52
Create Date: 2026-10-07 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4e8b2a6d913"
down_revision: str | Sequence[str] | None = "a7c3e9d10b52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "property_ownership_verifications"


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(TABLE, sa.Column("building_id", sa.BigInteger(), nullable=True))
    op.add_column(TABLE, sa.Column("unit_code", sa.String(length=50), nullable=True))
    op.add_column(TABLE, sa.Column("property_type", sa.String(length=32), nullable=True))
    op.add_column(TABLE, sa.Column("area_m2", sa.Numeric(precision=8, scale=2), nullable=True))
    op.add_column(TABLE, sa.Column("bedrooms", sa.Integer(), nullable=True))
    op.add_column(TABLE, sa.Column("bathrooms", sa.Integer(), nullable=True))
    op.add_column(TABLE, sa.Column("floor", sa.Integer(), nullable=True))
    op.add_column(TABLE, sa.Column("direction", sa.String(length=32), nullable=True))
    op.create_check_constraint(
        op.f("ck_property_ownership_verifications_property_type"),
        TABLE,
        "property_type IN ('APARTMENT', 'VILLA', 'TOWNHOUSE', 'SHOPHOUSE')",
    )
    op.create_check_constraint(
        op.f("ck_property_ownership_verifications_direction"),
        TABLE,
        "direction IN ('N', 'S', 'E', 'W', 'NE', 'NW', 'SE', 'SW')",
    )
    op.create_foreign_key(
        op.f("fk_property_ownership_verifications_building_id_buildings"),
        TABLE,
        "buildings",
        ["building_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f("fk_property_ownership_verifications_building_id_buildings"), TABLE, type_="foreignkey")
    op.drop_constraint(op.f("ck_property_ownership_verifications_direction"), TABLE, type_="check")
    op.drop_constraint(op.f("ck_property_ownership_verifications_property_type"), TABLE, type_="check")
    for name in ("direction", "floor", "bathrooms", "bedrooms", "area_m2", "property_type", "unit_code", "building_id"):
        op.drop_column(TABLE, name)
