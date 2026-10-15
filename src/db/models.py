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
    FetchedValue,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSTZRANGE, ExcludeConstraint
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
    # Sent to the phone recorded on a red book to prove the seller owns it
    OWNERSHIP = "OWNERSHIP"


class OwnershipVerificationStatus(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    OTP_SENT = "OTP_SENT"
    VERIFIED = "VERIFIED"
    # Too many wrong codes: locked until the investor/operator looks at it
    FAILED = "FAILED"


class BookingStatus(StrEnum):
    REQUESTED = "REQUESTED"
    CONFIRMED = "CONFIRMED"
    RESCHEDULE_REQUESTED = "RESCHEDULE_REQUESTED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    # The buyer did not come (recorded by the owner, or by the operator after a dispute)
    NO_SHOW = "NO_SHOW"
    # The owner was not there (found by the operator after the buyer's dispute)
    OWNER_ABSENT = "OWNER_ABSENT"
    # Nobody recorded the outcome in time: closed without blaming anyone
    UNREPORTED = "UNREPORTED"
    # The viewing time passed before the owner answered the request: closed by itself
    EXPIRED = "EXPIRED"


# Statuses of a viewing that is still going on (asked for or confirmed)
ACTIVE_BOOKING_STATUSES = (
    BookingStatus.REQUESTED,
    BookingStatus.CONFIRMED,
    BookingStatus.RESCHEDULE_REQUESTED,
)

# Statuses that take the owner's time. Unanswered requests do not: several buyers may ask for the same
# time and the owner chooses whom to receive; confirming one closes the others that overlap.
OWNER_BUSY_STATUSES = (
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


class ConversationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    ESCALATED = "ESCALATED"


class MessageRole(StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    TOOL = "TOOL"


class NotificationChannel(StrEnum):
    IN_APP = "IN_APP"
    SMS = "SMS"
    ZALO = "ZALO"
    EMAIL = "EMAIL"


class NotificationStatus(StrEnum):
    PENDING = "PENDING"  # scheduled for later (reminders)
    SENT = "SENT"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"  # e.g. reminder of a viewing that was cancelled or moved


class EscalationType(StrEnum):
    """When a human must step in (spec §4.3, §4.8 HITL, §6.4)."""

    SELLER_NO_RESPONSE = "SELLER_NO_RESPONSE"
    NO_COMMON_SLOT = "NO_COMMON_SLOT"
    SCHEDULE_CONFLICT = "SCHEDULE_CONFLICT"
    PROPERTY_ISSUE = "PROPERTY_ISSUE"
    MULTI_BUYER = "MULTI_BUYER"
    SYSTEM_FAILURE = "SYSTEM_FAILURE"
    OTHER = "OTHER"
    # A seller cannot verify a red book on their own (no OTP, locked, mismatch, proxy, dispute...)
    OWNERSHIP_SUPPORT = "OWNERSHIP_SUPPORT"
    # The buyer disagrees with the recorded outcome of a viewing (came / the owner was not there)
    VIEWING_DISPUTE = "VIEWING_DISPUTE"


class EscalationStatus(StrEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


OPEN_ESCALATION_STATUSES = (EscalationStatus.OPEN, EscalationStatus.IN_PROGRESS)


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


class PropertyOwnershipVerification(Base):
    """Red book (sổ đỏ/sổ hồng) ground truth; a seller claims one by naming its holder + code and passing an OTP.

    Rows are loaded from the investor's records with `user_id` NULL; it is set when a seller verifies.
    A verified red book backs exactly one listing (`properties.verification_id`).
    """

    __tablename__ = "property_ownership_verifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    red_book_holder_name: Mapped[str] = mapped_column(String(255), nullable=False)
    red_book_code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    # Where the ownership OTP goes: the phone on record, not the seller's login phone
    owner_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[OwnershipVerificationStatus] = mapped_column(
        _enum(OwnershipVerificationStatus, "ownership_verification_status"),
        nullable=False,
        default=OwnershipVerificationStatus.UNVERIFIED,
    )
    otp_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The investor's own record of the home behind this red book: a listing takes these facts from here,
    # so the seller cannot list them wrong
    building_id: Mapped[int | None] = mapped_column(ForeignKey("buildings.id", ondelete="RESTRICT"))
    unit_code: Mapped[str | None] = mapped_column(String(50))
    property_type: Mapped[PropertyType | None] = mapped_column(_enum(PropertyType, "property_type"))
    area_m2: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    bedrooms: Mapped[int | None] = mapped_column(Integer)
    bathrooms: Mapped[int | None] = mapped_column(Integer)
    floor: Mapped[int | None] = mapped_column(Integer)
    direction: Mapped[Direction | None] = mapped_column(_enum(Direction, "direction"))
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
    # Red book proving ownership (verified by the seller: red book + OTP); the home's facts come from it
    verification_id: Mapped[int | None] = mapped_column(
        ForeignKey("property_ownership_verifications.id", ondelete="RESTRICT"), unique=True
    )
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
    verification: Mapped["PropertyOwnershipVerification | None"] = relationship()
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


class MediaFile(Base):
    """A photo a seller uploaded from their device (bytes kept here; see media_service)."""

    __tablename__ = "media_files"
    __table_args__ = (Index("ix_media_files_owner", "owner_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    # Identity / authorisation documents: only the uploader and the investor can open them
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
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
    # The AI recommendation that led the buyer to this property, if any (recommendation analytics)
    source_recommendation_id: Mapped[int | None] = mapped_column(
        ForeignKey("recommendations.id", ondelete="SET NULL", use_alter=True)
    )
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
        # The anti-double-booking guarantee: an owner never has two confirmed viewings at overlapping times,
        # on any of their homes (pending requests may overlap: the owner picks whom to receive)
        ExcludeConstraint(
            (column("owner_id"), "="),
            (column("period"), "&&"),
            using="gist",
            name="ex_bookings_owner_no_overlap",
            where=text("status IN ('CONFIRMED', 'RESCHEDULE_REQUESTED')"),
        ),
        Index("ix_bookings_customer", "customer_id"),
        Index("ix_bookings_owner", "owner_id"),
        Index("ix_bookings_status_start", "status", "start_at"),
        Index("ix_bookings_deal", "deal_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="RESTRICT"), nullable=False)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    # The home's owner, copied by a trigger (trg_bookings_set_owner) for the owner-level overlap constraint
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, server_default=FetchedValue()
    )
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
    # Times the owner offered instead when declining (the buyer can book one of them in a tap)
    suggested_starts: Mapped[list[datetime] | None] = mapped_column(ARRAY(DateTime(timezone=True)))
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


class AiConversation(Base):
    """One chat thread with the AI agent (spec §4.16): a signed-in buyer's, or a guest's (no buyer yet)."""

    __tablename__ = "ai_conversations"
    __table_args__ = (
        UniqueConstraint("buyer_id", "client_id", name="uq_ai_conversations_buyer_client"),
        Index("ix_ai_conversations_buyer_last", "buyer_id", "last_message_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # Null while a guest chats; set when the guest signs up and the conversation is claimed
    buyer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # Id chosen by the web client; the LangGraph thread is "<buyer_id>:<client_id>" ("guest:<client_id>")
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    status: Mapped[ConversationStatus] = mapped_column(
        _enum(ConversationStatus, "conversation_status"), nullable=False, default=ConversationStatus.ACTIVE
    )
    # Latest search criteria the agent extracted (spec §6.2 correction path starts from here)
    extracted_criteria: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = _now_column()
    last_message_at: Mapped[datetime] = _now_column()


class AiMessage(Base):
    """Every turn element: buyer text, assistant text/tool calls, tool results (for audit of AC-01)."""

    __tablename__ = "ai_messages"
    __table_args__ = (Index("ix_ai_messages_conversation", "conversation_id", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False)
    # The turn (trace) this message belongs to
    turn_id: Mapped[int | None] = mapped_column(ForeignKey("ai_turns.id", ondelete="SET NULL"))
    role: Mapped[MessageRole] = mapped_column(_enum(MessageRole, "message_role"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Assistant: requested tool calls. Tool: the call it answers.
    tool_calls: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    tool_name: Mapped[str | None] = mapped_column(String(64))
    tool_args: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # The structured envelope the tool returned ({"ok": ..., "data"|"error": ...})
    tool_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    tool_ok: Mapped[bool | None] = mapped_column(Boolean)
    model: Mapped[str | None] = mapped_column(String(64))
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    # Set on the final assistant reply: wall time of the whole turn (spec §2.2 latency p95)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = _now_column()


class AiTurn(Base):
    """Developer trace of one chat turn: who (buyer or guest), what was asked, how it went (ok / error), and each
    step with its timing — every model call and tool call. Not shown to buyers, sellers or operators."""

    __tablename__ = "ai_turns"
    __table_args__ = (Index("ix_ai_turns_created", "created_at"), Index("ix_ai_turns_status", "status", "created_at"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # Also in the server logs and the chat response, so a reported problem leads straight here
    trace_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("ai_conversations.id", ondelete="SET NULL"))
    buyer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    guest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    streamed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # OK, or ERROR (the turn failed: model unavailable, timeout, ...)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="OK")
    error_type: Mapped[str | None] = mapped_column(String(128))
    error_message: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(64))
    llm_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # [{"kind": "llm"|"tool", "name", "at_ms", "ms", "ok", "error"?, "prompt_tokens"?, ...}] in start order
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = _now_column()


class Recommendation(Base):
    """A property the agent showed the buyer, with why (explainability + Precision@5)."""

    __tablename__ = "recommendations"
    __table_args__ = (
        Index("ix_recommendations_conversation", "conversation_id"),
        Index("ix_recommendations_buyer_property", "buyer_id", "property_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False)
    ai_message_id: Mapped[int] = mapped_column(ForeignKey("ai_messages.id", ondelete="CASCADE"), nullable=False)
    # Null for a guest's conversation (until it is claimed at sign-up)
    buyer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), nullable=False)
    rank: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    match_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    # matched / unmatched criteria as returned by search (the explanation shown to the buyer)
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    criteria_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = _now_column()


class Notification(Base):
    """Event notifications and scheduled reminders (spec §4.19). In-app for now; SMS/Zalo provider is TBD."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index("ix_notifications_status_scheduled", "status", "scheduled_at"),
        Index("ix_notifications_booking", "booking_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    channel: Mapped[NotificationChannel] = mapped_column(
        _enum(NotificationChannel, "notification_channel"), nullable=False, default=NotificationChannel.IN_APP
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    deal_id: Mapped[int | None] = mapped_column(ForeignKey("deals.id", ondelete="SET NULL"))
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id", ondelete="SET NULL"))
    status: Mapped[NotificationStatus] = mapped_column(
        _enum(NotificationStatus, "notification_status"), nullable=False, default=NotificationStatus.SENT
    )
    # When a PENDING notification becomes due (reminders); NULL = immediate
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Guards against sending the same reminder twice, e.g. "booking:12:2030-01-05T15:00:T-2h:user:1"
    dedupe_key: Mapped[str | None] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = _now_column()


class Escalation(Base):
    """Operator exception queue item (spec §4.15 Operator 'Exception queue')."""

    __tablename__ = "escalations"
    __table_args__ = (
        Index("ix_escalations_status_created", "status", "created_at"),
        Index("ix_escalations_requester", "requester_id"),
        # At most one open escalation of a given type per booking (the no-response sweep relies on it)
        Index(
            "uq_escalations_open_booking_type",
            "booking_id",
            "type",
            unique=True,
            postgresql_where=text("status IN ('OPEN', 'IN_PROGRESS') AND booking_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    type: Mapped[EscalationType] = mapped_column(_enum(EscalationType, "escalation_type"), nullable=False)
    status: Mapped[EscalationStatus] = mapped_column(
        _enum(EscalationStatus, "escalation_status"), nullable=False, default=EscalationStatus.OPEN
    )
    raised_by: Mapped[ActorType] = mapped_column(_enum(ActorType, "actor_type"), nullable=False)
    # The buyer/seller this is about; told the outcome when it is resolved
    requester_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    deal_id: Mapped[int | None] = mapped_column(ForeignKey("deals.id", ondelete="SET NULL"))
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id", ondelete="SET NULL"))
    property_id: Mapped[int | None] = mapped_column(ForeignKey("properties.id", ondelete="SET NULL"))
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("ai_conversations.id", ondelete="SET NULL"))
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    resolution: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _now_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


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


class SystemSetting(Base):
    """Operational switches the operator changes at run time (shared by every API instance), e.g. the AI kill switch."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
