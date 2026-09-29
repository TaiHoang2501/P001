"""deals, property holds, buyer availability; bookings gain deal_id and reschedule fields

Revision ID: c7d2e91b4f38
Revises: a36a40302169
Create Date: 2026-09-29 13:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7d2e91b4f38"
down_revision: str | Sequence[str] | None = "a36a40302169"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEAL_STATUSES = (
    "MATCHED",
    "VIEWING_REQUESTED",
    "VIEWING_CONFIRMED",
    "VIEWED",
    "INTERESTED",
    "NEGOTIATING",
    "TRANSACTION_SUPPORT",
    "COMPLETED",
    "CLOSED",
)
HOLD_STATUSES = ("ACTIVE", "RELEASED", "EXPIRED")
OLD_BOOKING_STATUSES = ("REQUESTED", "CONFIRMED", "REJECTED", "CANCELLED", "COMPLETED")
NEW_BOOKING_STATUSES = (*OLD_BOOKING_STATUSES, "RESCHEDULE_REQUESTED", "NO_SHOW")
OLD_ACTIVE = "status IN ('REQUESTED', 'CONFIRMED')"
NEW_ACTIVE = "status IN ('REQUESTED', 'CONFIRMED', 'RESCHEDULE_REQUESTED')"
DEAL_CODE_DEFAULT = "'VH-' || to_char(now(), 'YYYY') || '-' || lpad(nextval('deal_code_seq')::text, 5, '0')"


def _enum(name: str, *values: str) -> sa.Enum:
    # VARCHAR column; the allowed values are enforced by the named CHECK constraint next to it
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=False, length=32)


def _in(column: str, *values: str) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _period() -> sa.Column:
    return sa.Column(
        "period",
        postgresql.TSTZRANGE(),
        sa.Computed("tstzrange(start_at, end_at, '[)')", persisted=True),
        nullable=False,
    )


def _created_at() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def _fk(table: str, column: str, target: str, ondelete: str = "RESTRICT") -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], [f"{target}.id"], name=op.f(f"fk_{table}_{column}_{target}"), ondelete=ondelete
    )


def _replace_booking_rules(statuses: Sequence[str], active: str) -> None:
    op.drop_constraint(op.f("ck_bookings_booking_status"), "bookings", type_="check")
    op.create_check_constraint(op.f("ck_bookings_booking_status"), "bookings", _in("status", *statuses))
    op.execute("ALTER TABLE bookings DROP CONSTRAINT ex_bookings_no_overlap")
    op.create_exclude_constraint(
        "ex_bookings_no_overlap",
        "bookings",
        (sa.column("property_id"), "="),
        (sa.column("period"), "&&"),
        using="gist",
        where=sa.text(active),
    )


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE SEQUENCE deal_code_seq")
    op.create_table(
        "deals",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(length=32), server_default=sa.text(DEAL_CODE_DEFAULT), nullable=False),
        sa.Column("buyer_id", sa.BigInteger(), nullable=False),
        sa.Column("seller_id", sa.BigInteger(), nullable=False),
        sa.Column("property_id", sa.BigInteger(), nullable=False),
        sa.Column("status", _enum("deal_status", *DEAL_STATUSES), nullable=False),
        sa.Column("disclosure_level", sa.SmallInteger(), nullable=False),
        sa.Column("closed_reason", sa.Text(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(_in("status", *DEAL_STATUSES), name=op.f("ck_deals_deal_status")),
        _fk("deals", "buyer_id", "users"),
        _fk("deals", "seller_id", "users"),
        _fk("deals", "property_id", "properties"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deals")),
        sa.UniqueConstraint("code", name=op.f("uq_deals_code")),
    )
    op.execute("ALTER SEQUENCE deal_code_seq OWNED BY deals.code")
    op.create_index("ix_deals_property", "deals", ["property_id"], unique=False)
    op.create_index("ix_deals_seller", "deals", ["seller_id"], unique=False)
    op.create_index(
        "uq_deals_open_buyer_property",
        "deals",
        ["buyer_id", "property_id"],
        unique=True,
        postgresql_where=sa.text("status NOT IN ('COMPLETED', 'CLOSED')"),
    )

    op.create_table(
        "buyer_availability",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("buyer_id", sa.BigInteger(), nullable=False),
        sa.Column("deal_id", sa.BigInteger(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        _period(),
        _created_at(),
        sa.CheckConstraint("end_at > start_at", name=op.f("ck_buyer_availability_time_order")),
        _fk("buyer_availability", "buyer_id", "users", "CASCADE"),
        _fk("buyer_availability", "deal_id", "deals", "CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_buyer_availability")),
    )
    op.create_index("ix_buyer_availability_deal", "buyer_availability", ["deal_id"], unique=False)

    op.add_column("bookings", sa.Column("deal_id", sa.BigInteger(), nullable=True))
    op.add_column("bookings", sa.Column("proposed_start_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("bookings", sa.Column("proposed_end_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("bookings", sa.Column("cancelled_by", sa.BigInteger(), nullable=True))
    op.add_column("bookings", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_bookings_deal", "bookings", ["deal_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_bookings_deal_id_deals"), "bookings", "deals", ["deal_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_foreign_key(
        op.f("fk_bookings_cancelled_by_users"), "bookings", "users", ["cancelled_by"], ["id"], ondelete="RESTRICT"
    )
    op.create_check_constraint(
        op.f("ck_bookings_proposed_time_order"),
        "bookings",
        "(proposed_start_at IS NULL) = (proposed_end_at IS NULL)"
        " AND (proposed_end_at IS NULL OR proposed_end_at > proposed_start_at)",
    )
    _replace_booking_rules(NEW_BOOKING_STATUSES, NEW_ACTIVE)

    op.create_table(
        "property_holds",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("booking_id", sa.BigInteger(), nullable=False),
        sa.Column("deal_id", sa.BigInteger(), nullable=False),
        sa.Column("property_id", sa.BigInteger(), nullable=False),
        sa.Column("buyer_id", sa.BigInteger(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        _period(),
        sa.Column("status", _enum("hold_status", *HOLD_STATUSES), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("release_reason", sa.String(length=64), nullable=True),
        _created_at(),
        postgresql.ExcludeConstraint(
            (sa.column("property_id"), "="),
            (sa.column("period"), "&&"),
            where=sa.text("status = 'ACTIVE'"),
            using="gist",
            name="ex_property_holds_no_overlap",
        ),
        sa.CheckConstraint("end_at > start_at", name=op.f("ck_property_holds_time_order")),
        sa.CheckConstraint(_in("status", *HOLD_STATUSES), name=op.f("ck_property_holds_hold_status")),
        _fk("property_holds", "booking_id", "bookings"),
        _fk("property_holds", "deal_id", "deals"),
        _fk("property_holds", "property_id", "properties"),
        _fk("property_holds", "buyer_id", "users"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_property_holds")),
        sa.UniqueConstraint("booking_id", name=op.f("uq_property_holds_booking_id")),
    )
    op.create_index("ix_property_holds_status_end", "property_holds", ["status", "end_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_property_holds_status_end", table_name="property_holds")
    op.drop_table("property_holds")

    op.execute("UPDATE bookings SET status = 'CONFIRMED' WHERE status = 'RESCHEDULE_REQUESTED'")
    op.execute("UPDATE bookings SET status = 'CANCELLED' WHERE status = 'NO_SHOW'")
    _replace_booking_rules(OLD_BOOKING_STATUSES, OLD_ACTIVE)
    op.drop_constraint(op.f("ck_bookings_proposed_time_order"), "bookings", type_="check")
    op.drop_constraint(op.f("fk_bookings_cancelled_by_users"), "bookings", type_="foreignkey")
    op.drop_constraint(op.f("fk_bookings_deal_id_deals"), "bookings", type_="foreignkey")
    op.drop_index("ix_bookings_deal", table_name="bookings")
    for col in ("completed_at", "cancelled_by", "proposed_end_at", "proposed_start_at", "deal_id"):
        op.drop_column("bookings", col)

    op.drop_index("ix_buyer_availability_deal", table_name="buyer_availability")
    op.drop_table("buyer_availability")
    op.drop_index("uq_deals_open_buyer_property", table_name="deals")
    op.drop_index("ix_deals_seller", table_name="deals")
    op.drop_index("ix_deals_property", table_name="deals")
    op.drop_table("deals")
