"""SQLAlchemy models for the BookingBot MVP.

Design notes:
- Enums are stored as VARCHAR + CHECK (not native PG enums) so adding a value is a plain migration.
- Every Buyer + Seller + Property relationship is a Deal (spec §4.9); bookings hang off a deal.
- The viewing hold is its own row (property_holds), created only after Owner confirmation and
  locking only the viewing window (spec §4.13). REQUESTED bookings also reserve the window so two
  buyers cannot request the same time.
- Double-booking/double-holding is blocked by the database itself (exclusion constraints on
  property + time range), not only by application code (AC-08).
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
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
    WITHDRAWN = "WITHDRAWN"


class SellerVerificationStatus(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class SellerSource(StrEnum):
    """How the seller reached the platform (spec §4.6)."""

    SELF = "SELF"
    AI_INTENT = "AI_INTENT"
    APP = "APP"
    WEBSITE = "WEBSITE"
    CSKH = "CSKH"
    BQL = "BQL"
    HOTLINE = "HOTLINE"


class MediaKind(StrEnum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    FLOORPLAN = "FLOORPLAN"
    OWNERSHIP_DOC = "OWNERSHIP_DOC"


class OtpPurpose(StrEnum):
    LOGIN = "LOGIN"


class BookingStatus(StrEnum):
    REQUESTED = "REQUESTED"
    CONFIRMED = "CONFIRMED"
    RESCHEDULE_REQUESTED = "RESCHEDULE_REQUESTED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    NO_SHOW = "NO_SHOW"


# Statuses that occupy a property's time window
ACTIVE_BOOKING_STATUSES = (
    BookingStatus.REQUESTED,
    BookingStatus.CONFIRMED,
    BookingStatus.RESCHEDULE_REQUESTED,
)


class DealStatus(StrEnum):
    """Deal lifecycle (spec §4.9). The MVP drives it up to VIEWED."""

    MATCHED = "MATCHED"
    VIEWING_REQUESTED = "VIEWING_REQUESTED"
    VIEWING_CONFIRMED = "VIEWING_CONFIRMED"
    VIEWED = "VIEWED"
    INTERESTED = "INTERESTED"
    NEGOTIATING = "NEGOTIATING"
    TRANSACTION_SUPPORT = "TRANSACTION_SUPPORT"
    COMPLETED = "COMPLETED"
    CLOSED = "CLOSED"


# A buyer has at most one open deal per property
CLOSED_DEAL_STATUSES = (DealStatus.COMPLETED, DealStatus.CLOSED)


class HoldStatus(StrEnum):
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"


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
    # NULL for buyers/sellers who only ever sign in with OTP; operators always have one
    password_hash: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = _now_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class OtpCode(Base):
    """One-time login code sent to a phone/email. Only the hash is stored."""

    __tablename__ = "otp_codes"
    __table_args__ = (Index("ix_otp_codes_target_created", "target", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    target: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[OtpPurpose] = mapped_column(_enum(OtpPurpose, "otp_purpose"), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _now_column()


class BuyerProfile(Base):
    """What a seller may see about a buyer at privacy Level 1 (spec §4.7): no PII."""

    __tablename__ = "buyer_profiles"
    __table_args__ = (
        CheckConstraint(
            "budget_min_vnd IS NULL OR budget_max_vnd IS NULL OR budget_min_vnd <= budget_max_vnd",
            name="budget_order",
        ),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    budget_min_vnd: Mapped[int | None] = mapped_column(BigInteger)
    budget_max_vnd: Mapped[int | None] = mapped_column(BigInteger)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    viewing_preference: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SellerProfile(Base):
    """Owner verification state; only VERIFIED sellers' properties can be booked (AC-04)."""

    __tablename__ = "seller_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    verification_status: Mapped[SellerVerificationStatus] = mapped_column(
        _enum(SellerVerificationStatus, "seller_verification_status"),
        nullable=False,
        default=SellerVerificationStatus.UNVERIFIED,
    )
    source: Mapped[SellerSource] = mapped_column(
        _enum(SellerSource, "seller_source"), nullable=False, default=SellerSource.SELF
    )
    id_document_s3_key: Mapped[str | None] = mapped_column(String(512))
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
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
    media: Mapped[list["PropertyMedia"]] = relationship(
        order_by="(PropertyMedia.sort_order, PropertyMedia.id)", cascade="all, delete-orphan"
    )


class PropertyMedia(Base):
    """Photo/video/document stored in S3. Ownership documents are never shown to buyers."""

    __tablename__ = "property_media"
    __table_args__ = (Index("ix_property_media_property_order", "property_id", "sort_order"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[MediaKind] = mapped_column(_enum(MediaKind, "media_kind"), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = _now_column()


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


DEAL_CODE_SEQUENCE = "deal_code_seq"


class Deal(Base):
    """One Buyer + Seller + Property relationship, identified by a human-readable code (spec §4.9)."""

    __tablename__ = "deals"
    __table_args__ = (
        # A buyer has at most one open deal per property; a new one may start after it is closed
        Index(
            "uq_deals_open_buyer_property",
            "buyer_id",
            "property_id",
            unique=True,
            postgresql_where=text("status NOT IN ('COMPLETED', 'CLOSED')"),
        ),
        Index("ix_deals_seller", "seller_id"),
        Index("ix_deals_property", "property_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # e.g. VH-2026-00128
    code: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        unique=True,
        server_default=text(
            f"'VH-' || to_char(now(), 'YYYY') || '-' || lpad(nextval('{DEAL_CODE_SEQUENCE}')::text, 5, '0')"
        ),
    )
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    # Snapshot of the property's owner at deal creation, used for attribution (spec §4.10)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[DealStatus] = mapped_column(
        _enum(DealStatus, "deal_status"), nullable=False, default=DealStatus.MATCHED
    )
    # Progressive disclosure level 1-4 (spec §4.7)
    disclosure_level: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    closed_reason: Mapped[str | None] = mapped_column(Text)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _now_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    buyer: Mapped[User] = relationship(foreign_keys=[buyer_id])
    seller: Mapped[User] = relationship(foreign_keys=[seller_id])
    property: Mapped[Property] = relationship()


class BuyerAvailability(Base):
    """A time window the buyer can attend a viewing, intersected with seller slots (spec §4.8)."""

    __tablename__ = "buyer_availability"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="time_order"),
        Index("ix_buyer_availability_deal", "deal_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period: Mapped[Any] = mapped_column(TSTZRANGE, Computed("tstzrange(start_at, end_at, '[)')", persisted=True))
    created_at: Mapped[datetime] = _now_column()


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="time_order"),
        CheckConstraint(
            "(proposed_start_at IS NULL) = (proposed_end_at IS NULL)"
            " AND (proposed_end_at IS NULL OR proposed_end_at > proposed_start_at)",
            name="proposed_time_order",
        ),
        # The anti-double-booking guarantee: at most one active booking per property per time window
        ExcludeConstraint(
            (column("property_id"), "="),
            (column("period"), "&&"),
            using="gist",
            name="ex_bookings_no_overlap",
            where=text("status IN ('REQUESTED', 'CONFIRMED', 'RESCHEDULE_REQUESTED')"),
        ),
        Index("ix_bookings_customer", "customer_id"),
        Index("ix_bookings_status_start", "status", "start_at"),
        Index("ix_bookings_deal", "deal_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="RESTRICT"), nullable=False)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    slot_id: Mapped[int | None] = mapped_column(ForeignKey("availability_slots.id", ondelete="SET NULL"))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period: Mapped[Any] = mapped_column(TSTZRANGE, Computed("tstzrange(start_at, end_at, '[)')", persisted=True))
    status: Mapped[BookingStatus] = mapped_column(
        _enum(BookingStatus, "booking_status"), nullable=False, default=BookingStatus.REQUESTED
    )
    # New time asked for while RESCHEDULE_REQUESTED; becomes start_at/end_at once the owner confirms
    proposed_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    proposed_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_via: Mapped[Channel] = mapped_column(_enum(Channel, "channel"), nullable=False, default=Channel.WEB)
    customer_note: Mapped[str | None] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _now_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    deal: Mapped[Deal] = relationship()
    property: Mapped[Property] = relationship()
    customer: Mapped[User] = relationship(foreign_keys=[customer_id])
    hold: Mapped["PropertyHold | None"] = relationship(viewonly=True, uselist=False)


class PropertyHold(Base):
    """Viewing hold: locks the property for one confirmed viewing window only (spec §4.13)."""

    __tablename__ = "property_holds"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="time_order"),
        # AC-08: never two active holds on one property at overlapping times
        ExcludeConstraint(
            (column("property_id"), "="),
            (column("period"), "&&"),
            using="gist",
            name="ex_property_holds_no_overlap",
            where=text("status = 'ACTIVE'"),
        ),
        Index("ix_property_holds_status_end", "status", "end_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="RESTRICT"), nullable=False, unique=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="RESTRICT"), nullable=False)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period: Mapped[Any] = mapped_column(TSTZRANGE, Computed("tstzrange(start_at, end_at, '[)')", persisted=True))
    status: Mapped[HoldStatus] = mapped_column(
        _enum(HoldStatus, "hold_status"), nullable=False, default=HoldStatus.ACTIVE
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_reason: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = _now_column()

    booking: Mapped[Booking] = relationship()


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
