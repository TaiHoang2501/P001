"""Viewing bookings: request -> owner approval (HITL) -> confirmed hold -> completed/cancelled.

Safety rules enforced here (not in the UI or the prompt):
- Every viewing request belongs to a Deal (Buyer + Seller + Property), created on first request (AC-02, AC-09).
- Only verified sellers' properties can be booked (AC-04).
- Only the property's owner can confirm or reject (AC-05).
- Only one active booking per property per time window; enforced by the DB exclusion
  constraint, so concurrent requests cannot both succeed (AC-08).
- The seller never sees the buyer's name/phone at privacy level 1-2 (AC-03).
- Invalid status transitions are rejected; every change writes an audit row in the same transaction.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from src.config import get_settings
from src.core.actor import Actor
from src.core.errors import (
    BusinessRuleViolationError,
    ForbiddenError,
    NotFoundError,
    SlotUnavailableError,
    StateConflictError,
)
from src.db.models import (
    ACTIVE_BOOKING_STATUSES,
    AvailabilitySlot,
    Booking,
    BookingStatus,
    Building,
    BuyerAvailability,
    BuyerProfile,
    Property,
    PropertyStatus,
    UserRole,
)
from src.models.booking import BookingCreate, BookingOut
from src.services import audit, deal_service, seller_service
from src.services.availability_service import is_exclusion_violation, list_slots

_TRANSITIONS: dict[BookingStatus, set[BookingStatus]] = {
    BookingStatus.REQUESTED: {BookingStatus.CONFIRMED, BookingStatus.REJECTED, BookingStatus.CANCELLED},
    BookingStatus.CONFIRMED: {BookingStatus.COMPLETED, BookingStatus.CANCELLED},
    BookingStatus.REJECTED: set(),
    BookingStatus.CANCELLED: set(),
    BookingStatus.COMPLETED: set(),
}
# Spec §4.7: the seller gets buyer contact details only from level 3 (continue transaction) on
_CONTACT_LEVEL = 3


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
            joinedload(Booking.deal),
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


def to_out(booking: Booking, viewer: Actor, profile: BuyerProfile | None = None) -> BookingOut:
    prop = booking.property
    deal = booking.deal
    show_contact = (
        viewer.role == UserRole.INVESTOR_OPERATOR
        or viewer.id == booking.customer_id
        or deal.disclosure_level >= _CONTACT_LEVEL
    )
    return BookingOut(
        id=booking.id,
        deal_id=booking.deal_id,
        deal_code=deal.code,
        property_id=prop.id,
        property_label=f"{prop.building.project.name} · {prop.building.name} · {prop.unit_code}",
        customer_id=booking.customer_id,
        buyer_ref=f"Buyer #{booking.customer_id}",
        buyer_budget_min_vnd=profile.budget_min_vnd if profile else None,
        buyer_budget_max_vnd=profile.budget_max_vnd if profile else None,
        customer_name=booking.customer.full_name if show_contact else None,
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
    slot, start_at, end_at = _resolve_time(db, prop, data)

    try:
        deal = deal_service.get_or_create_open(db, actor, prop)
        if db.scalar(select(Booking.id).where(Booking.deal_id == deal.id, Booking.status.in_(ACTIVE_BOOKING_STATUSES))):
            raise StateConflictError(
                f"Deal {deal.code} already has an active viewing request; reschedule or cancel it first",
                details={"deal_id": deal.id},
            )
        if data.buyer_windows:
            db.execute(delete(BuyerAvailability).where(BuyerAvailability.deal_id == deal.id))
            db.add_all(
                BuyerAvailability(buyer_id=actor.id, deal_id=deal.id, start_at=w.start_at, end_at=w.end_at)
                for w in data.buyer_windows
            )
        booking = Booking(
            deal_id=deal.id,
            property_id=prop.id,
            customer_id=actor.id,
            slot_id=slot.id if slot else None,
            start_at=start_at,
            end_at=end_at,
            status=BookingStatus.REQUESTED,
            created_via=actor.via,
            customer_note=data.note,
        )
        db.add(booking)
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
        after={"status": booking.status, "property_id": prop.id, "deal_id": deal.id, "start_at": start_at.isoformat()},
    )
    deal_service.sync_status(db, actor, deal)
    db.commit()
    return to_out(_load(db, booking.id), actor)


def _resolve_time(
    db: Session, prop: Property, data: BookingCreate
) -> tuple[AvailabilitySlot | None, datetime, datetime]:
    """Viewing window from a seller slot, or from a start time that must fit inside one."""
    if data.slot_id is not None:
        slot = db.get(AvailabilitySlot, data.slot_id)
        if slot is None or slot.property_id != prop.id:
            raise NotFoundError(f"Slot {data.slot_id} not found for property {prop.id}")
        start_at, end_at = slot.start_at, slot.end_at
    else:
        assert data.start_at is not None  # guaranteed by BookingCreate validation
        start_at = data.start_at
        end_at = start_at + timedelta(minutes=get_settings().viewing_duration_minutes)
        slot = db.scalar(
            select(AvailabilitySlot).where(
                AvailabilitySlot.property_id == prop.id,
                AvailabilitySlot.start_at <= start_at,
                AvailabilitySlot.end_at >= end_at,
            )
        )
        if slot is None:
            raise BusinessRuleViolationError(
                "The seller is not available at this time; ask for viewing times first",
                details={"start_at": start_at.isoformat()},
            )
    if start_at <= _now():
        raise BusinessRuleViolationError("This viewing time has already started")
    return slot, start_at, end_at


def cancel(db: Session, actor: Actor, booking_id: int) -> BookingOut:
    """Customer cancels their own booking; operators may cancel any (manual fallback)."""
    booking = _load(db, booking_id, for_update=True)
    if not (booking.customer_id == actor.id or actor.role == UserRole.INVESTOR_OPERATOR):
        raise NotFoundError(f"Booking {booking_id} not found")
    if booking.start_at <= _now() and actor.role != UserRole.INVESTOR_OPERATOR:
        raise BusinessRuleViolationError("Viewing has already started")
    before = _transition(booking, BookingStatus.CANCELLED)
    booking.cancelled_at = _now()
    booking.cancelled_by = actor.id
    _audit_transition(db, actor, "booking.cancel", booking, before)
    _sync_deal(db, actor, booking)
    db.commit()
    return to_out(booking, actor)


def _sync_deal(db: Session, actor: Actor, booking: Booking) -> None:
    db.flush()
    deal_service.sync_status(db, actor, booking.deal)


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
    _sync_deal(db, actor, booking)
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
    _sync_deal(db, actor, booking)
    db.commit()
    return to_out(booking, actor)


def complete(db: Session, actor: Actor, booking_id: int) -> BookingOut:
    if actor.role != UserRole.OWNER:
        raise ForbiddenError("Only the property owner can mark a viewing as completed")
    booking = _load_for_owner(db, actor, booking_id)
    if booking.start_at > _now():
        raise BusinessRuleViolationError("Viewing has not started yet")
    before = _transition(booking, BookingStatus.COMPLETED)
    booking.completed_at = _now()
    _audit_transition(db, actor, "booking.complete", booking, before)
    _sync_deal(db, actor, booking)
    db.commit()
    return to_out(booking, actor)


# ---------- Reads ----------


def get(db: Session, actor: Actor, booking_id: int) -> BookingOut:
    booking = _load(db, booking_id)
    if not _can_view(booking, actor):
        raise NotFoundError(f"Booking {booking_id} not found")
    return to_out(booking, actor, db.get(BuyerProfile, booking.customer_id))


def list_for(db: Session, actor: Actor, status: BookingStatus | None = None) -> list[BookingOut]:
    """Customers see their bookings, owners see bookings on their properties, operators see all."""
    stmt = select(Booking).options(
        joinedload(Booking.property, innerjoin=True)
        .joinedload(Property.building, innerjoin=True)
        .joinedload(Building.project, innerjoin=True),
        joinedload(Booking.customer, innerjoin=True),
        joinedload(Booking.deal),
    )
    if actor.role == UserRole.CUSTOMER:
        stmt = stmt.where(Booking.customer_id == actor.id)
    elif actor.role == UserRole.OWNER:
        stmt = stmt.join(Booking.property).where(Property.owner_id == actor.id)
    if status is not None:
        stmt = stmt.where(Booking.status == status)
    stmt = stmt.order_by(Booking.start_at.desc())
    bookings = list(db.scalars(stmt).unique())
    profiles = {
        p.user_id: p
        for p in db.scalars(select(BuyerProfile).where(BuyerProfile.user_id.in_({b.customer_id for b in bookings})))
    }
    return [to_out(b, actor, profiles.get(b.customer_id)) for b in bookings]
