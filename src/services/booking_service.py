"""Viewing bookings: request -> owner approval (HITL) -> confirmed hold -> completed/cancelled.

Safety rules enforced here (not in the UI or the prompt):
- Only the property's owner can confirm or reject (AC-02).
- Only one active booking per property per time window; enforced by the DB exclusion
  constraint, so concurrent requests cannot both succeed (AC-03).
- Invalid status transitions are rejected (F10).
- Every change writes an audit row in the same transaction.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from src.core.actor import Actor
from src.core.errors import (
    BusinessRuleViolationError,
    ForbiddenError,
    NotFoundError,
    SlotUnavailableError,
    StateConflictError,
)
from src.db.models import (
    AvailabilitySlot,
    Booking,
    BookingStatus,
    Building,
    Property,
    PropertyStatus,
    UserRole,
)
from src.models.booking import BookingCreate, BookingOut
from src.services import audit, seller_service
from src.services.availability_service import is_exclusion_violation, list_slots

_TRANSITIONS: dict[BookingStatus, set[BookingStatus]] = {
    BookingStatus.REQUESTED: {BookingStatus.CONFIRMED, BookingStatus.REJECTED, BookingStatus.CANCELLED},
    BookingStatus.CONFIRMED: {BookingStatus.COMPLETED, BookingStatus.CANCELLED},
    BookingStatus.REJECTED: set(),
    BookingStatus.CANCELLED: set(),
    BookingStatus.COMPLETED: set(),
}
_CONTACT_VISIBLE_TO_OWNER = {BookingStatus.CONFIRMED, BookingStatus.COMPLETED}


def _now() -> datetime:
    return datetime.now(UTC)


def _load(db: Session, booking_id: int, *, for_update: bool = False) -> Booking:
    stmt = (
        select(Booking)
        .options(
            joinedload(Booking.property, innerjoin=True)
            .joinedload(Property.building, innerjoin=True)
            .joinedload(Building.project, innerjoin=True),
            joinedload(Booking.customer, innerjoin=True),
        )
        .where(Booking.id == booking_id)
    )
    if for_update:
        stmt = stmt.with_for_update(of=Booking)
    booking = db.scalar(stmt)
    if booking is None:
        raise NotFoundError(f"Booking {booking_id} not found")
    return booking


def _can_view(booking: Booking, actor: Actor) -> bool:
    return (
        actor.role == UserRole.INVESTOR_OPERATOR
        or booking.customer_id == actor.id
        or booking.property.owner_id == actor.id
    )


def _transition(booking: Booking, to: BookingStatus) -> BookingStatus:
    if to not in _TRANSITIONS[booking.status]:
        raise StateConflictError(
            f"Cannot move booking from {booking.status.value} to {to.value}",
            details={"current_status": booking.status.value},
        )
    before = booking.status
    booking.status = to
    return before


def to_out(booking: Booking, viewer: Actor) -> BookingOut:
    prop = booking.property
    show_contact = (
        viewer.role == UserRole.INVESTOR_OPERATOR
        or viewer.id == booking.customer_id
        or booking.status in _CONTACT_VISIBLE_TO_OWNER
    )
    return BookingOut(
        id=booking.id,
        property_id=prop.id,
        property_label=f"{prop.building.project.name} · {prop.building.name} · {prop.unit_code}",
        customer_id=booking.customer_id,
        # Name is needed for the owner to decide; phone only after confirmation
        customer_name=booking.customer.full_name,
        customer_phone=booking.customer.phone if show_contact else None,
        start_at=booking.start_at,
        end_at=booking.end_at,
        status=booking.status,
        created_via=booking.created_via,
        customer_note=booking.customer_note,
        rejection_reason=booking.rejection_reason,
        responded_at=booking.responded_at,
        created_at=booking.created_at,
    )


def _audit_transition(db: Session, actor: Actor, action: str, booking: Booking, before: BookingStatus, **extra) -> None:
    audit.record(
        db,
        actor,
        action,
        "booking",
        booking.id,
        before={"status": before},
        after={"status": booking.status, **extra},
    )


# ---------- Customer ----------


def create_request(db: Session, actor: Actor, data: BookingCreate) -> BookingOut:
    if actor.role != UserRole.CUSTOMER:
        raise ForbiddenError("Only customers can request viewings")

    prop = db.get(Property, data.property_id)
    if prop is None or prop.status != PropertyStatus.AVAILABLE:
        raise NotFoundError(f"Property {data.property_id} not found")
    seller_service.require_verified(db, prop.owner_id)  # AC-04
    slot = db.get(AvailabilitySlot, data.slot_id)
    if slot is None or slot.property_id != prop.id:
        raise NotFoundError(f"Slot {data.slot_id} not found for property {prop.id}")
    if slot.start_at <= _now():
        raise BusinessRuleViolationError("This slot has already started")

    booking = Booking(
        property_id=prop.id,
        customer_id=actor.id,
        slot_id=slot.id,
        start_at=slot.start_at,
        end_at=slot.end_at,
        status=BookingStatus.REQUESTED,
        created_via=actor.via,
        customer_note=data.note,
    )
    db.add(booking)
    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        if is_exclusion_violation(e):
            # Someone else holds this window: return alternatives so UI/AI can re-offer (F3/F5)
            raise SlotUnavailableError(
                "This viewing slot was just taken",
                details={"free_slots": [s.model_dump(mode="json") for s in list_slots(db, prop.id)]},
            ) from e
        raise
    audit.record(
        db,
        actor,
        "booking.request",
        "booking",
        booking.id,
        after={"status": booking.status, "property_id": prop.id, "slot_id": slot.id},
    )
    db.commit()
    return to_out(_load(db, booking.id), actor)


def cancel(db: Session, actor: Actor, booking_id: int) -> BookingOut:
    """Customer cancels their own booking; operators may cancel any (manual fallback)."""
    booking = _load(db, booking_id, for_update=True)
    if not (booking.customer_id == actor.id or actor.role == UserRole.INVESTOR_OPERATOR):
        raise NotFoundError(f"Booking {booking_id} not found")
    if booking.start_at <= _now() and actor.role != UserRole.INVESTOR_OPERATOR:
        raise BusinessRuleViolationError("Viewing has already started")
    before = _transition(booking, BookingStatus.CANCELLED)
    booking.cancelled_at = _now()
    _audit_transition(db, actor, "booking.cancel", booking, before)
    db.commit()
    return to_out(booking, actor)


# ---------- Owner (human-in-the-loop) ----------


def _load_for_owner(db: Session, actor: Actor, booking_id: int) -> Booking:
    booking = _load(db, booking_id, for_update=True)
    if booking.property.owner_id != actor.id:
        raise NotFoundError(f"Booking {booking_id} not found")
    return booking


def approve(db: Session, actor: Actor, booking_id: int) -> BookingOut:
    if actor.role != UserRole.OWNER:
        raise ForbiddenError("Only the property owner can confirm a viewing")
    booking = _load_for_owner(db, actor, booking_id)
    if booking.start_at <= _now():
        raise BusinessRuleViolationError("Viewing time has already passed")
    before = _transition(booking, BookingStatus.CONFIRMED)
    booking.responded_at = _now()
    _audit_transition(db, actor, "booking.approve", booking, before)
    db.commit()
    return to_out(booking, actor)


def reject(db: Session, actor: Actor, booking_id: int, reason: str) -> BookingOut:
    if actor.role != UserRole.OWNER:
        raise ForbiddenError("Only the property owner can reject a viewing")
    booking = _load_for_owner(db, actor, booking_id)
    before = _transition(booking, BookingStatus.REJECTED)
    booking.responded_at = _now()
    booking.rejection_reason = reason
    _audit_transition(db, actor, "booking.reject", booking, before, reason=reason)
    db.commit()
    return to_out(booking, actor)


def complete(db: Session, actor: Actor, booking_id: int) -> BookingOut:
    if actor.role != UserRole.OWNER:
        raise ForbiddenError("Only the property owner can mark a viewing as completed")
    booking = _load_for_owner(db, actor, booking_id)
    if booking.start_at > _now():
        raise BusinessRuleViolationError("Viewing has not started yet")
    before = _transition(booking, BookingStatus.COMPLETED)
    _audit_transition(db, actor, "booking.complete", booking, before)
    db.commit()
    return to_out(booking, actor)


# ---------- Reads ----------


def get(db: Session, actor: Actor, booking_id: int) -> BookingOut:
    booking = _load(db, booking_id)
    if not _can_view(booking, actor):
        raise NotFoundError(f"Booking {booking_id} not found")
    return to_out(booking, actor)


def list_for(db: Session, actor: Actor, status: BookingStatus | None = None) -> list[BookingOut]:
    """Customers see their bookings, owners see bookings on their properties, operators see all."""
    stmt = select(Booking).options(
        joinedload(Booking.property, innerjoin=True)
        .joinedload(Property.building, innerjoin=True)
        .joinedload(Building.project, innerjoin=True),
        joinedload(Booking.customer, innerjoin=True),
    )
    if actor.role == UserRole.CUSTOMER:
        stmt = stmt.where(Booking.customer_id == actor.id)
    elif actor.role == UserRole.OWNER:
        stmt = stmt.join(Booking.property).where(Property.owner_id == actor.id)
    if status is not None:
        stmt = stmt.where(Booking.status == status)
    stmt = stmt.order_by(Booking.start_at.desc())
    return [to_out(b, actor) for b in db.scalars(stmt).unique()]
