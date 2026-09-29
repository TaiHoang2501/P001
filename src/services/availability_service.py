"""Owner viewing slots and free-slot lookup."""

from datetime import UTC, datetime

from sqlalchemy import and_, exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.actor import Actor
from src.core.errors import AlreadyExistsError, BusinessRuleViolationError, NotFoundError, StateConflictError
from src.db.models import ACTIVE_BOOKING_STATUSES, AvailabilitySlot, Booking, Property, PropertyStatus
from src.models.booking import SlotCreate, SlotOut
from src.services import audit

EXCLUSION_VIOLATION = "23P01"


def is_exclusion_violation(err: IntegrityError) -> bool:
    return getattr(err.orig, "sqlstate", None) == EXCLUSION_VIOLATION


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
    except IntegrityError as e:
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
