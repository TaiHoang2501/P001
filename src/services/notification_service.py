"""Notifications (spec §4.19): event messages and T-24h / T-2h viewing reminders.

Rows are added in the same transaction as the change that caused them, so a notification
exists only if the change was committed. Delivery is in-app for now (the SMS/Zalo provider
is TBD, spec §10 Q18): an immediate notification is SENT when stored; a reminder is PENDING
until the periodic job marks it SENT at its scheduled time.

Privacy level 1 (spec §4.7): messages to the seller refer to the buyer only as "Buyer #id".
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from src.config import get_settings
from src.core.actor import Actor
from src.core.errors import NotFoundError
from src.db.models import Booking, Notification, NotificationStatus, Property
from src.models.notification import NotificationOut

REMINDERS = (("T-24h", timedelta(hours=24)), ("T-2h", timedelta(hours=2)))
_WEEKDAYS = ("Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật")


def _now() -> datetime:
    return datetime.now(UTC)


def _when(t: datetime) -> str:
    local = t.astimezone(ZoneInfo(get_settings().timezone))
    return f"{local:%H:%M} {_WEEKDAYS[local.weekday()]} {local:%d/%m/%Y}"


def _label(prop: Property) -> str:
    return f"{prop.building.project.name} · {prop.building.name} · {prop.unit_code}"


def notify(
    db: Session,
    user_id: int,
    event_type: str,
    title: str,
    body: str,
    *,
    booking: Booking | None = None,
    payload: dict | None = None,
    dedupe_key: str | None = None,
) -> None:
    now = _now()
    db.add(
        Notification(
            user_id=user_id,
            event_type=event_type,
            title=title,
            body=body,
            payload=payload or {},
            booking_id=booking.id if booking else None,
            deal_id=booking.deal_id if booking else None,
            status=NotificationStatus.SENT,
            sent_at=now,
            dedupe_key=dedupe_key,
        )
    )


# ---------- Booking events ----------


def viewing_requested(db: Session, booking: Booking) -> None:
    notify(
        db,
        booking.property.owner_id,
        "VIEWING_REQUESTED",
        "Yêu cầu xem nhà mới",
        f"Buyer #{booking.customer_id} muốn xem {_label(booking.property)} lúc {_when(booking.start_at)}. "
        f"Mã deal {booking.deal.code}. Vui lòng xác nhận hoặc từ chối.",
        booking=booking,
    )


def viewing_confirmed(db: Session, booking: Booking, *, rescheduled: bool = False) -> None:
    label, when = _label(booking.property), _when(booking.start_at)
    notify(
        db,
        booking.customer_id,
        "RESCHEDULE_CONFIRMED" if rescheduled else "VIEWING_CONFIRMED",
        "Lịch xem đã được xác nhận",
        f"Chủ căn đã xác nhận lịch xem {label} lúc {when} (deal {booking.deal.code}). "
        "Căn được giữ riêng cho buổi xem trong khung giờ này.",
        booking=booking,
    )
    notify(
        db,
        booking.property.owner_id,
        "HOLD_CREATED",
        "Căn đang được giữ cho buổi xem",
        f"{label} được giữ cho buổi xem lúc {when} (deal {booking.deal.code}).",
        booking=booking,
    )
    cancel_reminders(db, booking.id)
    schedule_reminders(db, booking)


def viewing_rejected(db: Session, booking: Booking, reason: str) -> None:
    notify(
        db,
        booking.customer_id,
        "VIEWING_REJECTED",
        "Chủ căn chưa thể nhận lịch xem",
        f"Lịch xem {_label(booking.property)} lúc {_when(booking.start_at)} bị từ chối: {reason}. "
        "Trợ lý AI có thể giúp bạn chọn giờ khác hoặc căn khác.",
        booking=booking,
    )


def viewing_cancelled(db: Session, booking: Booking, actor: Actor, *, hold_released: bool) -> None:
    label, when = _label(booking.property), _when(booking.start_at)
    if actor.id != booking.customer_id:
        notify(
            db,
            booking.customer_id,
            "VIEWING_CANCELLED",
            "Lịch xem đã bị hủy",
            f"Lịch xem {label} lúc {when} đã bị hủy.",
            booking=booking,
        )
    if actor.id != booking.property.owner_id:
        notify(
            db,
            booking.property.owner_id,
            "VIEWING_CANCELLED",
            "Lịch xem đã bị hủy",
            f"Buyer #{booking.customer_id} đã hủy lịch xem {label} lúc {when}.",
            booking=booking,
        )
    if hold_released:
        notify(
            db,
            booking.property.owner_id,
            "HOLD_RELEASED",
            "Căn đã được nhả giữ",
            f"{label} không còn được giữ cho khung giờ {when}.",
            booking=booking,
        )
    cancel_reminders(db, booking.id)


def reschedule_requested(db: Session, booking: Booking) -> None:
    assert booking.proposed_start_at is not None
    notify(
        db,
        booking.property.owner_id,
        "RESCHEDULE_REQUESTED",
        "Yêu cầu đổi lịch xem",
        f"Buyer #{booking.customer_id} muốn đổi lịch xem {_label(booking.property)} từ {_when(booking.start_at)} "
        f"sang {_when(booking.proposed_start_at)}.",
        booking=booking,
    )


def reschedule_declined(db: Session, booking: Booking, reason: str) -> None:
    notify(
        db,
        booking.customer_id,
        "RESCHEDULE_DECLINED",
        "Chủ căn giữ nguyên lịch xem",
        f"Chủ căn chưa đồng ý giờ mới ({reason}). Lịch xem vẫn là {_when(booking.start_at)}.",
        booking=booking,
    )


# ---------- Listing / seller events ----------


def listing_reviewed(db: Session, prop: Property, *, approved: bool, reason: str | None = None) -> None:
    if approved:
        notify(db, prop.owner_id, "LISTING_APPROVED", "Tin đăng đã được duyệt", f"{_label(prop)} đã lên hệ thống.")
    else:
        notify(db, prop.owner_id, "LISTING_REJECTED", "Tin đăng bị từ chối", f"{_label(prop)}: {reason}")


def seller_reviewed(db: Session, user_id: int, *, verified: bool, reason: str | None = None) -> None:
    if verified:
        notify(
            db, user_id, "SELLER_VERIFIED", "Tài khoản chủ căn đã được xác thực", "Bạn có thể gửi tin đăng để duyệt."
        )
    else:
        notify(db, user_id, "SELLER_REJECTED", "Xác thực chủ căn chưa thành công", reason or "")


# ---------- Reminders ----------


def schedule_reminders(db: Session, booking: Booking) -> None:
    """T-24h and T-2h reminders to buyer and seller; skipped if that moment has already passed."""
    now = _now()
    label, when = _label(booking.property), _when(booking.start_at)
    for name, before in REMINDERS:
        due = booking.start_at - before
        if due <= now:
            continue
        for user_id in (booking.customer_id, booking.property.owner_id):
            db.add(
                Notification(
                    user_id=user_id,
                    event_type=f"REMINDER_{name.replace('-', '')}",
                    title="Sắp đến giờ xem nhà",
                    body=f"Nhắc lịch: xem {label} lúc {when} (deal {booking.deal.code}).",
                    booking_id=booking.id,
                    deal_id=booking.deal_id,
                    status=NotificationStatus.PENDING,
                    scheduled_at=due,
                    dedupe_key=f"booking:{booking.id}:{booking.start_at.isoformat()}:{name}:user:{user_id}",
                )
            )


def cancel_reminders(db: Session, booking_id: int) -> None:
    db.execute(
        update(Notification)
        .where(Notification.booking_id == booking_id, Notification.status == NotificationStatus.PENDING)
        .values(status=NotificationStatus.CANCELLED)
    )


def deliver_due(db: Session, now: datetime | None = None) -> int:
    """Periodic job: PENDING reminders whose time has come become SENT (visible in-app)."""
    now = now or _now()
    ids = list(
        db.scalars(
            update(Notification)
            .where(Notification.status == NotificationStatus.PENDING, Notification.scheduled_at <= now)
            .values(status=NotificationStatus.SENT, sent_at=now, attempts=Notification.attempts + 1)
            .returning(Notification.id)
        )
    )
    db.commit()
    return len(ids)


# ---------- Reads ----------


def _visible(actor: Actor):
    return (Notification.user_id == actor.id) & (Notification.status == NotificationStatus.SENT)


def list_for(db: Session, actor: Actor, *, unread_only: bool = False, limit: int = 50) -> list[NotificationOut]:
    stmt = select(Notification).where(_visible(actor))
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    rows = db.scalars(stmt.order_by(Notification.sent_at.desc(), Notification.id.desc()).limit(limit))
    return [NotificationOut.model_validate(n) for n in rows]


def unread_count(db: Session, actor: Actor) -> int:
    return db.scalar(select(func.count()).where(_visible(actor), Notification.read_at.is_(None))) or 0


def mark_read(db: Session, actor: Actor, notification_id: int) -> NotificationOut:
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != actor.id or n.status != NotificationStatus.SENT:
        raise NotFoundError(f"Notification {notification_id} not found")
    if n.read_at is None:
        n.read_at = _now()
        db.commit()
    return NotificationOut.model_validate(n)


def mark_all_read(db: Session, actor: Actor) -> int:
    count = db.execute(
        update(Notification).where(_visible(actor), Notification.read_at.is_(None)).values(read_at=_now())
    ).rowcount
    db.commit()
    return count
