"""Owner viewing slots, free-slot lookup and buyer/seller time matching."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, exists, select
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError
from sqlalchemy.orm import Session

from src.config import get_settings
from src.core.actor import Actor
from src.core.errors import AlreadyExistsError, BusinessRuleViolationError, NotFoundError, StateConflictError
from src.db.models import (
    ACTIVE_BOOKING_STATUSES,
    AvailabilitySlot,
    Booking,
    HoldStatus,
    Property,
    PropertyHold,
    PropertyStatus,
)
from src.models.booking import SlotCreate, SlotOut, TimeWindow, ViewingTimesOut, ViewingTimesRequest
from src.services import audit, seller_service
from src.services.scheduling import Window, candidate_starts, intersect, subtract

EXCLUSION_VIOLATION = "23P01"
DEADLOCK_DETECTED = "40P01"

# DB errors raised when two transactions race for the same property/time window
TimeConflictError = (IntegrityError, OperationalError)


def is_exclusion_violation(err: DBAPIError) -> bool:
    """True when `err` means "this time window is taken".

    Besides a plain exclusion violation, two concurrent inserts that overlap can each wait on the
    other while checking the exclusion constraint; PostgreSQL then aborts one with a deadlock.
    Either way the loser simply did not get the slot.
    """
    return getattr(err.orig, "sqlstate", None) in (EXCLUSION_VIOLATION, DEADLOCK_DETECTED)


def _slot_taken():
    """SQL condition: an active booking overlaps this slot's window."""
    return exists().where(
        and_(
            Booking.property_id == AvailabilitySlot.property_id,
            Booking.status.in_(ACTIVE_BOOKING_STATUSES),
            Booking.period.op("&&")(AvailabilitySlot.period),
        )
    )


def add_slot(db: Session, actor: Actor, property_id: int, data: SlotCreate) -> SlotOut:
    prop = db.get(Property, property_id)
    if prop is None or prop.owner_id != actor.id:
        raise NotFoundError(f"Property {property_id} not found")
    if prop.status == PropertyStatus.SOLD:
        raise StateConflictError("Cannot add viewing slots to a sold property")
    if data.start_at <= datetime.now(UTC):
        raise BusinessRuleViolationError("Slot must start in the future")

    slot = AvailabilitySlot(property_id=property_id, start_at=data.start_at, end_at=data.end_at)
    db.add(slot)
    try:
        db.flush()
    except TimeConflictError as e:
        db.rollback()
        if is_exclusion_violation(e):
            raise AlreadyExistsError("This slot overlaps an existing slot for the property") from e
        raise
    audit.record(
        db,
        actor,
        "slot.create",
        "slot",
        slot.id,
        after={"start_at": slot.start_at.isoformat(), "end_at": slot.end_at.isoformat()},
    )
    db.commit()
    return SlotOut(id=slot.id, property_id=slot.property_id, start_at=slot.start_at, end_at=slot.end_at, is_free=True)


def delete_slot(db: Session, actor: Actor, slot_id: int) -> None:
    slot = db.get(AvailabilitySlot, slot_id, with_for_update=True)
    if slot is None:
        raise NotFoundError(f"Slot {slot_id} not found")
    prop = db.get(Property, slot.property_id)
    if prop is None or prop.owner_id != actor.id:
        raise NotFoundError(f"Slot {slot_id} not found")
    taken = db.scalar(select(_slot_taken()).where(AvailabilitySlot.id == slot_id))
    if taken:
        raise StateConflictError("Slot has an active booking; reject or wait for it to finish first")
    audit.record(db, actor, "slot.delete", "slot", slot.id, before={"start_at": slot.start_at.isoformat()})
    db.delete(slot)
    db.commit()


def list_slots(db: Session, property_id: int, *, only_free: bool = True, include_past: bool = False) -> list[SlotOut]:
    taken = _slot_taken().label("taken")
    stmt = select(AvailabilitySlot, taken).where(AvailabilitySlot.property_id == property_id)
    if not include_past:
        stmt = stmt.where(AvailabilitySlot.start_at > datetime.now(UTC))
    rows = db.execute(stmt.order_by(AvailabilitySlot.start_at)).all()
    slots = [
        SlotOut(id=s.id, property_id=s.property_id, start_at=s.start_at, end_at=s.end_at, is_free=not is_taken)
        for s, is_taken in rows
    ]
    return [s for s in slots if s.is_free] if only_free else slots


def check_availability(db: Session, property_id: int, slot_id: int | None = None) -> dict:
    """Read-only availability check used by the booking UI and the AI tool.

    With slot_id: is that slot still free? Always also returns the current free slots,
    so the caller can suggest alternatives (F3 stale availability).
    """
    prop = db.get(Property, property_id)
    if prop is None or prop.status != PropertyStatus.AVAILABLE:
        raise NotFoundError(f"Property {property_id} not found")
    free = list_slots(db, property_id)
    result: dict = {"property_id": property_id, "free_slots": free}
    if slot_id is not None:
        result["slot_id"] = slot_id
        result["is_free"] = any(s.id == slot_id for s in free)
    return result


# ---------- Buyer ∩ Seller matching (spec §4.8, AC-06, AC-07) ----------


def busy_windows(db: Session, property_id: int, *, since: datetime) -> list[Window]:
    """Times the property is already taken: active bookings and active viewing holds."""
    bookings = db.execute(
        select(Booking.start_at, Booking.end_at).where(
            Booking.property_id == property_id,
            Booking.status.in_(ACTIVE_BOOKING_STATUSES),
            Booking.end_at > since,
        )
    ).all()
    holds = db.execute(
        select(PropertyHold.start_at, PropertyHold.end_at).where(
            PropertyHold.property_id == property_id,
            PropertyHold.status == HoldStatus.ACTIVE,
            PropertyHold.end_at > since,
        )
    ).all()
    return [Window(start, end) for start, end in [*bookings, *holds]]


def seller_windows(db: Session, property_id: int, *, since: datetime, until: datetime | None = None) -> list[Window]:
    stmt = select(AvailabilitySlot.start_at, AvailabilitySlot.end_at).where(
        AvailabilitySlot.property_id == property_id, AvailabilitySlot.end_at > since
    )
    if until is not None:
        stmt = stmt.where(AvailabilitySlot.start_at < until)
    return [Window(start, end) for start, end in db.execute(stmt).all()]


def _require_bookable(db: Session, property_id: int) -> Property:
    prop = db.get(Property, property_id)
    if prop is None or prop.status != PropertyStatus.AVAILABLE:
        raise NotFoundError(f"Property {property_id} not found")
    seller_service.require_verified(db, prop.owner_id)
    return prop


def _seller_free(db: Session, property_id: int, now: datetime, until: datetime | None = None) -> list[Window]:
    return subtract(seller_windows(db, property_id, since=now, until=until), busy_windows(db, property_id, since=now))


def seller_free_windows(db: Session, property_id: int) -> list[TimeWindow]:
    """The seller's free windows over the next `viewing_alternative_days`, minus booked/held times."""
    _require_bookable(db, property_id)
    now = datetime.now(UTC)
    until = now + timedelta(days=get_settings().viewing_alternative_days)
    return [
        TimeWindow(start_at=max(w.start, now), end_at=w.end)
        for w in _seller_free(db, property_id, now, until)
        if w.end > now
    ]


def propose_viewing_times(db: Session, property_id: int, data: ViewingTimesRequest) -> ViewingTimesOut:
    """Match the buyer's free windows with the seller's, skipping times already booked or held.

    Read-only: nothing is reserved until a viewing request is created.
    """
    _require_bookable(db, property_id)
    s = get_settings()
    now = datetime.now(UTC)
    duration = timedelta(minutes=s.viewing_duration_minutes)
    step = timedelta(minutes=s.viewing_step_minutes)

    seller_free = _seller_free(db, property_id, now)
    buyer = [Window(w.start_at, w.end_at) for w in data.windows]
    common = [w for w in intersect(buyer, seller_free) if w.end > now]
    starts = candidate_starts(common, duration=duration, step=step, not_before=now, limit=s.viewing_max_proposals)

    alternatives: list[datetime] = []
    if not starts:
        horizon = now + timedelta(days=s.viewing_alternative_days)
        upcoming = [w for w in seller_free if w.start < horizon]
        alternatives = candidate_starts(
            upcoming, duration=duration, step=step, not_before=now, limit=s.viewing_max_proposals
        )

    def _slot(start: datetime) -> TimeWindow:
        return TimeWindow(start_at=start, end_at=start + duration)

    return ViewingTimesOut(
        property_id=property_id,
        viewing_duration_minutes=s.viewing_duration_minutes,
        common_windows=[TimeWindow(start_at=w.start, end_at=w.end) for w in common],
        proposals=[_slot(t) for t in starts],
        alternatives=[_slot(t) for t in alternatives],
    )
