"""identity & media: seller/buyer profiles, property media, otp codes; WITHDRAWN property status

Revision ID: a36a40302169
Revises: e803d4d391f5
Create Date: 2026-09-29 12:21:38.848929

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a36a40302169"
down_revision: str | Sequence[str] | None = "e803d4d391f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_PROPERTY_STATUSES = "'DRAFT', 'PENDING_REVIEW', 'AVAILABLE', 'REJECTED', 'SOLD'"
NEW_PROPERTY_STATUSES = OLD_PROPERTY_STATUSES + ", 'WITHDRAWN'"


def _enum(name: str, *values: str) -> sa.Enum:
    # VARCHAR column; the allowed values are enforced by the named CHECK constraint next to it
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=False, length=32)


def _in(column: str, *values: str) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


VERIFICATION = ("UNVERIFIED", "PENDING", "VERIFIED", "REJECTED")
SOURCES = ("SELF", "AI_INTENT", "APP", "WEBSITE", "CSKH", "BQL", "HOTLINE")
MEDIA_KINDS = ("IMAGE", "VIDEO", "FLOORPLAN", "OWNERSHIP_DOC")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "otp_codes",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("target", sa.String(length=255), nullable=False),
        sa.Column("purpose", _enum("otp_purpose", "LOGIN"), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(_in("purpose", "LOGIN"), name=op.f("ck_otp_codes_otp_purpose")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_otp_codes")),
    )
    op.create_index("ix_otp_codes_target_created", "otp_codes", ["target", "created_at"], unique=False)

    op.create_table(
        "buyer_profiles",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("budget_min_vnd", sa.BigInteger(), nullable=True),
        sa.Column("budget_max_vnd", sa.BigInteger(), nullable=True),
        sa.Column("preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("viewing_preference", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "budget_min_vnd IS NULL OR budget_max_vnd IS NULL OR budget_min_vnd <= budget_max_vnd",
            name=op.f("ck_buyer_profiles_budget_order"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_buyer_profiles_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_buyer_profiles")),
    )

    op.create_table(
        "seller_profiles",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("verification_status", _enum("seller_verification_status", *VERIFICATION), nullable=False),
        sa.Column("source", _enum("seller_source", *SOURCES), nullable=False),
        sa.Column("id_document_s3_key", sa.String(length=512), nullable=True),
        sa.Column("verified_by", sa.BigInteger(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(_in("source", *SOURCES), name=op.f("ck_seller_profiles_seller_source")),
        sa.CheckConstraint(
            _in("verification_status", *VERIFICATION), name=op.f("ck_seller_profiles_seller_verification_status")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_seller_profiles_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["verified_by"], ["users.id"], name=op.f("fk_seller_profiles_verified_by_users"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_seller_profiles")),
    )

    op.create_table(
        "property_media",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("property_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", _enum("media_kind", *MEDIA_KINDS), nullable=False),
        sa.Column("s3_key", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(_in("kind", *MEDIA_KINDS), name=op.f("ck_property_media_media_kind")),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
            name=op.f("fk_property_media_property_id_properties"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_property_media")),
    )
    op.create_index("ix_property_media_property_order", "property_media", ["property_id", "sort_order"], unique=False)

    op.drop_constraint(op.f("ck_properties_property_status"), "properties", type_="check")
    op.create_check_constraint(
        op.f("ck_properties_property_status"), "properties", f"status IN ({NEW_PROPERTY_STATUSES})"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE properties SET status = 'REJECTED' WHERE status = 'WITHDRAWN'")
    op.drop_constraint(op.f("ck_properties_property_status"), "properties", type_="check")
    op.create_check_constraint(
        op.f("ck_properties_property_status"), "properties", f"status IN ({OLD_PROPERTY_STATUSES})"
    )
    op.drop_index("ix_property_media_property_order", table_name="property_media")
    op.drop_table("property_media")
    op.drop_table("seller_profiles")
    op.drop_table("buyer_profiles")
    op.drop_index("ix_otp_codes_target_created", table_name="otp_codes")
    op.drop_table("otp_codes")
