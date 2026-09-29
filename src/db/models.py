"""SQLAlchemy models for the BookingBot MVP.

Design notes (see docs/backend-mvp.md):
- Enums are stored as VARCHAR + CHECK (not native PG enums) so adding a value is a plain migration.
- A CONFIRMED booking *is* the viewing hold (spec §4.9): it only locks its own time window.
  REQUESTED bookings also reserve the slot so two customers cannot request the same window.
- Double-booking is blocked by the database itself (exclusion constraint on property + time range),
  not only by application code.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    column,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSTZRANGE, ExcludeConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# ---------- Enums ----------


class UserRole(StrEnum):
    CUSTOMER = "CUSTOMER"
    OWNER = "OWNER"
    INVESTOR_OPERATOR = "INVESTOR_OPERATOR"


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"


class PropertyType(StrEnum):
    APARTMENT = "APARTMENT"
    VILLA = "VILLA"
    TOWNHOUSE = "TOWNHOUSE"
    SHOPHOUSE = "SHOPHOUSE"


class Direction(StrEnum):
    N = "N"
    S = "S"
    E = "E"
    W = "W"
    NE = "NE"
    NW = "NW"
    SE = "SE"
    SW = "SW"


class ViewType(StrEnum):
    LAKE = "LAKE"
    RIVER = "RIVER"
    PARK = "PARK"
    POOL = "POOL"
    CITY = "CITY"
    INTERNAL = "INTERNAL"


class Furnishing(StrEnum):
    NONE = "NONE"
    BASIC = "BASIC"
    FULL = "FULL"


class LegalStatus(StrEnum):
    PINK_BOOK = "PINK_BOOK"
    PENDING_BOOK = "PENDING_BOOK"
    SALE_CONTRACT = "SALE_CONTRACT"


class PropertyStatus(StrEnum):
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    AVAILABLE = "AVAILABLE"
    REJECTED = "REJECTED"
    SOLD = "SOLD"


class BookingStatus(StrEnum):
    REQUESTED = "REQUESTED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


# Statuses that occupy a property's time window
ACTIVE_BOOKING_STATUSES = (BookingStatus.REQUESTED, BookingStatus.CONFIRMED)


class Channel(StrEnum):
    WEB = "WEB"
    AI_AGENT = "AI_AGENT"


class ActorType(StrEnum):
    USER = "USER"
    AI_AGENT = "AI_AGENT"
    SYSTEM = "SYSTEM"


def _enum(enum_cls: type[StrEnum], name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda e: [m.value for m in e],
    )


def _now_column() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


# ---------- Tables ----------


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    role: Mapped[UserRole] = mapped_column(_enum(UserRole, "user_role"), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        _enum(UserStatus, "user_status"), nullable=False, default=UserStatus.ACTIVE
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = _now_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    district: Mapped[str | None] = mapped_column(String(100))

    buildings: Mapped[list["Building"]] = relationship(back_populates="project")


class Building(Base):
    __tablename__ = "buildings"
    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_buildings_project_code"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    total_floors: Mapped[int | None] = mapped_column(Integer)
    lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))

    project: Mapped[Project] = relationship(back_populates="buildings")


class Property(Base):
    __tablename__ = "properties"
    __table_args__ = (
        UniqueConstraint("building_id", "unit_code", name="uq_properties_building_unit"),
        CheckConstraint("price_vnd > 0", name="price_positive"),
        CheckConstraint("area_m2 > 0", name="area_positive"),
        CheckConstraint("bedrooms >= 0 AND bathrooms >= 0", name="rooms_non_negative"),
        Index("ix_properties_status_price", "status", "price_vnd"),
        Index("ix_properties_owner", "owner_id"),
        Index(
            "ix_properties_description_trgm",
            "description",
            postgresql_using="gin",
            postgresql_ops={"description": "gin_trgm_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    building_id: Mapped[int] = mapped_column(ForeignKey("buildings.id", ondelete="RESTRICT"), nullable=False)
    unit_code: Mapped[str] = mapped_column(String(50), nullable=False)
    property_type: Mapped[PropertyType] = mapped_column(_enum(PropertyType, "property_type"), nullable=False)
    bedrooms: Mapped[int] = mapped_column(Integer, nullable=False)
    bathrooms: Mapped[int] = mapped_column(Integer, nullable=False)
    area_m2: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    floor: Mapped[int] = mapped_column(Integer, nullable=False)
    price_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    direction: Mapped[Direction] = mapped_column(_enum(Direction, "direction"), nullable=False)
    view: Mapped[ViewType] = mapped_column(_enum(ViewType, "view_type"), nullable=False)
    furnishing: Mapped[Furnishing] = mapped_column(_enum(Furnishing, "furnishing"), nullable=False)
    legal_status: Mapped[LegalStatus] = mapped_column(_enum(LegalStatus, "legal_status"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    image_urls: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[PropertyStatus] = mapped_column(
        _enum(PropertyStatus, "property_status"), nullable=False, default=PropertyStatus.DRAFT
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _now_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped[User] = relationship(foreign_keys=[owner_id])
    building: Mapped[Building] = relationship()


class AvailabilitySlot(Base):
    """A viewing window the owner offers for one property."""

    __tablename__ = "availability_slots"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="time_order"),
        ExcludeConstraint(
            (column("property_id"), "="),
            (column("period"), "&&"),
            using="gist",
            name="ex_slots_no_overlap",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period: Mapped[Any] = mapped_column(TSTZRANGE, Computed("tstzrange(start_at, end_at, '[)')", persisted=True))
    created_at: Mapped[datetime] = _now_column()


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="time_order"),
        # The anti-double-booking guarantee (AC-03): at most one active booking per property per time window
        ExcludeConstraint(
            (column("property_id"), "="),
            (column("period"), "&&"),
            using="gist",
            name="ex_bookings_no_overlap",
            where=text("status IN ('REQUESTED', 'CONFIRMED')"),
        ),
        Index("ix_bookings_customer", "customer_id"),
        Index("ix_bookings_status_start", "status", "start_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    slot_id: Mapped[int | None] = mapped_column(ForeignKey("availability_slots.id", ondelete="SET NULL"))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period: Mapped[Any] = mapped_column(TSTZRANGE, Computed("tstzrange(start_at, end_at, '[)')", persisted=True))
    status: Mapped[BookingStatus] = mapped_column(
        _enum(BookingStatus, "booking_status"), nullable=False, default=BookingStatus.REQUESTED
    )
    created_via: Mapped[Channel] = mapped_column(_enum(Channel, "channel"), nullable=False, default=Channel.WEB)
    customer_note: Mapped[str | None] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _now_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    property: Mapped[Property] = relationship()
    customer: Mapped[User] = relationship(foreign_keys=[customer_id])


class AuditLog(Base):
    """Append-only record of every important write (who, what, which record, before/after)."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_target", "target_type", "target_id"),
        Index("ix_audit_actor", "actor_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = _now_column()
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    actor_type: Mapped[ActorType] = mapped_column(_enum(ActorType, "actor_type"), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    extra: Mapped[dict | None] = mapped_column(JSONB)
