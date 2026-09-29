"""initial MVP schema: users, projects, buildings, properties, slots, bookings, audit log

Revision ID: e803d4d391f5
Revises:
Create Date: 2026-09-28 01:56:06.974917

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e803d4d391f5"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # btree_gist: exclusion constraints mixing "=" and "&&" (anti double-booking)
    # pg_trgm: fuzzy text search on descriptions
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Enum columns use VARCHAR; the allowed values are enforced by the named CHECK constraints below
    op.create_table(
        "projects",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("district", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
        sa.UniqueConstraint("code", name=op.f("uq_projects_code")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "CUSTOMER",
                "OWNER",
                "INVESTOR_OPERATOR",
                name="user_role",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "ACTIVE",
                "SUSPENDED",
                "PENDING_VERIFICATION",
                name="user_status",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role IN ('CUSTOMER', 'OWNER', 'INVESTOR_OPERATOR')", name=op.f("ck_users_user_role")),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'SUSPENDED', 'PENDING_VERIFICATION')", name=op.f("ck_users_user_status")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("phone", name=op.f("uq_users_phone")),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "actor_type",
            sa.Enum(
                "USER", "AI_AGENT", "SYSTEM", name="actor_type", native_enum=False, create_constraint=False, length=32
            ),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.BigInteger(), nullable=False),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint("actor_type IN ('USER', 'AI_AGENT', 'SYSTEM')", name=op.f("ck_audit_logs_actor_type")),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name=op.f("fk_audit_logs_actor_id_users"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index("ix_audit_actor", "audit_logs", ["actor_id"], unique=False)
    op.create_index("ix_audit_target", "audit_logs", ["target_type", "target_id"], unique=False)
    op.create_table(
        "buildings",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("total_floors", sa.Integer(), nullable=True),
        sa.Column("lat", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("lng", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_buildings_project_id_projects"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_buildings")),
        sa.UniqueConstraint("project_id", "code", name="uq_buildings_project_code"),
    )
    op.create_table(
        "properties",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("building_id", sa.BigInteger(), nullable=False),
        sa.Column("unit_code", sa.String(length=50), nullable=False),
        sa.Column(
            "property_type",
            sa.Enum(
                "APARTMENT",
                "VILLA",
                "TOWNHOUSE",
                "SHOPHOUSE",
                name="property_type",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("bedrooms", sa.Integer(), nullable=False),
        sa.Column("bathrooms", sa.Integer(), nullable=False),
        sa.Column("area_m2", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("floor", sa.Integer(), nullable=False),
        sa.Column("price_vnd", sa.BigInteger(), nullable=False),
        sa.Column(
            "direction",
            sa.Enum(
                "N",
                "S",
                "E",
                "W",
                "NE",
                "NW",
                "SE",
                "SW",
                name="direction",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "view",
            sa.Enum(
                "LAKE",
                "RIVER",
                "PARK",
                "POOL",
                "CITY",
                "INTERNAL",
                name="view_type",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "furnishing",
            sa.Enum("NONE", "BASIC", "FULL", name="furnishing", native_enum=False, create_constraint=False, length=32),
            nullable=False,
        ),
        sa.Column(
            "legal_status",
            sa.Enum(
                "PINK_BOOK",
                "PENDING_BOOK",
                "SALE_CONTRACT",
                name="legal_status",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("image_urls", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT",
                "PENDING_REVIEW",
                "AVAILABLE",
                "REJECTED",
                "SOLD",
                name="property_status",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.BigInteger(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "direction IN ('N', 'S', 'E', 'W', 'NE', 'NW', 'SE', 'SW')", name=op.f("ck_properties_direction")
        ),
        sa.CheckConstraint("furnishing IN ('NONE', 'BASIC', 'FULL')", name=op.f("ck_properties_furnishing")),
        sa.CheckConstraint(
            "legal_status IN ('PINK_BOOK', 'PENDING_BOOK', 'SALE_CONTRACT')", name=op.f("ck_properties_legal_status")
        ),
        sa.CheckConstraint(
            "property_type IN ('APARTMENT', 'VILLA', 'TOWNHOUSE', 'SHOPHOUSE')",
            name=op.f("ck_properties_property_type"),
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'PENDING_REVIEW', 'AVAILABLE', 'REJECTED', 'SOLD')",
            name=op.f("ck_properties_property_status"),
        ),
        sa.CheckConstraint(
            "view IN ('LAKE', 'RIVER', 'PARK', 'POOL', 'CITY', 'INTERNAL')", name=op.f("ck_properties_view_type")
        ),
        sa.CheckConstraint("area_m2 > 0", name=op.f("ck_properties_area_positive")),
        sa.CheckConstraint("bedrooms >= 0 AND bathrooms >= 0", name=op.f("ck_properties_rooms_non_negative")),
        sa.CheckConstraint("price_vnd > 0", name=op.f("ck_properties_price_positive")),
        sa.ForeignKeyConstraint(
            ["building_id"], ["buildings.id"], name=op.f("fk_properties_building_id_buildings"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_properties_owner_id_users"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"], ["users.id"], name=op.f("fk_properties_reviewed_by_users"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_properties")),
        sa.UniqueConstraint("building_id", "unit_code", name="uq_properties_building_unit"),
    )
    op.create_index(
        "ix_properties_description_trgm",
        "properties",
        ["description"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"description": "gin_trgm_ops"},
    )
    op.create_index("ix_properties_owner", "properties", ["owner_id"], unique=False)
    op.create_index("ix_properties_status_price", "properties", ["status", "price_vnd"], unique=False)
    op.create_table(
        "availability_slots",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("property_id", sa.BigInteger(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "period",
            postgresql.TSTZRANGE(),
            sa.Computed("tstzrange(start_at, end_at, '[)')", persisted=True),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        postgresql.ExcludeConstraint(
            (sa.column("property_id"), "="), (sa.column("period"), "&&"), using="gist", name="ex_slots_no_overlap"
        ),
        sa.CheckConstraint("end_at > start_at", name=op.f("ck_availability_slots_time_order")),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
            name=op.f("fk_availability_slots_property_id_properties"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_availability_slots")),
    )
    op.create_table(
        "bookings",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("property_id", sa.BigInteger(), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=False),
        sa.Column("slot_id", sa.BigInteger(), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "period",
            postgresql.TSTZRANGE(),
            sa.Computed("tstzrange(start_at, end_at, '[)')", persisted=True),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "REQUESTED",
                "CONFIRMED",
                "REJECTED",
                "CANCELLED",
                "COMPLETED",
                name="booking_status",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_via",
            sa.Enum("WEB", "AI_AGENT", name="channel", native_enum=False, create_constraint=False, length=32),
            nullable=False,
        ),
        sa.Column("customer_note", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        postgresql.ExcludeConstraint(
            (sa.column("property_id"), "="),
            (sa.column("period"), "&&"),
            where=sa.text("status IN ('REQUESTED', 'CONFIRMED')"),
            using="gist",
            name="ex_bookings_no_overlap",
        ),
        sa.CheckConstraint("created_via IN ('WEB', 'AI_AGENT')", name=op.f("ck_bookings_channel")),
        sa.CheckConstraint(
            "status IN ('REQUESTED', 'CONFIRMED', 'REJECTED', 'CANCELLED', 'COMPLETED')",
            name=op.f("ck_bookings_booking_status"),
        ),
        sa.CheckConstraint("end_at > start_at", name=op.f("ck_bookings_time_order")),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["users.id"], name=op.f("fk_bookings_customer_id_users"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["property_id"], ["properties.id"], name=op.f("fk_bookings_property_id_properties"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["slot_id"],
            ["availability_slots.id"],
            name=op.f("fk_bookings_slot_id_availability_slots"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bookings")),
    )
    op.create_index("ix_bookings_customer", "bookings", ["customer_id"], unique=False)
    op.create_index("ix_bookings_status_start", "bookings", ["status", "start_at"], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index("ix_bookings_status_start", table_name="bookings")
    op.drop_index("ix_bookings_customer", table_name="bookings")
    op.drop_table("bookings")
    op.drop_table("availability_slots")
    op.drop_index("ix_properties_status_price", table_name="properties")
    op.drop_index("ix_properties_owner", table_name="properties")
    op.drop_index(
        "ix_properties_description_trgm",
        table_name="properties",
        postgresql_using="gin",
        postgresql_ops={"description": "gin_trgm_ops"},
    )
    op.drop_table("properties")
    op.drop_table("buildings")
    op.drop_index("ix_audit_target", table_name="audit_logs")
    op.drop_index("ix_audit_actor", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_table("users")
    op.drop_table("projects")
    # ### end Alembic commands ###
