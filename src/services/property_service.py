"""Property listings: owner CRUD, operator moderation, customer search + recommendation."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from src.config import get_settings
from src.core.actor import Actor
from src.core.errors import BusinessRuleViolationError, NotFoundError, StateConflictError
from src.db.models import (
    ACTIVE_BOOKING_STATUSES,
    Booking,
    Building,
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
    PropertyCreate,
    PropertyOut,
    PropertyUpdate,
    Recommendation,
    SearchCriteria,
    SearchResult,
)
from src.services import audit, seller_service

# Listing lifecycle (spec §4.11). SOLD is terminal; a WITHDRAWN listing can be re-submitted.
_TRANSITIONS: dict[PropertyStatus, set[PropertyStatus]] = {
    PropertyStatus.DRAFT: {PropertyStatus.PENDING_REVIEW},
    PropertyStatus.REJECTED: {PropertyStatus.PENDING_REVIEW},
    PropertyStatus.PENDING_REVIEW: {PropertyStatus.AVAILABLE, PropertyStatus.REJECTED},
    PropertyStatus.AVAILABLE: {PropertyStatus.SOLD, PropertyStatus.WITHDRAWN},
    PropertyStatus.WITHDRAWN: {PropertyStatus.PENDING_REVIEW, PropertyStatus.SOLD},
    PropertyStatus.SOLD: set(),
}
# Content (including media) can only change while the listing is off the marketplace
_EDITABLE = {PropertyStatus.DRAFT, PropertyStatus.REJECTED, PropertyStatus.WITHDRAWN}
_MAX_CANDIDATES = 500


def media_url(s3_key: str) -> str:
    return get_settings().media_base_url + s3_key


def _media_out(m: PropertyMedia) -> MediaOut:
    return MediaOut(
        id=m.id,
        kind=m.kind,
        url=media_url(m.s3_key),
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
        created_at=p.created_at,
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


def list_by_status(db: Session, status: PropertyStatus) -> list[PropertyOut]:
    """Operator moderation queue."""
    stmt = _base_query().where(Property.status == status).order_by(Property.updated_at.asc())
    return [to_out(p, include_private=True) for p in db.scalars(stmt)]


# ---------- Owner writes ----------


def create(db: Session, actor: Actor, data: PropertyCreate) -> PropertyOut:
    if db.get(Building, data.building_id) is None:
        raise NotFoundError(f"Building {data.building_id} not found")
    prop = Property(owner_id=actor.id, status=PropertyStatus.DRAFT, **data.model_dump())
    db.add(prop)
    db.flush()
    audit.record(db, actor, "property.create", "property", prop.id, after={"status": prop.status.value})
    db.commit()
    return get_property(db, prop.id, actor)


def update(db: Session, actor: Actor, property_id: int, data: PropertyUpdate) -> PropertyOut:
    prop = _load_owned(db, actor, property_id)
    _require_editable(prop)
    changes = data.model_dump(exclude_unset=True)
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
            "Only DRAFT, REJECTED or WITHDRAWN listings can be edited",
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
    # Ownership documents are for the operator only, never for buyers
    is_public = data.is_public and data.kind != MediaKind.OWNERSHIP_DOC
    media = PropertyMedia(
        kind=data.kind,
        s3_key=data.s3_key,
        content_type=data.content_type,
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
    return get_property(db, prop.id, actor)


def submit_for_review(db: Session, actor: Actor, property_id: int) -> PropertyOut:
    prop = _load_owned(db, actor, property_id)
    # Spec §4.5: the operator checks ownership during listing review, so a document is required
    if not any(m.kind == MediaKind.OWNERSHIP_DOC for m in prop.media):
        raise BusinessRuleViolationError(
            "Upload an ownership document (sổ hồng / HĐMB) before submitting for review",
            details={"missing": MediaKind.OWNERSHIP_DOC.value},
        )
    before = _transition(prop, PropertyStatus.PENDING_REVIEW)
    prop.rejection_reason = None
    audit.record(
        db, actor, "property.submit", "property", prop.id, before={"status": before}, after={"status": prop.status}
    )
    db.commit()
    return get_property(db, prop.id, actor)


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


def mark_sold(db: Session, actor: Actor, property_id: int) -> PropertyOut:
    prop = _load_owned(db, actor, property_id)
    _require_no_active_bookings(db, prop, "marking the property as sold")
    before = _transition(prop, PropertyStatus.SOLD)
    audit.record(
        db, actor, "property.sold", "property", prop.id, before={"status": before}, after={"status": prop.status}
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
    if criteria.bedrooms_min is not None:
        stmt = stmt.where(Property.bedrooms >= criteria.bedrooms_min)
    if criteria.area_min is not None:
        stmt = stmt.where(Property.area_m2 >= criteria.area_min)
    if criteria.keyword:
        kw = criteria.keyword.strip()
        escaped = kw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(
            or_(
                Property.description.ilike(f"%{escaped}%", escape="\\"),
                func.word_similarity(kw, Property.description) > 0.4,
            )
        )

    candidates = list(db.scalars(stmt.order_by(Property.price_vnd).limit(_MAX_CANDIDATES)))
    ranked = sorted((_score(p, criteria) for p in candidates), key=lambda r: (-r.match_score, r.property.price_vnd))
    return SearchResult(total_candidates=len(candidates), results=ranked[: criteria.limit])


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
        if c.budget_min is not None and c.budget_max is not None:
            target = (c.budget_min + c.budget_max) / 2
        else:
            target = c.budget_max if c.budget_max is not None else c.budget_min
        score = _closeness(prop.price_vnd, target)
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
