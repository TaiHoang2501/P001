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
from typing import NoReturn

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, joinedload, selectinload

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
    AuditLog,
    AvailabilitySlot,
    Booking,
    BookingStatus,
    Building,
    BuyerAvailability,
    BuyerProfile,
    DealStatus,
    Property,
    PropertyStatus,
    User,
    UserRole,
)
from src.models.booking import ActivityOut, BookingCreate, BookingOut, RescheduleRequest
from src.services import (
    audit,
    availability_service,
    deal_service,
    escalation_service,
    hold_service,
    notification_service,
    seller_service,
)
from src.services.availability_service import TimeConflictError, is_exclusion_violation, list_slots, owner_busy

# Booking lifecycle (spec §4.12)
_TRANSITIONS: dict[BookingStatus, set[BookingStatus]] = {
    BookingStatus.REQUESTED: {
        BookingStatus.CONFIRMED,
        BookingStatus.REJECTED,
        BookingStatus.CANCELLED,
        BookingStatus.EXPIRED,
    },
    BookingStatus.CONFIRMED: {
        BookingStatus.COMPLETED,
        BookingStatus.CANCELLED,
        BookingStatus.RESCHEDULE_REQUESTED,
        BookingStatus.NO_SHOW,
    },
    # Owner accepts (new time) or declines (old time stays) -> CONFIRMED either way
    BookingStatus.RESCHEDULE_REQUESTED: {BookingStatus.CONFIRMED, BookingStatus.CANCELLED},
    BookingStatus.REJECTED: set(),
    BookingStatus.CANCELLED: set(),
    BookingStatus.COMPLETED: set(),
    BookingStatus.NO_SHOW: set(),
    BookingStatus.OWNER_ABSENT: set(),
    BookingStatus.UNREPORTED: set(),
    BookingStatus.EXPIRED: set(),
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


def expire_unanswered(db: Session, now: datetime | None = None) -> int:
    """Periodic job: what the owner did not answer before the viewing time can no longer happen.

    - A request whose viewing time has come -> EXPIRED; the buyer is told (in the chat, with a way to find
      another time) and a "seller did not answer" case, if any, closes.
    - A new time asked for on a confirmed viewing, now passed -> the request lapses; the confirmed viewing stays.
    Returns how many were closed.
    """
    now = now or _now()
    rows = db.scalars(
        select(Booking)
        .where(
            or_(
                and_(Booking.status == BookingStatus.REQUESTED, Booking.start_at <= now),
                and_(Booking.status == BookingStatus.RESCHEDULE_REQUESTED, Booking.proposed_start_at <= now),
            )
        )
        .with_for_update(skip_locked=True)
    ).all()
    for booking in rows:
        if booking.status == BookingStatus.REQUESTED:
            before = _transition(booking, BookingStatus.EXPIRED)
            _audit_transition(db, None, "booking.expired", booking, before)
            escalation_service.settle_no_response(
                db, None, booking.id, "Giờ xem đã qua mà chủ căn chưa trả lời: yêu cầu tự hết hạn."
            )
            notification_service.viewing_expired(db, booking)
        else:
            before = _transition(booking, BookingStatus.CONFIRMED)
            lapsed = booking.proposed_start_at
            booking.proposed_start_at = booking.proposed_end_at = None
            _audit_transition(
                db, None, "booking.reschedule_lapsed", booking, before, lapsed=lapsed.isoformat() if lapsed else None
            )
            notification_service.reschedule_lapsed(db, booking)
        _sync_deal(db, None, booking)
    db.commit()
    return len(rows)


def respond_by(booking: Booking) -> datetime:
    """When the seller must have answered a request: `seller_response_hours` after it was sent, but never later
    than `seller_response_lead_minutes` before the viewing (a request for tomorrow cannot wait 24 hours)."""
    s = get_settings()
    return min(
        booking.created_at + timedelta(hours=s.seller_response_hours),
        booking.start_at - timedelta(minutes=s.seller_response_lead_minutes),
    )


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
        # The seller always sees who asks to view (product decision); the phone stays hidden until level 3
        customer_name=booking.customer.full_name,
        customer_phone=booking.customer.phone if show_contact else None,
        owner_name=prop.owner.full_name if viewer.role == UserRole.INVESTOR_OPERATOR else None,
        owner_phone=prop.owner.phone if viewer.role == UserRole.INVESTOR_OPERATOR else None,
        start_at=booking.start_at,
        end_at=booking.end_at,
        status=booking.status,
        hold_status=booking.hold.status if booking.hold else None,
        proposed_start_at=booking.proposed_start_at,
        proposed_end_at=booking.proposed_end_at,
        created_via=booking.created_via,
        customer_note=booking.customer_note,
        rejection_reason=booking.rejection_reason,
        suggested_starts=booking.suggested_starts or [],
        closed_by_system=booking.status == BookingStatus.REJECTED
        and booking.rejection_reason in (SUPERSEDED_REASON, SOLD_REASON),
        responded_at=booking.responded_at,
        created_at=booking.created_at,
        respond_by=respond_by(booking) if booking.status == BookingStatus.REQUESTED else None,
        deal_status=deal.status,
    )


def _audit_transition(
    db: Session, actor: Actor | None, action: str, booking: Booking, before: BookingStatus, **extra
) -> None:
    audit.record(
        db,
        actor,
        action,
        "booking",
        booking.id,
        before={"status": before},
        after={"status": booking.status, "start_at": booking.start_at.isoformat(), **extra},
    )


# ---------- Customer ----------


def create_request(db: Session, actor: Actor, data: BookingCreate) -> BookingOut:
    if actor.role != UserRole.CUSTOMER:
        raise ForbiddenError("Only customers can request viewings")

    prop = db.get(Property, data.property_id)
    if prop is None or prop.status != PropertyStatus.AVAILABLE:
        raise NotFoundError(f"Property {data.property_id} not found")
    seller_service.require_verified(db, prop.owner_id)  # AC-04
    slot, start_at, end_at = _resolve_time(db, prop, slot_id=data.slot_id, start_at=data.start_at)
    _require_owner_free(db, prop, start_at, end_at)

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
    except TimeConflictError as e:
        _raise_slot_taken(db, e, data.property_id)
    audit.record(
        db,
        actor,
        "booking.request",
        "booking",
        booking.id,
        after={"status": booking.status, "property_id": prop.id, "deal_id": deal.id, "start_at": start_at.isoformat()},
    )
    deal_service.sync_status(db, actor, deal)
    notification_service.viewing_requested(db, booking)
    db.commit()
    return to_out(_load(db, booking.id), actor)


def _lock_owner(db: Session, owner_id: int) -> None:
    """Serialize viewing changes per owner: a request cannot slip in while the owner confirms another one."""
    db.execute(select(User.id).where(User.id == owner_id).with_for_update())


def _require_owner_free(
    db: Session, prop: Property, start_at: datetime, end_at: datetime, *, except_booking: int | None = None
) -> None:
    """The owner already confirmed a viewing at this time (on any of their homes): offer the free times instead."""
    _lock_owner(db, prop.owner_id)
    if owner_busy(db, prop.owner_id, start_at, end_at, except_booking=except_booking):
        raise SlotUnavailableError(
            "The owner already has a confirmed viewing at this time",
            details={"free_slots": [s.model_dump(mode="json") for s in list_slots(db, prop.id)]},
        )


SUPERSEDED_REASON = "Chủ căn đã nhận một lịch xem khác vào giờ này"


def _close_overlapping(db: Session, confirmed: Booking) -> None:
    """The owner just took this time: other buyers' overlapping requests can no longer happen.

    Unanswered requests are closed and their buyers told by the assistant (with free times); a new time asked for
    on a confirmed viewing is declined and its old time stays. Same transaction as the confirmation.
    """
    overlapping = db.scalars(
        select(Booking)
        .where(
            Booking.owner_id == confirmed.owner_id,
            Booking.id != confirmed.id,
            Booking.status.in_((BookingStatus.REQUESTED, BookingStatus.RESCHEDULE_REQUESTED)),
        )
        .with_for_update()
    ).all()
    for other in overlapping:
        if (
            other.status == BookingStatus.REQUESTED
            and other.start_at < confirmed.end_at
            and other.end_at > confirmed.start_at
        ):
            before = _transition(other, BookingStatus.REJECTED)
            other.responded_at = _now()
            other.rejection_reason = SUPERSEDED_REASON
            _audit_transition(db, None, "booking.superseded", other, before, reason=SUPERSEDED_REASON)
            escalation_service.settle_no_response(db, None, other.id, "Chủ căn đã nhận một lịch xem khác vào giờ này.")
            _sync_deal(db, None, other)
            free = [s.start_at for s in list_slots(db, other.property_id)[:3]]
            notification_service.viewing_superseded(db, other, free)
        elif (
            other.status == BookingStatus.RESCHEDULE_REQUESTED
            and other.proposed_start_at is not None
            and other.proposed_end_at is not None
            and other.proposed_start_at < confirmed.end_at
            and other.proposed_end_at > confirmed.start_at
        ):
            before = _transition(other, BookingStatus.CONFIRMED)
            other.proposed_start_at = other.proposed_end_at = None
            other.responded_at = _now()
            _audit_transition(db, None, "booking.reschedule_decline", other, before, reason=SUPERSEDED_REASON)
            _sync_deal(db, None, other)
            notification_service.reschedule_declined(db, other, SUPERSEDED_REASON)


SOLD_REASON = "Căn đã được bán"


def close_for_sold(db: Session, actor: Actor, prop: Property) -> int:
    """The owner sold the home: every viewing still ahead of it is closed and its buyer told the home was sold, in
    the owner's transaction (no commit). Unanswered requests are declined, confirmed viewings not yet held are
    cancelled (their holds released). A viewing whose time has come stays: its outcome is still recorded (a new
    time asked for on it is dropped). Returns how many buyers' viewings were closed."""
    now = _now()
    bookings = db.scalars(
        select(Booking)
        .where(Booking.property_id == prop.id, Booking.status.in_(ACTIVE_BOOKING_STATUSES))
        .order_by(Booking.start_at)
        .with_for_update()
    ).all()
    closed = 0
    for booking in bookings:
        if booking.start_at <= now and booking.status != BookingStatus.REQUESTED:
            # Already taking place or held: kept for its outcome, without the new time it asked for
            if booking.status == BookingStatus.RESCHEDULE_REQUESTED:
                before = _transition(booking, BookingStatus.CONFIRMED)
                booking.proposed_start_at = booking.proposed_end_at = None
                _audit_transition(db, actor, "booking.reschedule_decline", booking, before, reason=SOLD_REASON)
                _sync_deal(db, actor, booking)
                notification_service.reschedule_declined(db, booking, SOLD_REASON)
            continue
        if booking.status == BookingStatus.REQUESTED:
            before = _transition(booking, BookingStatus.REJECTED)
            booking.responded_at = now
            booking.rejection_reason = SOLD_REASON
        else:
            before = _transition(booking, BookingStatus.CANCELLED)
            booking.cancelled_at = now
            booking.cancelled_by = actor.id
            hold_service.release(db, actor, booking.id, "property_sold")
        booking.proposed_start_at = booking.proposed_end_at = None
        _audit_transition(db, actor, "booking.closed_sold", booking, before, reason=SOLD_REASON)
        escalation_service.settle_no_response(db, actor, booking.id, "Chủ căn đã bán căn này.")
        _sync_deal(db, actor, booking)
        if booking.deal.status == DealStatus.MATCHED:
            # Nothing left to view on a sold home: the deal is over
            booking.deal.status = DealStatus.CLOSED
            audit.record(
                db,
                actor,
                "deal.status",
                "deal",
                booking.deal.id,
                before={"status": DealStatus.MATCHED},
                after={"status": DealStatus.CLOSED},
                extra={"reason": SOLD_REASON},
            )
        notification_service.property_sold(db, booking, was_confirmed=before != BookingStatus.REQUESTED)
        closed += 1
    return closed


def _raise_slot_taken(db: Session, err: DBAPIError, property_id: int) -> NoReturn:
    """Roll back first: the session is unusable after a failed flush."""
    db.rollback()
    if is_exclusion_violation(err):
        # Someone else holds this window: return alternatives so UI/AI can re-offer (spec §6.3)
        raise SlotUnavailableError(
            "This viewing slot was just taken",
            details={"free_slots": [s.model_dump(mode="json") for s in list_slots(db, property_id)]},
        ) from err
    raise err


def _resolve_time(
    db: Session, prop: Property, *, slot_id: int | None = None, start_at: datetime | None = None
) -> tuple[AvailabilitySlot | None, datetime, datetime]:
    """Viewing window from a seller slot, or from a start time that must fit inside one."""
    if slot_id is not None:
        slot = db.get(AvailabilitySlot, slot_id)
        if slot is None or slot.property_id != prop.id:
            raise NotFoundError(f"Slot {slot_id} not found for property {prop.id}")
        start_at, end_at = slot.start_at, slot.end_at
    else:
        assert start_at is not None  # callers validate that one of the two is given
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
    notice = get_settings().viewing_min_notice_minutes
    if start_at < _now() + timedelta(minutes=notice):
        raise BusinessRuleViolationError(
            f"Book a viewing at least {notice} minutes ahead", details={"min_notice_minutes": notice}
        )
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
    booking.proposed_start_at = booking.proposed_end_at = None
    released = hold_service.release(db, actor, booking.id, "cancelled")
    _audit_transition(db, actor, "booking.cancel", booking, before)
    escalation_service.settle_no_response(db, actor, booking.id, "Người mua đã hủy yêu cầu xem.")
    _sync_deal(db, actor, booking)
    notification_service.viewing_cancelled(db, booking, actor, hold_released=released)
    db.commit()
    return to_out(booking, actor)


def operator_cancel(db: Session, actor: Actor, booking_id: int) -> BookingOut:
    """The operator's manual fallback, only before the viewing: once its time has come, what happened is recorded
    after the viewing (outcome), not cancelled."""
    booking = _load(db, booking_id)
    if booking.start_at <= _now():
        raise BusinessRuleViolationError(
            "Buổi xem đã tới giờ nên không hủy được; kết quả buổi xem do chủ căn ghi nhận.",
            details={"reason": "VIEWING_STARTED"},
        )
    return cancel(db, actor, booking_id)


def reschedule(db: Session, actor: Actor, booking_id: int, data: RescheduleRequest) -> BookingOut:
    """Buyer moves a viewing to another time (spec §4.12, extended).

    - REQUESTED (owner has not answered yet): the request itself moves to the new time and stays REQUESTED;
      the owner is told and still has to confirm it.
    - CONFIRMED: the owner must confirm the new time; the current time and its hold stay until then.
    """
    # Owner first, then the booking (same lock order as a confirmation)
    owner_id = db.scalar(select(Booking.owner_id).where(Booking.id == booking_id))
    if owner_id is not None:
        _lock_owner(db, owner_id)
    booking = _load(db, booking_id, for_update=True)
    if booking.customer_id != actor.id:
        raise NotFoundError(f"Booking {booking_id} not found")
    deal_service.require_open(booking.deal)
    if booking.property.status != PropertyStatus.AVAILABLE:
        raise StateConflictError("This home is no longer open for viewings", details={"reason": "PROPERTY_UNAVAILABLE"})
    if booking.start_at <= _now():
        # Its outcome is recorded now (seen / no-show); a new time would let it slip past that
        raise BusinessRuleViolationError("This viewing's time has already come", details={"reason": "VIEWING_STARTED"})
    if booking.status == BookingStatus.REQUESTED:
        return _move_request(db, actor, booking, data)
    _, start_at, end_at = _resolve_time(db, booking.property, start_at=data.start_at)
    _require_owner_free(db, booking.property, start_at, end_at, except_booking=booking.id)
    before = _transition(booking, BookingStatus.RESCHEDULE_REQUESTED)
    booking.proposed_start_at, booking.proposed_end_at = start_at, end_at
    _audit_transition(db, actor, "booking.reschedule_request", booking, before, proposed_start_at=start_at.isoformat())
    _sync_deal(db, actor, booking)
    notification_service.reschedule_requested(db, booking)
    db.commit()
    return to_out(booking, actor)


def _move_request(db: Session, actor: Actor, booking: Booking, data: RescheduleRequest) -> BookingOut:
    """Change the time of a request the owner has not answered: nothing is held yet, so it simply moves."""
    property_id = booking.property_id  # read now: attributes can't be loaded after a failed flush
    old_start, old_end = booking.start_at, booking.end_at
    slot, start_at, end_at = _resolve_time(db, booking.property, start_at=data.start_at)
    _require_owner_free(db, booking.property, start_at, end_at)
    try:
        booking.slot_id = slot.id if slot else None
        booking.start_at, booking.end_at = start_at, end_at
        db.flush()
    except TimeConflictError as e:
        _raise_slot_taken(db, e, property_id)
    audit.record(
        db,
        actor,
        "booking.request_time_change",
        "booking",
        booking.id,
        before={"status": booking.status, "start_at": old_start.isoformat(), "end_at": old_end.isoformat()},
        after={"status": booking.status, "start_at": start_at.isoformat(), "end_at": end_at.isoformat()},
    )
    notification_service.request_time_changed(db, booking, old_start)
    db.commit()
    return to_out(_load(db, booking.id), actor)


def _sync_deal(db: Session, actor: Actor | None, booking: Booking) -> None:
    db.flush()
    deal_service.sync_status(db, actor, booking.deal)


# ---------- Owner (human-in-the-loop) ----------


def _load_for_owner(db: Session, actor: Actor, booking_id: int) -> Booking:
    booking = _load(db, booking_id, for_update=True)
    if booking.property.owner_id != actor.id:
        raise NotFoundError(f"Booking {booking_id} not found")
    return booking


def approve(db: Session, actor: Actor, booking_id: int) -> BookingOut:
    """Owner confirms a request (or a new time) -> CONFIRMED + viewing hold, in one transaction (AC-05, AC-08)."""
    if actor.role != UserRole.OWNER:
        raise ForbiddenError("Only the property owner can confirm a viewing")
    # Owner first, then the booking: the same lock order everywhere, so concurrent changes cannot deadlock
    _lock_owner(db, actor.id)
    booking = _load_for_owner(db, actor, booking_id)
    deal_service.require_open(booking.deal)
    if booking.property.status != PropertyStatus.AVAILABLE:
        raise StateConflictError("This home is no longer open for viewings", details={"reason": "PROPERTY_UNAVAILABLE"})
    property_id = booking.property_id  # read now: attributes can't be loaded after a failed flush
    rescheduling = booking.status == BookingStatus.RESCHEDULE_REQUESTED
    if rescheduling:
        assert booking.proposed_start_at is not None and booking.proposed_end_at is not None
        booking.start_at, booking.end_at = booking.proposed_start_at, booking.proposed_end_at
        booking.proposed_start_at = booking.proposed_end_at = None
    if booking.start_at <= _now():
        raise BusinessRuleViolationError("Viewing time has already passed")
    before = _transition(booking, BookingStatus.CONFIRMED)
    booking.responded_at = _now()
    try:
        db.flush()  # the booking's own no-overlap constraint for a new time
        hold = hold_service.active_for(db, booking.id) if rescheduling else None
        if hold is not None:
            hold_service.move(db, actor, hold, booking)
        else:
            hold_service.create_for(db, actor, booking)
    except TimeConflictError as e:
        _raise_slot_taken(db, e, property_id)
    _audit_transition(db, actor, "booking.reschedule_approve" if rescheduling else "booking.approve", booking, before)
    escalation_service.settle_no_response(db, actor, booking.id, "Chủ căn đã xác nhận lịch xem.")
    _sync_deal(db, actor, booking)
    notification_service.viewing_confirmed(db, booking, rescheduled=rescheduling)
    _close_overlapping(db, booking)
    db.commit()
    return to_out(_load(db, booking.id), actor)


def reject(
    db: Session,
    actor: Actor,
    booking_id: int,
    reason: str,
    *,
    suggested_starts: list[datetime] | None = None,
    close_time: bool = False,
) -> BookingOut:
    """Decline a request (or a new time asked for). The owner may offer up to three other times of their own
    (the buyer books one in a tap) and may close the declined time so nobody else asks for it."""
    if actor.role != UserRole.OWNER:
        raise ForbiddenError("Only the property owner can reject a viewing")
    booking = _load_for_owner(db, actor, booking_id)
    if suggested_starts and booking.status != BookingStatus.REQUESTED:
        raise BusinessRuleViolationError("Other times can be suggested for a new request only")
    if booking.status == BookingStatus.RESCHEDULE_REQUESTED:
        # Declining a new time keeps the viewing (and its hold) at the original time
        before = _transition(booking, BookingStatus.CONFIRMED)
        booking.proposed_start_at = booking.proposed_end_at = None
        booking.responded_at = _now()
        _audit_transition(db, actor, "booking.reschedule_decline", booking, before, reason=reason)
        _sync_deal(db, actor, booking)
        notification_service.reschedule_declined(db, booking, reason)
        db.commit()
        return to_out(booking, actor)
    offered = (
        availability_service.require_offerable(db, booking.property_id, suggested_starts) if suggested_starts else []
    )
    before = _transition(booking, BookingStatus.REJECTED)
    booking.responded_at = _now()
    booking.rejection_reason = reason
    booking.suggested_starts = offered or None
    db.flush()
    closed = (
        availability_service.close_time(db, actor, booking.property_id, booking.start_at, booking.end_at)
        if close_time
        else 0
    )
    _audit_transition(
        db,
        actor,
        "booking.reject",
        booking,
        before,
        reason=reason,
        suggested_starts=[t.isoformat() for t in offered],
        closed_slots=closed,
    )
    escalation_service.settle_no_response(
        db, actor, booking.id, "Chủ căn đã trả lời: không nhận lịch" + (", đề xuất giờ khác." if offered else ".")
    )
    _sync_deal(db, actor, booking)
    notification_service.viewing_rejected(db, booking, reason, offered)
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
    hold_service.release(db, actor, booking.id, "completed")
    _audit_transition(db, actor, "booking.complete", booking, before)
    _sync_deal(db, actor, booking)
    notification_service.cancel_reminders(db, booking.id)
    notification_service.notify(
        db,
        booking.customer_id,
        "VIEWING_COMPLETED",
        "Bạn thấy căn thế nào?",
        f"Buổi xem {booking.property.unit_code} đã hoàn tất. Cho chủ căn và trợ lý biết bạn có quan tâm không "
        "trong mục Hoạt động.",
        booking=booking,
    )
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
        selectinload(Booking.hold),
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


# ---------- Activity history (buyer) ----------

_ACTIVITY_KIND = {
    "booking.request": "REQUESTED",
    "booking.request_time_change": "TIME_CHANGED",
    "booking.reschedule_request": "RESCHEDULE_REQUESTED",
    "booking.approve": "CONFIRMED",
    "booking.reject": "REJECTED",
    "booking.reschedule_approve": "RESCHEDULE_APPROVED",
    "booking.reschedule_decline": "RESCHEDULE_DECLINED",
    "booking.cancel": "CANCELLED",
    "booking.complete": "COMPLETED",
    "booking.superseded": "SUPERSEDED",
    "booking.closed_sold": "SOLD",
    "booking.no_show": "NO_SHOW",
    "booking.unreported": "UNREPORTED",
    "booking.expired": "EXPIRED",
    "booking.reschedule_lapsed": "RESCHEDULE_LAPSED",
    "booking.dispute": "DISPUTED",
    "booking.feedback": "FEEDBACK",
    "booking.outcome_by_operator": "OUTCOME",
}

# What an event says, when it depends on the details (the buyer's answer, the operator's finding)
_KIND_BY_DETAIL = {
    ("FEEDBACK", "INTERESTED"): "INTERESTED",
    ("FEEDBACK", "NOT_SUITABLE"): "NOT_SUITABLE",
    ("OUTCOME", "COMPLETED"): "COMPLETED",
    ("OUTCOME", "NO_SHOW"): "NO_SHOW",
    ("OUTCOME", "OWNER_ABSENT"): "OWNER_ABSENT",
}


def activity_for(db: Session, actor: Actor, limit: int = 200) -> list[ActivityOut]:
    """The buyer's viewing history, newest first, from the audit log of their bookings."""
    bookings = {
        b.id: b
        for b in db.scalars(
            select(Booking)
            .where(Booking.customer_id == actor.id)
            .options(
                joinedload(Booking.property, innerjoin=True)
                .joinedload(Property.building, innerjoin=True)
                .joinedload(Building.project, innerjoin=True),
                joinedload(Booking.deal),
            )
        ).unique()
    }
    if not bookings:
        return []
    rows = db.scalars(
        select(AuditLog)
        .where(
            AuditLog.target_type == "booking",
            AuditLog.target_id.in_(bookings),
            AuditLog.action.in_(_ACTIVITY_KIND),
        )
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
    )
    out: list[ActivityOut] = []
    for row in rows:
        b = bookings[row.target_id]
        after = row.after or {}
        if row.actor_id == actor.id:
            by = "BUYER"
        elif row.actor_id is not None and row.actor_id == b.property.owner_id:
            by = "OWNER"
        else:
            by = "BOOKINGBOT"
        when = after.get("proposed_start_at") or after.get("start_at")
        out.append(
            ActivityOut(
                id=row.id,
                at=row.created_at,
                kind=_KIND_BY_DETAIL.get(
                    (_ACTIVITY_KIND[row.action], after.get("interest") or after.get("status")),
                    _ACTIVITY_KIND[row.action],
                ),
                by=by,
                booking_id=b.id,
                property_id=b.property_id,
                property_label=to_out(b, actor).property_label,
                deal_code=b.deal.code,
                start_at=datetime.fromisoformat(when) if when else None,
                reason=after.get("reason"),
                booking_status=b.status,
                booking_start_at=b.start_at,
                booking_end_at=b.end_at,
            )
        )
    return out
