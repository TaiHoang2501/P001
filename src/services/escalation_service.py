"""Human escalation / operator exception queue (spec §4.3, §4.8 HITL, §6.4 fallback path).

Escalations are raised by the AI agent (create_human_escalation), by the system when a tool
fails, or by the periodic sweep when a seller does not answer a viewing request in time.
Operators take, resolve or dismiss them; the requester is told the outcome.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Integer, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.config import get_settings
from src.core.actor import Actor
from src.core.errors import NotFoundError, StateConflictError
from src.db.models import (
    OPEN_ESCALATION_STATUSES,
    ActorType,
    AiConversation,
    AiMessage,
    Booking,
    BookingStatus,
    Escalation,
    EscalationStatus,
    EscalationType,
    MessageRole,
    Notification,
    Property,
    User,
    UserRole,
)
from src.models.escalation import CaseContext, CaseMessage, EscalationOut
from src.services import audit, notification_service

# The kind of case in plain words, for the operators' notifications (same wording as their queue)
ESCALATION_LABELS = {
    EscalationType.SELLER_NO_RESPONSE: "Chủ căn chưa phản hồi",
    EscalationType.NO_COMMON_SLOT: "Không có giờ xem chung",
    EscalationType.SCHEDULE_CONFLICT: "Xung đột lịch",
    EscalationType.PROPERTY_ISSUE: "Vấn đề về căn",
    EscalationType.MULTI_BUYER: "Nhiều người mua cùng căn",
    EscalationType.SYSTEM_FAILURE: "Lỗi hệ thống",
    EscalationType.OTHER: "Khách cần hỗ trợ",
    EscalationType.OWNERSHIP_SUPPORT: "Hỗ trợ xác thực sổ đỏ / sổ hồng",
    EscalationType.VIEWING_DISPUTE: "Tranh chấp kết quả buổi xem",
}


def _notify_operators(db: Session, esc: Escalation) -> None:
    operators = db.scalars(select(User.id).where(User.role == UserRole.INVESTOR_OPERATOR))
    for operator_id in operators:
        notification_service.notify(
            db,
            operator_id,
            "ESCALATION_OPENED",
            f"Ca mới: {ESCALATION_LABELS.get(esc.type, esc.type.value)}",
            esc.summary,
            # The kind of case: the bell groups the operator's notifications by it
            payload={"escalation_id": esc.id, "escalation_type": esc.type.value},
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
    s = get_settings()
    cutoff = now - timedelta(hours=s.seller_response_hours)
    stale = db.scalars(
        select(Booking).where(
            Booking.status == BookingStatus.REQUESTED,
            # Only viewings still ahead: nobody can rescue one whose time has come (it expires by itself, see
            # booking_service.expire_unanswered)
            Booking.start_at > now,
            # Past the answer deadline: 24 h after the request, or 1 h before the viewing if that comes first
            or_(
                Booking.created_at <= cutoff,
                Booking.start_at <= now + timedelta(minutes=s.seller_response_lead_minutes),
            ),
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
                summary=f"Chủ căn chưa phản hồi yêu cầu xem #{booking.id} trước hạn "
                f"({s.seller_response_hours} giờ, hoặc {s.seller_response_lead_minutes} phút trước giờ xem).",
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


def settle_no_response(db: Session, actor: Actor | None, booking_id: int, outcome: str) -> int:
    """The request a "seller did not answer" case is about has been dealt with (the owner answered late, the buyer
    cancelled, another viewing took the time): close the case so nobody calls about it any more. No commit; the
    people involved already hear about the booking itself. Returns how many cases were closed."""
    cases = db.scalars(
        select(Escalation)
        .where(
            Escalation.booking_id == booking_id,
            Escalation.type == EscalationType.SELLER_NO_RESPONSE,
            Escalation.status.in_(OPEN_ESCALATION_STATUSES),
        )
        .with_for_update()
    ).all()
    for esc in cases:
        before = esc.status
        esc.status = EscalationStatus.RESOLVED
        esc.resolution = outcome
        esc.resolved_at = datetime.now(UTC)
        audit.record(
            db,
            actor,
            "escalation.auto_resolve",
            "escalation",
            esc.id,
            before={"status": before},
            after={"status": esc.status, "resolution": outcome},
        )
    if cases:
        db.flush()
        retire_closed_case_notices(db)
    return len(cases)


_SETTLED_BY_STATUS = {
    BookingStatus.CONFIRMED: "Chủ căn đã xác nhận lịch xem.",
    BookingStatus.RESCHEDULE_REQUESTED: "Chủ căn đã xác nhận lịch xem.",
    BookingStatus.REJECTED: "Chủ căn đã trả lời yêu cầu xem (từ chối hoặc đã nhận lịch khác vào giờ này).",
    BookingStatus.CANCELLED: "Người mua đã hủy yêu cầu xem.",
    BookingStatus.EXPIRED: "Đã tới giờ xem mà chủ căn chưa trả lời; yêu cầu tự hết hạn và người mua đã được báo.",
}


def settle_stale_cases(db: Session) -> int:
    """Periodic job: "seller did not answer" cases whose request is no longer waiting (answered, cancelled,
    expired), e.g. left over from before such cases closed by themselves. Commits; returns how many closed."""
    rows = db.execute(
        select(Escalation.booking_id, Booking.status)
        .join(Booking, Booking.id == Escalation.booking_id)
        .where(
            Escalation.type == EscalationType.SELLER_NO_RESPONSE,
            Escalation.status.in_(OPEN_ESCALATION_STATUSES),
            Booking.status != BookingStatus.REQUESTED,
        )
    ).all()
    closed = sum(
        settle_no_response(db, None, booking_id, _SETTLED_BY_STATUS.get(status, "Yêu cầu xem đã được xử lý."))
        for booking_id, status in rows
    )
    db.commit()
    return closed


def retire_closed_case_notices(db: Session) -> int:
    """The operators' notices about cases that are closed no longer wait to be read: the bell counts work still
    to do. No commit; returns how many notices were marked read."""
    closed = select(Escalation.id).where(Escalation.status.not_in(OPEN_ESCALATION_STATUSES))
    result = db.execute(
        update(Notification)
        .where(
            Notification.event_type == "ESCALATION_OPENED",
            Notification.read_at.is_(None),
            Notification.user_id.in_(select(User.id).where(User.role == UserRole.INVESTOR_OPERATOR)),
            Notification.payload["escalation_id"].astext.cast(Integer).in_(closed),
        )
        .values(read_at=datetime.now(UTC))
        .execution_options(synchronize_session=False)
    )
    return result.rowcount or 0


def _out(db: Session, esc: Escalation) -> EscalationOut:
    out = EscalationOut.model_validate(esc)
    if esc.assigned_to is not None:
        staff = db.get(User, esc.assigned_to)
        out.assigned_to_name = staff.full_name if staff else None
    return out


# Who hears the outcome of a case by default (the operator can change it when closing). The person who raised
# the case always does; these add the other side when the case is about both of them.
_TELL_BUYER = {
    EscalationType.SELLER_NO_RESPONSE,
    EscalationType.NO_COMMON_SLOT,
    EscalationType.SCHEDULE_CONFLICT,
    EscalationType.PROPERTY_ISSUE,
    EscalationType.MULTI_BUYER,
    EscalationType.SYSTEM_FAILURE,
    EscalationType.OTHER,
    EscalationType.VIEWING_DISPUTE,
}
_TELL_SELLER = {
    EscalationType.SELLER_NO_RESPONSE,
    EscalationType.NO_COMMON_SLOT,
    EscalationType.SCHEDULE_CONFLICT,
    EscalationType.OWNERSHIP_SUPPORT,
    EscalationType.VIEWING_DISPUTE,
}


def _parties(db: Session, esc: Escalation) -> tuple[User | None, User | None, Booking | None, Property | None]:
    """The buyer and the seller a case is about (either may be missing), with its viewing and home."""
    requester = db.get(User, esc.requester_id) if esc.requester_id else None
    booking = db.get(Booking, esc.booking_id) if esc.booking_id else None
    prop = db.get(Property, esc.property_id) if esc.property_id else (booking.property if booking else None)
    buyer = requester if requester and requester.role == UserRole.CUSTOMER else (booking.customer if booking else None)
    seller = requester if requester and requester.role == UserRole.OWNER else None
    if seller is None and prop is not None:
        seller = db.get(User, prop.owner_id)
    return buyer, seller, booking, prop


# How much of the buyer's chat an operator sees on a case the assistant raised
CASE_CHAT_MESSAGES = 12


def case_context(db: Session, escalation_id: int) -> CaseContext:
    """The case in plain words for the operator: names and phones (operators may see them), the home, the viewing,
    and the last messages of the buyer's chat with the assistant (text only: no tool calls or other internals)."""
    esc = _load(db, escalation_id)
    buyer, seller, booking, prop = _parties(db, esc)
    ctx = CaseContext(
        buyer_name=buyer.full_name if buyer else None,
        buyer_phone=buyer.phone if buyer else None,
        seller_name=seller.full_name if seller else None,
        seller_phone=seller.phone if seller else None,
        property_label=(
            f"{prop.unit_code} · {prop.building.name} · {prop.building.project.name}" if prop is not None else None
        ),
        deal_code=booking.deal.code if booking else None,
        viewing_time=booking.start_at if booking else None,
        viewing_status=booking.status.value if booking else None,
        notify_buyer_default=buyer is not None and (esc.type in _TELL_BUYER or buyer.id == esc.requester_id),
        notify_seller_default=seller is not None and (esc.type in _TELL_SELLER or seller.id == esc.requester_id),
    )

    conv_id = esc.conversation_id
    if conv_id is None and (thread := (esc.context or {}).get("thread_id")):
        conv_id = db.scalar(select(AiConversation.id).where(AiConversation.thread_id == thread))
    if conv_id is not None:
        shown = (AiMessage.conversation_id == conv_id, AiMessage.role.in_([MessageRole.USER, MessageRole.ASSISTANT]))
        rows = db.scalars(
            select(AiMessage).where(*shown, AiMessage.content != "").order_by(AiMessage.id.desc()).limit(200)
        ).all()
        ctx.messages = [
            CaseMessage(role=m.role, content=m.content, created_at=m.created_at)
            for m in reversed(rows[:CASE_CHAT_MESSAGES])
        ]
        ctx.earlier_messages = max(0, len(rows) - CASE_CHAT_MESSAGES)
    return ctx


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
    return [_out(db, e) for e in db.scalars(stmt.order_by(Escalation.created_at))]


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
    return _out(db, esc)


def close(
    db: Session,
    actor: Actor,
    escalation_id: int,
    resolution: str,
    *,
    dismissed: bool = False,
    notify_buyer: bool | None = None,
    notify_seller: bool | None = None,
) -> EscalationOut:
    """Close a case with what was done. The buyer and/or the seller it is about are told (default by the kind of
    case, see _TELL_BUYER / _TELL_SELLER; the operator may change it). Each sees only the operator's words."""
    esc = _load(db, escalation_id)
    if esc.status not in OPEN_ESCALATION_STATUSES:
        raise StateConflictError(f"Escalation is already {esc.status.value}")
    if esc.status == EscalationStatus.IN_PROGRESS and esc.assigned_to not in (None, actor.id):
        raise StateConflictError(
            'Ca này đang do nhân viên khác xử lý; bấm "Nhận lại ca" nếu bạn tiếp quản.',
            details={"reason": "ASSIGNED_TO_OTHER", "assigned_to": esc.assigned_to},
        )
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
    buyer, seller, booking, prop = _parties(db, esc)
    if notify_buyer is None:
        notify_buyer = buyer is not None and (esc.type in _TELL_BUYER or buyer.id == esc.requester_id)
    if notify_seller is None:
        notify_seller = seller is not None and (esc.type in _TELL_SELLER or seller.id == esc.requester_id)
    told = {u.id: u for u, yes in ((buyer, notify_buyer), (seller, notify_seller)) if u is not None and yes}
    for user_id in told:
        notification_service.notify(
            db,
            user_id,
            "ESCALATION_RESOLVED",
            "Yêu cầu hỗ trợ đã được xử lý"
            if user_id == esc.requester_id
            else f"Cập nhật từ nhân viên Chủ đầu tư{f' về căn {prop.unit_code}' if prop else ''}",
            resolution,
            # Linked to the viewing it is about, so opening the notice leads there
            booking=booking,
            payload={"escalation_id": esc.id},
        )
    audit.record(db, actor, "escalation.notify", "escalation", esc.id, after={"told": sorted(told)})
    db.flush()
    retire_closed_case_notices(db)
    db.commit()
    return _out(db, esc)


# ---------- Requester ----------


# What a buyer/seller may read back of their own case: only what they wrote themselves. The rest of `context` is
# for operators (the other side's phone, no-show counters, internal ids) and never goes to the requester (AC-03)
_REQUESTER_CONTEXT = {"reason", "red_book_code", "red_book_holder_name", "note", "documents", "claim"}


def for_requester(e: Escalation) -> EscalationOut:
    out = EscalationOut.model_validate(e)
    out.context = {k: v for k, v in out.context.items() if k in _REQUESTER_CONTEXT}
    return out


def list_mine(db: Session, actor: Actor) -> list[EscalationOut]:
    rows = db.scalars(
        select(Escalation).where(Escalation.requester_id == actor.id).order_by(Escalation.created_at.desc())
    )
    return [for_requester(e) for e in rows]
