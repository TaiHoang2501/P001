"""What happened at a viewing, once its time has passed.

- The owner records it (they are the one at the home): "Đã xem" (COMPLETED, existing) or "Khách không đến"
  (NO_SHOW). They are reminded once if they forget.
- The buyer, after a viewing that took place, says how they found the home: interested (deal INTERESTED, the
  owner is told) or not suitable (deal CLOSED, the assistant offers other homes).
- The buyer may disagree ("I came" / "the owner was not there"): only then a case goes to the operator, who
  calls both and records the outcome.
- Nobody recorded it within `viewing_outcome_hours`: the viewing closes as UNREPORTED, blaming nobody.

No automatic penalties: counts of no-shows / absences are only shown to the operator handling a dispute.
"""

from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.core.actor import Actor
from src.core.errors import BusinessRuleViolationError, ForbiddenError, NotFoundError, StateConflictError
from src.db.models import (
    OPEN_ESCALATION_STATUSES,
    ActorType,
    Booking,
    BookingStatus,
    DealStatus,
    Escalation,
    EscalationStatus,
    EscalationType,
    Notification,
    UserRole,
)
from src.models.booking import BookingOut
from src.services import audit, booking_service, deal_service, escalation_service, hold_service, notification_service

Interest = Literal["INTERESTED", "NOT_SUITABLE"]
Claim = Literal["I_CAME", "OWNER_ABSENT"]
Outcome = Literal["VIEWED", "BUYER_NO_SHOW", "OWNER_ABSENT"]

_OUTCOME_STATUS = {
    "VIEWED": BookingStatus.COMPLETED,
    "BUYER_NO_SHOW": BookingStatus.NO_SHOW,
    "OWNER_ABSENT": BookingStatus.OWNER_ABSENT,
}


def _now() -> datetime:
    return datetime.now(UTC)


def _label(b: Booking) -> str:
    return f"{b.property.building.name} · {b.property.unit_code}"


def _sync_after_viewing(db: Session, actor: Actor | None, booking: Booking) -> None:
    """Deal follows the viewing; a deal already marked VIEWED goes back to MATCHED if the viewing did not happen."""
    db.flush()
    deal = booking.deal
    if deal.status == DealStatus.VIEWED and booking.status != BookingStatus.COMPLETED:
        before = deal.status
        deal.status = DealStatus.MATCHED
        audit.record(
            db, actor, "deal.status", "deal", deal.id, before={"status": before}, after={"status": deal.status}
        )
    deal_service.sync_status(db, actor, deal)


# ---------- Owner ----------


def no_show(db: Session, actor: Actor, booking_id: int) -> BookingOut:
    """The owner records that the buyer did not come."""
    if actor.role != UserRole.OWNER:
        raise ForbiddenError("Only the property owner can record a no-show")
    booking = booking_service._load_for_owner(db, actor, booking_id)
    if booking.start_at > _now():
        raise BusinessRuleViolationError("Viewing has not started yet")
    before = booking_service._transition(booking, BookingStatus.NO_SHOW)
    hold_service.release(db, actor, booking.id, "no_show")
    booking_service._audit_transition(db, actor, "booking.no_show", booking, before)
    _sync_after_viewing(db, actor, booking)
    notification_service.cancel_reminders(db, booking.id)
    notification_service.notify(
        db,
        booking.customer_id,
        "VIEWING_NO_SHOW",
        "Chủ căn ghi nhận bạn không đến buổi xem",
        f"Buổi xem {_label(booking)} được ghi là bạn không đến. Nếu bạn đã đến, bấm “Tôi có đến” trong mục Hoạt động.",
        booking=booking,
    )
    db.commit()
    return booking_service.to_out(booking, actor)


# ---------- Buyer ----------


def _own_booking(db: Session, actor: Actor, booking_id: int) -> Booking:
    booking = booking_service._load(db, booking_id, for_update=True)
    if booking.customer_id != actor.id:
        raise NotFoundError(f"Booking {booking_id} not found")
    return booking


def feedback(db: Session, actor: Actor, booking_id: int, interest: Interest, note: str) -> BookingOut:
    """After a viewing that took place: is the buyer interested? Asked once per viewing."""
    booking = _own_booking(db, actor, booking_id)
    if booking.status != BookingStatus.COMPLETED:
        raise StateConflictError("You can say how you found the home after the viewing took place")
    deal = booking.deal
    if deal.status != DealStatus.VIEWED:
        raise StateConflictError("You already told us about this viewing", details={"deal_status": deal.status.value})
    before = deal.status
    deal.status = DealStatus.INTERESTED if interest == "INTERESTED" else DealStatus.CLOSED
    audit.record(db, actor, "deal.status", "deal", deal.id, before={"status": before}, after={"status": deal.status})
    audit.record(
        db,
        actor,
        "booking.feedback",
        "booking",
        booking.id,
        after={"interest": interest, "note": note, "start_at": booking.start_at.isoformat()},
    )
    if interest == "INTERESTED":
        notification_service.notify(
            db,
            booking.property.owner_id,
            "BUYER_INTERESTED",
            "Người mua quan tâm căn của bạn",
            f"{booking.customer.full_name} đã xem {_label(booking)} và cho biết quan tâm (deal {deal.code}).",
            booking=booking,
        )
    else:
        # Shown in the buyer's chat: the assistant offers to look again
        notification_service.notify(
            db,
            booking.customer_id,
            "AGENT_FOLLOWUP",
            "Tìm căn khác cho bạn?",
            f"Bạn thấy {_label(booking)} chưa phù hợp"
            + (f" ({note})" if note else "")
            + ". Nhắn mình điều bạn muốn khác đi, mình tìm căn khác ngay.",
            booking=booking,
            payload={"property_id": booking.property_id},
        )
    db.commit()
    return booking_service.to_out(booking, actor)


def dispute(db: Session, actor: Actor, booking_id: int, claim: Claim, note: str) -> BookingOut:
    """The buyer disagrees: "I came" (after a no-show) or "the owner was not there" (outcome not recorded)."""
    booking = _own_booking(db, actor, booking_id)
    if claim == "I_CAME" and booking.status != BookingStatus.NO_SHOW:
        raise StateConflictError("Only a viewing recorded as a no-show can be disputed this way")
    if claim == "OWNER_ABSENT" and not (booking.status == BookingStatus.CONFIRMED and booking.end_at <= _now()):
        raise StateConflictError("You can report this once the viewing time has passed")
    open_case = db.scalar(
        select(Escalation.id).where(
            Escalation.booking_id == booking.id,
            Escalation.type == EscalationType.VIEWING_DISPUTE,
            Escalation.status.in_(OPEN_ESCALATION_STATUSES),
        )
    )
    if open_case is not None:
        raise StateConflictError("This viewing is already being checked", details={"escalation_id": open_case})

    # For the operator only: how often each side missed a viewing before (no automatic penalty)
    buyer_no_shows = db.scalar(
        select(func.count()).where(Booking.customer_id == booking.customer_id, Booking.status == BookingStatus.NO_SHOW)
    )
    owner_absences = db.scalar(
        select(func.count()).where(Booking.owner_id == booking.owner_id, Booking.status == BookingStatus.OWNER_ABSENT)
    )
    what = "đã đến nhưng bị ghi là không đến" if claim == "I_CAME" else "đã đến nhưng chủ căn không có mặt"
    escalation_service.create(
        db,
        type=EscalationType.VIEWING_DISPUTE,
        summary=f"Người mua báo {what}: {_label(booking)}, {booking.start_at:%H:%M %d/%m}",
        raised_by=ActorType.USER,
        actor=actor,
        requester_id=actor.id,
        deal_id=booking.deal_id,
        booking_id=booking.id,
        property_id=booking.property_id,
        context={
            "claim": claim,
            "note": note,
            "booking_status": booking.status.value,
            "buyer_name": booking.customer.full_name,
            "buyer_phone": booking.customer.phone,
            "owner_id": booking.property.owner_id,
            "owner_name": booking.property.owner.full_name,
            "owner_phone": booking.property.owner.phone,
            "buyer_no_shows": buyer_no_shows,
            "owner_absences": owner_absences,
        },
    )
    audit.record(db, actor, "booking.dispute", "booking", booking.id, after={"claim": claim, "note": note})
    db.commit()
    return booking_service.to_out(booking, actor)


# ---------- Operator ----------


def record_outcome(db: Session, actor: Actor, escalation_id: int, outcome: Outcome, note: str) -> BookingOut:
    """After calling both sides: what really happened. Closes the dispute and tells both."""
    esc = db.get(Escalation, escalation_id, with_for_update=True)
    if esc is None or esc.type != EscalationType.VIEWING_DISPUTE or esc.booking_id is None:
        raise NotFoundError(f"Viewing dispute {escalation_id} not found")
    if esc.status not in OPEN_ESCALATION_STATUSES:
        raise StateConflictError(f"This case is already {esc.status.value}")
    booking = booking_service._load(db, esc.booking_id, for_update=True)
    before = booking.status
    booking.status = _OUTCOME_STATUS[outcome]
    if booking.status == BookingStatus.COMPLETED:
        booking.completed_at = booking.completed_at or _now()
    hold_service.release(db, actor, booking.id, "outcome_recorded")
    audit.record(
        db,
        actor,
        "booking.outcome_by_operator",
        "booking",
        booking.id,
        before={"status": before},
        after={
            "status": booking.status,
            "start_at": booking.start_at.isoformat(),
            "note": note,
            "escalation_id": esc.id,
        },
    )
    _sync_after_viewing(db, actor, booking)
    text = {
        "VIEWED": "Buổi xem được ghi nhận là đã diễn ra.",
        "BUYER_NO_SHOW": "Buổi xem được ghi nhận là người mua không đến.",
        "OWNER_ABSENT": "Buổi xem được ghi nhận là chủ căn không có mặt.",
    }[outcome]
    esc.status = EscalationStatus.RESOLVED
    esc.resolution = f"{text} {note}"
    esc.resolved_at = _now()
    esc.assigned_to = esc.assigned_to or actor.id
    audit.record(db, actor, "escalation.resolve", "escalation", esc.id, after={"resolution": esc.resolution})
    for user_id in (booking.customer_id, booking.property.owner_id):
        notification_service.notify(
            db,
            user_id,
            "VIEWING_OUTCOME_RECORDED",
            f"Kết quả buổi xem {_label(booking)}",
            esc.resolution,
            booking=booking,
        )
    db.commit()
    return booking_service.to_out(booking, actor)


# ---------- Periodic ----------


def remind_and_close(db: Session, now: datetime | None = None) -> tuple[int, int]:
    """Remind owners once to record a past viewing; close the ones nobody recorded in time (UNREPORTED)."""
    now = now or _now()
    deadline = timedelta(hours=get_settings().viewing_outcome_hours)
    past = db.scalars(
        select(Booking).where(
            Booking.status.in_((BookingStatus.CONFIRMED, BookingStatus.RESCHEDULE_REQUESTED)),
            Booking.end_at <= now,
        )
    ).all()
    reminded = closed = 0
    for booking in past:
        if booking.end_at <= now - deadline:
            # A dispute in progress waits for the operator
            if db.scalar(
                select(Escalation.id).where(
                    Escalation.booking_id == booking.id,
                    Escalation.type == EscalationType.VIEWING_DISPUTE,
                    Escalation.status.in_(OPEN_ESCALATION_STATUSES),
                )
            ):
                continue
            before = booking.status
            booking.status = BookingStatus.UNREPORTED
            booking.proposed_start_at = booking.proposed_end_at = None
            hold_service.release(db, None, booking.id, "unreported")
            booking_service._audit_transition(db, None, "booking.unreported", booking, before)
            _sync_after_viewing(db, None, booking)
            closed += 1
        elif booking.status == BookingStatus.CONFIRMED:
            key = f"outcome-due-{booking.id}"
            if db.scalar(select(Notification.id).where(Notification.dedupe_key == key)) is not None:
                continue  # reminded already
            notification_service.notify(
                db,
                booking.property.owner_id,
                "VIEWING_OUTCOME_DUE",
                "Buổi xem đã qua: khách có đến không?",
                f"Buổi xem {_label(booking)} của {booking.customer.full_name} đã qua. Vào “Yêu cầu xem” để ghi nhận "
                "“Đã xem xong” hoặc “Khách không đến”.",
                booking=booking,
                dedupe_key=key,
            )
            reminded += 1
    db.commit()
    return reminded, closed
