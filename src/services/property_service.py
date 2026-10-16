"""Property listings: owner CRUD, operator moderation, customer search + recommendation."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import SEEK_END
from typing import BinaryIO
from uuid import uuid4

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from src.config import get_settings
from src.core.actor import Actor
from src.core.errors import BusinessRuleViolationError, NotFoundError, StateConflictError, StorageUnavailableError
from src.db.models import (
    ACTIVE_BOOKING_STATUSES,
    AvailabilitySlot,
    Booking,
    BookingStatus,
    Building,
    LegalStatus,
    MediaKind,
    Project,
    Property,
    PropertyMedia,
    PropertyStatus,
    SellerProfile,
    SellerVerificationStatus,
    User,
    UserRole,
    UserStatus,
)
from src.models.property import (
    CriterionMatch,
    MediaCreate,
    MediaOut,
    OwnerOverview,
    OwnerPropertyStats,
    PropertyCreate,
    PropertyOut,
    PropertyUpdate,
    Recommendation,
    SearchCriteria,
    SearchResult,
)
from src.services import (
    audit,
    availability_service,
    media_service,
    notification_service,
    ownership_service,
    seller_service,
    storage_service,
)

# Listing lifecycle (spec §4.11). SOLD is terminal; a WITHDRAWN listing can be re-submitted.
_TRANSITIONS: dict[PropertyStatus, set[PropertyStatus]] = {
    PropertyStatus.DRAFT: {PropertyStatus.PENDING_REVIEW},
    # A home can be sold while its listing waits for review or was turned down
    PropertyStatus.REJECTED: {PropertyStatus.PENDING_REVIEW, PropertyStatus.SOLD},
    PropertyStatus.PENDING_REVIEW: {PropertyStatus.AVAILABLE, PropertyStatus.REJECTED, PropertyStatus.SOLD},
    # REJECTED from AVAILABLE: the investor takes a live listing down (with a reason); the seller fixes and resubmits
    PropertyStatus.AVAILABLE: {PropertyStatus.SOLD, PropertyStatus.WITHDRAWN, PropertyStatus.REJECTED},
    PropertyStatus.WITHDRAWN: {PropertyStatus.PENDING_REVIEW, PropertyStatus.SOLD},
    PropertyStatus.SOLD: set(),
}
# Content (including media) can only change while the listing is off the marketplace
# Facts of the home a listing takes from its red book (the investor's record), not from the seller
RED_BOOK_FIELDS = (
    "building_id",
    "unit_code",
    "property_type",
    "area_m2",
    "bedrooms",
    "bathrooms",
    "floor",
    "direction",
)

# A listing waiting for review can still be corrected (a wrong detail would only get it rejected)
_EDITABLE = {PropertyStatus.DRAFT, PropertyStatus.PENDING_REVIEW, PropertyStatus.REJECTED, PropertyStatus.WITHDRAWN}
_MAX_CANDIDATES = 500

# Uploads: allowed file types per media kind, and size limits (Supabase free tier caps files at 50 MB)
_UPLOAD_TYPES: dict[MediaKind, set[str]] = {
    MediaKind.IMAGE: {"image/jpeg", "image/png", "image/webp"},
    MediaKind.FLOORPLAN: {"image/jpeg", "image/png", "image/webp", "application/pdf"},
    MediaKind.VIDEO: {"video/mp4", "video/webm"},
    MediaKind.OWNERSHIP_DOC: {"application/pdf", "image/jpeg", "image/png"},
}
_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "application/pdf": "pdf",
    "video/mp4": "mp4",
    "video/webm": "webm",
}
_MAX_UPLOAD_MB: dict[MediaKind, int] = {MediaKind.VIDEO: 50}
_DEFAULT_MAX_UPLOAD_MB = 10


def media_url(s3_key: str) -> str:
    # Photos uploaded from a device are served by this API: a full URL when the web app is on another domain
    if s3_key.startswith("/api/"):
        return get_settings().public_api_url.rstrip("/") + s3_key
    # A path or full URL (the demo photos shipped with the web app, see seed.ensure_photos) is used as is
    if s3_key.startswith(("/", "http://", "https://")):
        return s3_key
    return get_settings().media_base_url + s3_key


def _media_out(m: PropertyMedia) -> MediaOut:
    # Private media sits in the private bucket: hand out a short-lived signed URL instead of a public one
    url = (
        storage_service.signed_url(m.s3_key)
        if not m.is_public and storage_service.is_enabled()
        else media_url(m.s3_key)
    )
    return MediaOut(
        id=m.id,
        kind=m.kind,
        url=url,
        content_type=m.content_type,
        sort_order=m.sort_order,
        is_public=m.is_public,
    )


def to_out(p: Property, *, include_private: bool = False) -> PropertyOut:
    media = [m for m in p.media if include_private or m.is_public]
    return PropertyOut(
        id=p.id,
        owner_id=p.owner_id,
        building_id=p.building_id,
        unit_code=p.unit_code,
        property_type=p.property_type,
        bedrooms=p.bedrooms,
        bathrooms=p.bathrooms,
        area_m2=p.area_m2,
        floor=p.floor,
        price_vnd=p.price_vnd,
        direction=p.direction,
        view=p.view,
        furnishing=p.furnishing,
        legal_status=p.legal_status,
        description=p.description,
        status=p.status,
        project_code=p.building.project.code,
        project_name=p.building.project.name,
        building_name=p.building.name,
        city=p.building.project.city,
        rejection_reason=p.rejection_reason,
        verified_red_book=p.verification_id is not None,
        red_book_code=p.verification.red_book_code if include_private and p.verification else None,
        created_at=p.created_at,
        updated_at=p.updated_at,
        media=[_media_out(m) for m in media],
        image_urls=[media_url(m.s3_key) for m in media if m.kind == MediaKind.IMAGE and m.is_public],
    )


def _base_query() -> Select[tuple[Property]]:
    return select(Property).options(
        joinedload(Property.building, innerjoin=True).joinedload(Building.project, innerjoin=True),
        selectinload(Property.media),
    )


def _load(db: Session, property_id: int, *, for_update: bool = False) -> Property:
    stmt = _base_query().where(Property.id == property_id)
    if for_update:
        stmt = stmt.with_for_update(of=Property)
    prop = db.scalar(stmt)
    if prop is None:
        raise NotFoundError(f"Property {property_id} not found")
    return prop


def _transition(prop: Property, to: PropertyStatus) -> PropertyStatus:
    if to not in _TRANSITIONS[prop.status]:
        raise StateConflictError(
            f"Cannot move listing from {prop.status.value} to {to.value}",
            details={"current_status": prop.status.value},
        )
    before = prop.status
    prop.status = to
    return before


def _load_owned(db: Session, actor: Actor, property_id: int) -> Property:
    prop = _load(db, property_id, for_update=True)
    if prop.owner_id != actor.id:
        # Don't reveal other owners' listings
        raise NotFoundError(f"Property {property_id} not found")
    return prop


# ---------- Reads ----------


def list_projects(db: Session) -> list[Project]:
    return list(db.scalars(select(Project).options(joinedload(Project.buildings)).order_by(Project.name)).unique())


def get_property(db: Session, property_id: int, actor: Actor | None = None) -> PropertyOut:
    """Customers/anonymous only see AVAILABLE listings; owners see their own; operators see all.

    Private media (ownership documents) is only returned to the owner and operators.
    """
    prop = _load(db, property_id)
    privileged = actor is not None and (actor.role == UserRole.INVESTOR_OPERATOR or prop.owner_id == actor.id)
    if not (prop.status == PropertyStatus.AVAILABLE or privileged):
        raise NotFoundError(f"Property {property_id} not found")
    return to_out(prop, include_private=privileged)


def list_owned(db: Session, actor: Actor) -> list[PropertyOut]:
    stmt = _base_query().where(Property.owner_id == actor.id).order_by(Property.created_at.desc())
    return [to_out(p, include_private=True) for p in db.scalars(stmt)]


def owner_overview(db: Session, actor: Actor) -> OwnerOverview:
    """Per-listing numbers for the seller's dashboard: viewing requests (all / waiting for them) and AI exposure."""
    # Imported here: the db models module also defines `Recommendation`, a name this module uses for the schema
    from src.db.models import Recommendation as Suggested

    ids = list(db.scalars(select(Property.id).where(Property.owner_id == actor.id)))
    waiting = (BookingStatus.REQUESTED, BookingStatus.RESCHEDULE_REQUESTED)
    requests = dict(
        db.execute(
            select(Booking.property_id, func.count()).where(Booking.property_id.in_(ids)).group_by(Booking.property_id)
        ).all()
    )
    pending = dict(
        db.execute(
            select(Booking.property_id, func.count())
            .where(
                Booking.property_id.in_(ids),
                Booking.status.in_(waiting),
                # Still answerable: the (proposed) viewing time has not passed yet
                func.coalesce(Booking.proposed_start_at, Booking.start_at) > datetime.now(UTC),
            )
            .group_by(Booking.property_id)
        ).all()
    )
    shown = dict(
        db.execute(
            select(Suggested.property_id, func.count())
            # Signed-in buyers only (as the stat says); guests' chats are stored too, for developers
            .where(Suggested.property_id.in_(ids), Suggested.buyer_id.is_not(None))
            .group_by(Suggested.property_id)
        ).all()
    )
    now = datetime.now(UTC)
    slots = dict(
        db.execute(
            select(AvailabilitySlot.property_id, func.count())
            .where(
                AvailabilitySlot.property_id.in_(ids),
                AvailabilitySlot.start_at > now,
                AvailabilitySlot.start_at <= now + timedelta(days=7),
                # Only times still open: not already given to a confirmed viewing
                ~availability_service.slot_taken(),
            )
            .group_by(AvailabilitySlot.property_id)
        ).all()
    )
    return OwnerOverview(
        response_hours=get_settings().seller_response_hours,
        properties=[
            OwnerPropertyStats(
                property_id=i,
                viewing_requests=requests.get(i, 0),
                pending_requests=pending.get(i, 0),
                ai_suggestions=shown.get(i, 0),
                open_slots_week=slots.get(i, 0),
            )
            for i in ids
        ],
    )


def list_by_status(db: Session, status: PropertyStatus) -> list[PropertyOut]:
    """Operator moderation queue."""
    stmt = _base_query().where(Property.status == status).order_by(Property.updated_at.asc())
    out = []
    for p in db.scalars(stmt):
        item = to_out(p, include_private=True)
        item.owner_name, item.owner_phone = p.owner.full_name, p.owner.phone
        out.append(item)
    return out


# ---------- Owner writes ----------


def create(db: Session, actor: Actor, data: PropertyCreate) -> PropertyOut:
    """ "Đăng tin bán": the listing, its photos and the request for review in one step (there are no drafts)."""
    if db.get(Building, data.building_id) is None:
        raise NotFoundError(f"Building {data.building_id} not found")
    record = ownership_service.require_usable(db, actor, data.verification_id)
    fields = data.model_dump(exclude={"photos"})
    # The home's facts come from the red book (the investor's data), whatever the form sent
    unit = ownership_service.unit_of(db, record)
    if unit is not None:
        fields.update(unit.model_dump(include=set(RED_BOOK_FIELDS)), legal_status=LegalStatus.PINK_BOOK)
    prop = Property(owner_id=actor.id, status=PropertyStatus.DRAFT, **fields)
    db.add(prop)
    for order, key in enumerate(data.photos):
        upload = media_service.require_own_upload(db, actor, key)
        prop.media.append(
            PropertyMedia(
                kind=MediaKind.IMAGE,
                s3_key=key,
                content_type=upload.content_type if upload else "image/jpeg",
                sort_order=order,
                is_public=True,
            )
        )
    db.flush()
    audit.record(
        db,
        actor,
        "property.create",
        "property",
        prop.id,
        after={"status": prop.status.value, "photos": len(data.photos)},
    )
    _submit(db, actor, prop)
    db.commit()
    return get_property(db, prop.id, actor)


def update(db: Session, actor: Actor, property_id: int, data: PropertyUpdate) -> PropertyOut:
    prop = _load_owned(db, actor, property_id)
    _require_editable(prop)
    changes = data.model_dump(exclude_unset=True)
    # Facts taken from the red book cannot be changed by the seller (sending the same value is fine)
    if prop.verification and ownership_service.unit_of(db, prop.verification) is not None:
        locked = {k for k in (*RED_BOOK_FIELDS, "legal_status") if k in changes and changes[k] != getattr(prop, k)}
        if locked:
            raise BusinessRuleViolationError(
                "These details come from the red book and cannot be changed", details={"fields": sorted(locked)}
            )
    before = {k: _jsonable(getattr(prop, k)) for k in changes}
    for key, value in changes.items():
        setattr(prop, key, value)
    audit.record(
        db,
        actor,
        "property.update",
        "property",
        prop.id,
        before=before,
        after={k: _jsonable(v) for k, v in changes.items()},
    )
    db.commit()
    return get_property(db, prop.id, actor)


def _require_editable(prop: Property) -> None:
    if prop.status not in _EDITABLE:
        raise StateConflictError(
            "Only listings waiting for review, rejected or withdrawn can be edited",
            details={"current_status": prop.status.value},
        )


def _require_no_active_bookings(db: Session, prop: Property, action: str) -> None:
    active = db.scalar(
        select(func.count())
        .select_from(Booking)
        .where(Booking.property_id == prop.id, Booking.status.in_(ACTIVE_BOOKING_STATUSES))
    )
    if active:
        raise StateConflictError(f"Resolve active bookings before {action}", details={"active": active})


def add_media(db: Session, actor: Actor, property_id: int, data: MediaCreate) -> PropertyOut:
    prop = _load_owned(db, actor, property_id)
    _require_editable(prop)
    # Photos are files on BookingBot's own storage (uploaded, or a storage key), never a link to another site:
    # an outside image could change, track buyers, or show anything
    if "://" in data.s3_key or data.s3_key.startswith("//"):
        raise BusinessRuleViolationError(
            "Upload the photo; links to other sites are not accepted", details={"reason": "EXTERNAL_URL"}
        )
    upload = media_service.require_own_upload(db, actor, data.s3_key)
    if data.kind == MediaKind.IMAGE:
        limit = get_settings().media_max_photos
        if sum(m.kind == MediaKind.IMAGE for m in prop.media) >= limit:
            raise BusinessRuleViolationError(f"A listing can have at most {limit} photos", details={"max": limit})
    # Ownership documents are for the operator only, never for buyers
    is_public = data.is_public and data.kind != MediaKind.OWNERSHIP_DOC
    # Private keys get signed download URLs, so an owner may only register files stored under their own listing
    if not is_public and storage_service.is_enabled() and not data.s3_key.startswith(_key_prefix(prop.id)):
        raise BusinessRuleViolationError(
            "Private documents must be uploaded through the upload endpoint", details={"s3_key": data.s3_key}
        )
    media = PropertyMedia(
        kind=data.kind,
        s3_key=data.s3_key,
        content_type=upload.content_type if upload else data.content_type,
        sort_order=data.sort_order,
        is_public=is_public,
    )
    prop.media.append(media)
    db.flush()
    audit.record(db, actor, "property.media_add", "property", prop.id, after={"media_id": media.id, "kind": media.kind})
    db.commit()
    return get_property(db, prop.id, actor)


def delete_media(db: Session, actor: Actor, property_id: int, media_id: int) -> PropertyOut:
    prop = _load_owned(db, actor, property_id)
    _require_editable(prop)
    media = db.get(PropertyMedia, media_id)
    if media is None or media.property_id != prop.id:
        raise NotFoundError(f"Media {media_id} not found")
    prop.media.remove(media)  # delete-orphan cascade removes the row
    audit.record(db, actor, "property.media_delete", "property", prop.id, before={"media_id": media_id})
    db.commit()
    # Only remove files uploaded for this listing: a manually registered key may point at someone else's file
    if media.s3_key.startswith(_key_prefix(prop.id)):
        storage_service.delete(media.s3_key, private=not media.is_public)
    return get_property(db, prop.id, actor)


def _key_prefix(property_id: int) -> str:
    return f"properties/{property_id}/"


def upload_media(
    db: Session, actor: Actor, property_id: int, kind: MediaKind, file: BinaryIO, content_type: str
) -> PropertyOut:
    """Store a file in object storage, then register it as listing media."""
    if not storage_service.is_enabled():
        raise StorageUnavailableError("Media storage is not configured")
    allowed = _UPLOAD_TYPES[kind]
    if content_type not in allowed:
        raise BusinessRuleViolationError(
            f"File type {content_type or 'unknown'} is not allowed for {kind.value}",
            details={"allowed": sorted(allowed)},
        )
    file.seek(0, SEEK_END)
    size = file.tell()
    file.seek(0)
    max_mb = _MAX_UPLOAD_MB.get(kind, _DEFAULT_MAX_UPLOAD_MB)
    if size == 0 or size > max_mb * 1024 * 1024:
        raise BusinessRuleViolationError(f"File must be between 1 byte and {max_mb} MB", details={"max_mb": max_mb})

    # Check ownership and status before uploading; add_media re-checks both under the row lock
    prop = _load_owned(db, actor, property_id)
    _require_editable(prop)
    sort_order = len(prop.media)
    db.rollback()  # don't hold the row lock during the upload

    private = kind == MediaKind.OWNERSHIP_DOC
    key = f"{_key_prefix(property_id)}{uuid4().hex}.{_EXTENSIONS[content_type]}"
    storage_service.upload(key, file, content_type, private=private)
    data = MediaCreate(kind=kind, s3_key=key, content_type=content_type, sort_order=sort_order, is_public=not private)
    try:
        return add_media(db, actor, property_id, data)
    except Exception:
        db.rollback()
        storage_service.delete(key, private=private)
        raise


def submit_for_review(db: Session, actor: Actor, property_id: int) -> PropertyOut:
    prop = _load_owned(db, actor, property_id)
    _submit(db, actor, prop)
    db.commit()
    return get_property(db, prop.id, actor)


def _submit(db: Session, actor: Actor, prop: Property) -> None:
    # Spec §4.5: ownership is proven by a verified red book (red book + OTP), checked by the seller themselves
    if prop.verification_id is None:
        raise BusinessRuleViolationError(
            "Verify the red book of this home before submitting it for review",
            details={"missing": "OWNERSHIP_VERIFICATION"},
        )
    before = _transition(prop, PropertyStatus.PENDING_REVIEW)
    prop.rejection_reason = None
    audit.record(
        db, actor, "property.submit", "property", prop.id, before={"status": before}, after={"status": prop.status}
    )


def withdraw(db: Session, actor: Actor, property_id: int) -> PropertyOut:
    """Owner takes an AVAILABLE listing off the marketplace (it can be re-submitted later)."""
    prop = _load_owned(db, actor, property_id)
    _require_no_active_bookings(db, prop, "withdrawing the listing")
    before = _transition(prop, PropertyStatus.WITHDRAWN)
    audit.record(
        db, actor, "property.withdraw", "property", prop.id, before={"status": before}, after={"status": prop.status}
    )
    db.commit()
    return get_property(db, prop.id, actor)


def mark_sold(db: Session, actor: Actor, property_id: int, buyer_id: int | None = None) -> PropertyOut:
    """Final: the listing closes, and every viewing still ahead of it is closed with its buyer told the home was
    sold (same transaction). A viewing whose time has come stays for its outcome. `buyer_id`: the BookingBot
    buyer it went to, who must have viewed it here; every other buyer's deal on it is closed and they are told."""
    from src.services import booking_service  # imported here: booking_service is a lower layer

    prop = _load_owned(db, actor, property_id)
    if buyer_id is not None and buyer_id not in booking_service.viewed_by(db, prop.id):
        raise BusinessRuleViolationError(
            "Choose a buyer who viewed this home on BookingBot, or none", details={"reason": "BUYER_DID_NOT_VIEW"}
        )
    before = _transition(prop, PropertyStatus.SOLD)
    prop.sold_to_user_id = buyer_id
    closed = booking_service.close_for_sold(db, actor, prop)
    audit.record(
        db,
        actor,
        "property.sold",
        "property",
        prop.id,
        before={"status": before},
        after={"status": prop.status},
        extra={"viewings_closed": closed, "sold_to": buyer_id},
    )
    db.commit()
    return get_property(db, prop.id, actor)


# ---------- Operator moderation ----------


def approve(db: Session, actor: Actor, property_id: int) -> PropertyOut:
    prop = _load(db, property_id, for_update=True)
    # Spec §2.3 principle 5: only verified sellers' properties enter the marketplace
    seller_service.require_verified(db, prop.owner_id)
    before = _transition(prop, PropertyStatus.AVAILABLE)
    prop.reviewed_by = actor.id
    prop.reviewed_at = datetime.now(UTC)
    prop.rejection_reason = None
    audit.record(
        db, actor, "property.approve", "property", prop.id, before={"status": before}, after={"status": prop.status}
    )
    notification_service.listing_reviewed(db, prop, approved=True)
    # The agent tells buyers whose remembered needs this home fits (imported here: it uses this module)
    from src.services import agent_followup

    agent_followup.announce_listing(db, prop)
    db.commit()
    return get_property(db, prop.id, actor)


def take_down(db: Session, actor: Actor, property_id: int, reason: str) -> PropertyOut:
    """The investor takes a live listing off the market (wrong photos found later, a complaint...). It goes back to
    the seller as REJECTED with the reason; viewings still ahead are closed and those buyers told."""
    from src.services import booking_service  # imported here: booking_service is a lower layer

    prop = _load(db, property_id, for_update=True)
    if prop.status != PropertyStatus.AVAILABLE:
        raise StateConflictError(
            "Only a listing on the market can be taken down", details={"status": prop.status.value}
        )
    before = _transition(prop, PropertyStatus.REJECTED)
    prop.rejection_reason = reason
    prop.reviewed_by = actor.id
    prop.reviewed_at = datetime.now(UTC)
    closed, _ = booking_service.close_ahead(
        db,
        actor,
        prop,
        booking_service.LISTING_DOWN_REASON,
        lambda b, was_confirmed: notification_service.viewing_listing_down(db, b, was_confirmed=was_confirmed),
    )
    audit.record(
        db,
        actor,
        "property.take_down",
        "property",
        prop.id,
        before={"status": before},
        after={"status": prop.status, "reason": reason},
        extra={"viewings_closed": closed},
    )
    notification_service.listing_taken_down(db, prop, reason, closed)
    db.commit()
    return get_property(db, prop.id, actor)


def reject(db: Session, actor: Actor, property_id: int, reason: str) -> PropertyOut:
    prop = _load(db, property_id, for_update=True)
    before = _transition(prop, PropertyStatus.REJECTED)
    prop.reviewed_by = actor.id
    prop.reviewed_at = datetime.now(UTC)
    prop.rejection_reason = reason
    audit.record(
        db,
        actor,
        "property.reject",
        "property",
        prop.id,
        before={"status": before},
        after={"status": prop.status, "reason": reason},
    )
    notification_service.listing_reviewed(db, prop, approved=False, reason=reason)
    db.commit()
    return get_property(db, prop.id, actor)


# ---------- Search + recommendation (spec §4.6 / §10.3) ----------


def search(db: Session, criteria: SearchCriteria) -> SearchResult:
    """Step 1 hard filters in SQL, then soft scoring + priority weighting in Python.

    Only AVAILABLE listings of ACTIVE, VERIFIED owners are ever returned, so the AI cannot
    recommend unapproved or invented properties (AC-01, AC-04).
    """
    stmt = (
        _base_query()
        .join(Property.building)
        .join(Building.project)
        .join(User, User.id == Property.owner_id)
        .join(SellerProfile, SellerProfile.user_id == Property.owner_id)
        .where(
            Property.status == PropertyStatus.AVAILABLE,
            User.status == UserStatus.ACTIVE,
            SellerProfile.verification_status == SellerVerificationStatus.VERIFIED,
        )
    )
    if criteria.project_codes:
        stmt = stmt.where(Project.code.in_([c.upper() for c in criteria.project_codes]))
    if criteria.property_types:
        stmt = stmt.where(Property.property_type.in_(criteria.property_types))
    if criteria.budget_min is not None:
        stmt = stmt.where(Property.price_vnd >= criteria.budget_min)
    if criteria.budget_max is not None:
        stmt = stmt.where(Property.price_vnd <= criteria.budget_max)
    if criteria.bedrooms is not None:
        stmt = stmt.where(Property.bedrooms == criteria.bedrooms)
    if criteria.bedrooms_min is not None:
        stmt = stmt.where(Property.bedrooms >= criteria.bedrooms_min)
    if criteria.area_min is not None:
        stmt = stmt.where(Property.area_m2 >= criteria.area_min)
    if criteria.keyword:
        kw = criteria.keyword.strip()
        escaped = kw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(
            or_(
                # A unit code the buyer names ("căn S1.08-2410") finds that home directly
                Property.unit_code.ilike(f"%{escaped}%", escape="\\"),
                Property.description.ilike(f"%{escaped}%", escape="\\"),
                func.word_similarity(kw, Property.description) > 0.4,
            )
        )

    candidates = list(db.scalars(stmt.order_by(Property.price_vnd).limit(_MAX_CANDIDATES)))
    ranked = sorted((_score(p, criteria) for p in candidates), key=lambda r: (-r.match_score, r.property.price_vnd))
    return SearchResult(total_candidates=len(candidates), results=ranked[: criteria.limit])


def match(prop: Property, criteria: SearchCriteria) -> Recommendation | None:
    """One property against saved criteria: None when a hard constraint rules it out, else its ranking.

    Same rules as `search` (minus the keyword), for checking a newly approved listing against buyers' needs.
    """
    c = criteria
    if c.project_codes and prop.building.project.code not in {code.upper() for code in c.project_codes}:
        return None
    if c.property_types and prop.property_type not in c.property_types:
        return None
    if (c.budget_min is not None and prop.price_vnd < c.budget_min) or (
        c.budget_max is not None and prop.price_vnd > c.budget_max
    ):
        return None
    if c.bedrooms is not None and prop.bedrooms != c.bedrooms:
        return None
    if c.bedrooms_min is not None and prop.bedrooms < c.bedrooms_min:
        return None
    if c.area_min is not None and prop.area_m2 < c.area_min:
        return None
    return _score(prop, c)


_PRIORITY_MULTIPLIER = {"high": 2.0, "normal": 1.0, "low": 0.5}


def _score(prop: Property, c: SearchCriteria) -> Recommendation:
    s = get_settings()
    parts: list[tuple[float, CriterionMatch]] = []

    def add(name: str, weight: float, score: float, matched: bool, wanted: str, actual: str) -> None:
        multiplier = _PRIORITY_MULTIPLIER[c.priorities.get(name, "normal")]
        parts.append(
            (
                weight * multiplier,
                CriterionMatch(criterion=name, matched=matched, score=round(score, 3), wanted=wanted, actual=actual),
            )
        )

    if c.budget_min is not None or c.budget_max is not None:
        # The budget is a hard filter: every home left is within it. Being closer to the cap is not
        # "a better match" (it used to rank a 4,85 tỷ home above a 3,5 tỷ one for "dưới 5 tỷ");
        # among equally good homes the cheaper one comes first (see `search`).
        score = 1.0
        wanted = (
            f"{_fmt_vnd(c.budget_min) if c.budget_min else '0'} - {_fmt_vnd(c.budget_max) if c.budget_max else '∞'}"
        )
        add("price", s.score_weight_price, score, True, wanted, _fmt_vnd(prop.price_vnd))

    if c.preferred_area_m2 is not None:
        score = _closeness(float(prop.area_m2), float(c.preferred_area_m2))
        add("area", s.score_weight_area, score, score >= 0.9, f"~{c.preferred_area_m2} m²", f"{prop.area_m2} m²")

    if c.preferred_bedrooms is not None:
        diff = abs(prop.bedrooms - c.preferred_bedrooms)
        score = {0: 1.0, 1: 0.5}.get(diff, 0.0)
        add("bedrooms", s.score_weight_bedrooms, score, diff == 0, str(c.preferred_bedrooms), str(prop.bedrooms))

    if c.preferred_directions:
        ok = prop.direction in c.preferred_directions
        add("direction", s.score_weight_direction, float(ok), ok, _join(c.preferred_directions), prop.direction.value)

    if c.preferred_views:
        ok = prop.view in c.preferred_views
        add("view", s.score_weight_view, float(ok), ok, _join(c.preferred_views), prop.view.value)

    if c.preferred_floor_min is not None or c.preferred_floor_max is not None:
        lo = c.preferred_floor_min if c.preferred_floor_min is not None else -(10**6)
        hi = c.preferred_floor_max if c.preferred_floor_max is not None else 10**6
        distance = 0 if lo <= prop.floor <= hi else min(abs(prop.floor - lo), abs(prop.floor - hi))
        score = max(0.0, 1 - distance / 10)
        wanted = f"{c.preferred_floor_min if c.preferred_floor_min is not None else ''}-{c.preferred_floor_max if c.preferred_floor_max is not None else ''}"
        add("floor", s.score_weight_floor, score, distance == 0, wanted, str(prop.floor))

    if c.preferred_furnishing is not None:
        ok = prop.furnishing == c.preferred_furnishing
        add("furnishing", s.score_weight_furnishing, float(ok), ok, c.preferred_furnishing.value, prop.furnishing.value)

    total_weight = sum(w for w, _ in parts)
    match_score = sum(w * m.score for w, m in parts) / total_weight if total_weight else 1.0
    return Recommendation(
        property=to_out(prop),
        match_score=round(match_score, 3),
        matched=[m for _, m in parts if m.matched],
        unmatched=[m for _, m in parts if not m.matched],
    )


def _closeness(actual: float, target: float) -> float:
    """1.0 when equal, falling linearly to 0 at 100% relative difference."""
    if target <= 0:
        return 0.0
    return max(0.0, 1 - abs(actual - target) / target)


def _fmt_vnd(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"{value / 1_000_000_000:.2f} tỷ"


def _join(values: list) -> str:
    return ",".join(v.value for v in values)


def _jsonable(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    return value
