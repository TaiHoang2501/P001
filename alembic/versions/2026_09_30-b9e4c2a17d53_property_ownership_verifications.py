"""property ownership verifications: red book + OTP before a seller can list

Revision ID: b9e4c2a17d53
Revises: 4530e22c63a4
Create Date: 2026-09-30 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b9e4c2a17d53"
down_revision: str | Sequence[str] | None = "4530e22c63a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "property_ownership_verifications",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("red_book_holder_name", sa.String(length=255), nullable=False),
        sa.Column("red_book_code", sa.String(length=100), nullable=False),
        sa.Column("owner_phone", sa.String(length=20), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "UNVERIFIED",
                "OTP_SENT",
                "VERIFIED",
                "FAILED",
                name="ownership_verification_status",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("otp_attempts", sa.Integer(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('UNVERIFIED', 'OTP_SENT', 'VERIFIED', 'FAILED')",
            name=op.f("ck_property_ownership_verifications_ownership_verification_status"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_property_ownership_verifications_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_property_ownership_verifications")),
        sa.UniqueConstraint("red_book_code", name=op.f("uq_property_ownership_verifications_red_book_code")),
    )
    op.create_index(
        op.f("ix_property_ownership_verifications_user_id"),
        "property_ownership_verifications",
        ["user_id"],
        unique=False,
    )

    op.add_column("properties", sa.Column("verification_id", sa.BigInteger(), nullable=True))
    op.create_unique_constraint(op.f("uq_properties_verification_id"), "properties", ["verification_id"])
    op.create_foreign_key(
        op.f("fk_properties_verification_id_property_ownership_verifications"),
        "properties",
        "property_ownership_verifications",
        ["verification_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.drop_constraint(op.f("ck_otp_codes_otp_purpose"), "otp_codes", type_="check")
    op.create_check_constraint(op.f("ck_otp_codes_otp_purpose"), "otp_codes", "purpose IN ('LOGIN', 'OWNERSHIP')")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM otp_codes WHERE purpose = 'OWNERSHIP'")
    op.drop_constraint(op.f("ck_otp_codes_otp_purpose"), "otp_codes", type_="check")
    op.create_check_constraint(op.f("ck_otp_codes_otp_purpose"), "otp_codes", "purpose IN ('LOGIN')")

    op.drop_constraint(
        op.f("fk_properties_verification_id_property_ownership_verifications"), "properties", type_="foreignkey"
    )
    op.drop_constraint(op.f("uq_properties_verification_id"), "properties", type_="unique")
    op.drop_column("properties", "verification_id")

    op.drop_index(op.f("ix_property_ownership_verifications_user_id"), table_name="property_ownership_verifications")
    op.drop_table("property_ownership_verifications")
