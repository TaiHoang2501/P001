"""Human escalation / operator exception queue (spec §4.3, §4.8 HITL, §6.4 fallback path).

Escalations are raised by the AI agent (create_human_escalation), by the system when a tool
fails, or by the periodic sweep when a seller does not answer a viewing request in time.
Operators take, resolve or dismiss them; the requester is told the outcome.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.config import get_settings
from src.core.actor import Actor
from src.core.errors import NotFoundError, StateConflictError
from src.db.models import (
    OPEN_ESCALATION_STATUSES,
    ActorType,
    Booking,
    BookingStatus,
    Escalation,
    EscalationStatus,
    EscalationType,
    User,
    UserRole,
)
from src.models.escalation import EscalationOut
from src.services import audit, notification_service


def _notify_operators(db: Session, esc: Escalation) -> None:
    operators = db.scalars(select(User.id).where(User.role == UserRole.INVESTOR_OPERATOR))
    for operator_id in operators:
        notification_service.notify(
            db,
            operator_id,
            "ESCALATION_OPENED",
            f"Cần xử lý: {esc.type.value}",
            esc.summary,
            payload={"escalation_id": esc.id},
        )


def create(
    db: Session,
    *,
    type: EscalationType,
    summary: str,
    raised_by: ActorType,
    actor: Actor | None = None,
    requester_id: int | None = None,
    deal_id: int | None = None,
    booking_id: int | None = None,
    property_id: int | None = None,
    context: dict[str, Any] | None = None,
) -> Escalation:
    """Add an OPEN escalation to the current transaction and tell the operators. Caller commits."""
    esc = Escalation(
        type=type,
        status=EscalationStatus.OPEN,
        raised_by=raised_by,
        requester_id=requester_id,
        deal_id=deal_id,
        booking_id=booking_id,
        property_id=property_id,
        summary=summary,
        context=context or {},
    )
    db.add(esc)
    db.flush()
    audit.record(db, actor, "escalation.open", "escalation", esc.id, after={"type": type, "summary": summary})
    _notify_operators(db, esc)
    return esc


# ---------- Automatic sweep ----------


def escalate_unanswered_requests(db: Session, now: datetime | None = None) -> int:
    """Periodic job: viewing requests the seller has not answered in time go to an operator (spec §4.8)."""
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(hours=get_settings().seller_response_hours)
    stale = db.scalars(
        select(Booking).where(
            Booking.status == BookingStatus.REQUESTED,
            Booking.created_at <= cutoff,
            ~select(Escalation.id)
            .where(Escalation.booking_id == Booking.id, Escalation.type == EscalationType.SELLER_NO_RESPONSE)
            .exists(),
        )
    ).all()
    created = 0
    for booking in stale:
        # Insert-if-absent: the partial unique index makes a concurrent sweep a no-op
        result = db.execute(
            insert(Escalation)
            .values(
                type=EscalationType.SELLER_NO_RESPONSE,
                status=EscalationStatus.OPEN,
                raised_by=ActorType.SYSTEM,
                requester_id=booking.customer_id,
                deal_id=booking.deal_id,
                booking_id=booking.id,
                property_id=booking.property_id,
                summary=f"Chủ căn chưa phản hồi yêu cầu xem #{booking.id} sau "
                f"{get_settings().seller_response_hours} giờ.",
                context={"requested_at": booking.created_at.isoformat(), "start_at": booking.start_at.isoformat()},
            )
            .on_conflict_do_nothing()
            .returning(Escalation.id)
        )
        esc_id = result.scalar()
        if esc_id is None:
            continue
        created += 1
        esc = db.get(Escalation, esc_id)
        audit.record(db, None, "escalation.open", "escalation", esc_id, after={"type": esc.type})
        _notify_operators(db, esc)
        notification_service.notify(
            db,
            booking.customer_id,
            "ESCALATION_OPENED",
            "Đội hỗ trợ đang liên hệ chủ căn",
            "Chủ căn chưa phản hồi yêu cầu xem của bạn; bộ phận hỗ trợ của Chủ đầu tư sẽ giúp sắp xếp.",
            booking=booking,
        )
    db.commit()
    return created


# ---------- Operator ----------


def _load(db: Session, escalation_id: int) -> Escalation:
    esc = db.get(Escalation, escalation_id, with_for_update=True)
    if esc is None:
        raise NotFoundError(f"Escalation {escalation_id} not found")
    return esc


def list_queue(db: Session, status: EscalationStatus | None = None) -> list[EscalationOut]:
    """Operator queue; without a status filter it shows everything still open, oldest first."""
    stmt = select(Escalation)
    stmt = (
        stmt.where(Escalation.status == status)
        if status
        else stmt.where(Escalation.status.in_(OPEN_ESCALATION_STATUSES))
    )
    return [EscalationOut.model_validate(e) for e in db.scalars(stmt.order_by(Escalation.created_at))]


def assign(db: Session, actor: Actor, escalation_id: int) -> EscalationOut:
    esc = _load(db, escalation_id)
    if esc.status not in OPEN_ESCALATION_STATUSES:
        raise StateConflictError(f"Escalation is already {esc.status.value}")
    before = esc.status
    esc.status = EscalationStatus.IN_PROGRESS
    esc.assigned_to = actor.id
    audit.record(
        db, actor, "escalation.assign", "escalation", esc.id, before={"status": before}, after={"status": esc.status}
    )
    db.commit()
    return EscalationOut.model_validate(esc)


def close(db: Session, actor: Actor, escalation_id: int, resolution: str, *, dismissed: bool = False) -> EscalationOut:
    esc = _load(db, escalation_id)
    if esc.status not in OPEN_ESCALATION_STATUSES:
        raise StateConflictError(f"Escalation is already {esc.status.value}")
    before = esc.status
    esc.status = EscalationStatus.DISMISSED if dismissed else EscalationStatus.RESOLVED
    esc.resolution = resolution
    esc.resolved_at = datetime.now(UTC)
    esc.assigned_to = esc.assigned_to or actor.id
    audit.record(
        db,
        actor,
        "escalation.dismiss" if dismissed else "escalation.resolve",
        "escalation",
        esc.id,
        before={"status": before},
        after={"status": esc.status, "resolution": resolution},
    )
    if esc.requester_id is not None:
        notification_service.notify(
            db,
            esc.requester_id,
            "ESCALATION_RESOLVED",
            "Yêu cầu hỗ trợ đã được xử lý",
            resolution,
            payload={"escalation_id": esc.id},
        )
    db.commit()
    return EscalationOut.model_validate(esc)


# ---------- Requester ----------


def list_mine(db: Session, actor: Actor) -> list[EscalationOut]:
    rows = db.scalars(
        select(Escalation).where(Escalation.requester_id == actor.id).order_by(Escalation.created_at.desc())
    )
    return [EscalationOut.model_validate(e) for e in rows]
