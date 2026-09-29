"""Viewing holds (spec §4.13): lock a property for one confirmed viewing window only.

Rules: created only after Owner confirmation, tied to Deal + Buyer + time window, never
outside that window, released when the window ends or the booking stops. The GiST
exclusion constraint on property_holds makes two overlapping ACTIVE holds impossible (AC-08).
"""

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.core.actor import Actor
from src.db.models import Booking, HoldStatus, PropertyHold
from src.services import audit


def create_for(db: Session, actor: Actor, booking: Booking) -> PropertyHold:
    """Add an ACTIVE hold for the booking's window. Flushes, so an overlap raises IntegrityError here."""
    hold = PropertyHold(
        booking_id=booking.id,
        deal_id=booking.deal_id,
        property_id=booking.property_id,
        buyer_id=booking.customer_id,
        start_at=booking.start_at,
        end_at=booking.end_at,
        status=HoldStatus.ACTIVE,
    )
    db.add(hold)
    db.flush()
    audit.record(
        db,
        actor,
        "hold.create",
        "hold",
        hold.id,
        after={"booking_id": booking.id, "start_at": hold.start_at.isoformat(), "end_at": hold.end_at.isoformat()},
    )
    return hold


def active_for(db: Session, booking_id: int) -> PropertyHold | None:
    return db.scalar(
        select(PropertyHold)
        .where(PropertyHold.booking_id == booking_id, PropertyHold.status == HoldStatus.ACTIVE)
        .with_for_update()
    )


def move(db: Session, actor: Actor, hold: PropertyHold, booking: Booking) -> None:
    """Follow a rescheduled booking to its new window. Flushes, so an overlap raises IntegrityError."""
    before = {"start_at": hold.start_at.isoformat(), "end_at": hold.end_at.isoformat()}
    hold.start_at, hold.end_at = booking.start_at, booking.end_at
    db.flush()
    audit.record(
        db,
        actor,
        "hold.move",
        "hold",
        hold.id,
        before=before,
        after={"start_at": hold.start_at.isoformat(), "end_at": hold.end_at.isoformat()},
    )


def release(db: Session, actor: Actor | None, booking_id: int, reason: str) -> bool:
    """Release the booking's ACTIVE hold, if any. Returns whether one was released."""
    hold = active_for(db, booking_id)
    if hold is None:
        return False
    hold.status = HoldStatus.RELEASED
    hold.released_at = datetime.now(UTC)
    hold.release_reason = reason
    audit.record(
        db,
        actor,
        "hold.release",
        "hold",
        hold.id,
        before={"status": HoldStatus.ACTIVE},
        after={"status": hold.status, "reason": reason},
    )
    return True


def expire_finished(db: Session, now: datetime | None = None) -> int:
    """Background sweep: holds whose viewing window has ended become EXPIRED. Returns how many."""
    now = now or datetime.now(UTC)
    ids = list(
        db.scalars(
            update(PropertyHold)
            .where(PropertyHold.status == HoldStatus.ACTIVE, PropertyHold.end_at <= now)
            .values(status=HoldStatus.EXPIRED, released_at=now, release_reason="window_ended")
            .returning(PropertyHold.id)
        )
    )
    for hold_id in ids:
        audit.record(db, None, "hold.expire", "hold", hold_id, after={"status": HoldStatus.EXPIRED})
    db.commit()
    return len(ids)
