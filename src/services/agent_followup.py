"""The agent acting while the buyer is away (run by the periodic job, and on listing approval).

1. A viewing request the seller has not answered after `agent_followup_minutes`, or has rejected: the agent
   looks for other free times of that home and for similar homes, and sends the buyer those options. The
   request itself is left as it is: only the seller can confirm (AC-05), and the 24h operator escalation
   (escalation_service) still applies.
2. A newly approved listing that fits a buyer's remembered criteria (buyer_memory): the buyer is told.
3. Due viewing reminders to buyers are worded for them (agent_writer) just before they are delivered.

Every suggestion comes from the same services the chat uses (verified sellers' AVAILABLE homes, real free
times); nothing is booked on the buyer's behalf. Each message is sent once (notifications.dedupe_key).
"""

import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.db.models import (
    Booking,
    BookingStatus,
    BuyerAvailability,
    BuyerProfile,
    Notification,
    NotificationStatus,
    Property,
    User,
)
from src.models.booking import TimeWindow, ViewingTimesRequest
from src.models.property import SearchCriteria
from src.services import agent_writer, availability_service, buyer_memory, notification_service, property_service

logger = logging.getLogger(__name__)

_MAX_TIMES = 3
_MAX_SIMILAR = 2
# Rejections older than this are not followed up (e.g. after a long downtime)
_REJECTION_LOOKBACK = timedelta(days=2)
# A new listing is announced to buyers whose remembered criteria it fits at least this well
_NEW_MATCH_MIN_SCORE = 0.6
_WEEKDAYS = ("Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật")


def _when(t: datetime) -> str:
    local = t.astimezone(ZoneInfo(get_settings().timezone))
    return f"{local:%H:%M} {_WEEKDAYS[local.weekday()]} {local:%d/%m}"


def _price(vnd: int) -> str:
    return f"{vnd / 1_000_000_000:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " tỷ"


def _label(prop: Property) -> str:
    return f"{prop.unit_code} ({prop.building.project.name})"


def _already_sent(db: Session, key: str) -> bool:
    return db.scalar(select(Notification.id).where(Notification.dedupe_key == key)) is not None


# ---------- 1. Unanswered / rejected viewing requests ----------


def run(db: Session, now: datetime | None = None) -> int:
    """Periodic job: follow up waiting and rejected requests. Returns how many buyers were messaged."""
    now = now or datetime.now(UTC)
    waiting_cutoff = now - timedelta(minutes=get_settings().agent_followup_minutes)
    candidates = [
        ("waiting", b)
        for b in db.scalars(
            select(Booking).where(
                Booking.status == BookingStatus.REQUESTED,
                Booking.created_at <= waiting_cutoff,
                Booking.start_at > now,
            )
        )
    ] + [
        ("rejected", b)
        for b in db.scalars(
            select(Booking).where(
                Booking.status == BookingStatus.REJECTED,
                Booking.responded_at >= now - _REJECTION_LOOKBACK,
            )
        )
    ]
    sent = 0
    for kind, booking in candidates:
        key = f"agent-followup:booking:{booking.id}:{kind}"
        if _already_sent(db, key):
            continue
        try:
            _follow_up(db, booking, kind, key, now)
            db.commit()
            sent += 1
        except Exception:
            db.rollback()
            logger.exception("agent follow-up failed for booking %s", booking.id)
    return sent


def _buyer_windows(db: Session, booking: Booking, now: datetime) -> list[TimeWindow]:
    """When the buyer said they are free: this deal's windows, else what the agent remembers, else 3 days."""
    rows = db.scalars(
        select(BuyerAvailability).where(BuyerAvailability.deal_id == booking.deal_id, BuyerAvailability.end_at > now)
    ).all()
    windows = [TimeWindow(start_at=r.start_at, end_at=r.end_at) for r in rows]
    if not windows:
        windows = [TimeWindow.model_validate(w) for w in buyer_memory.known_windows(db, booking.customer_id)]
    if not windows:
        tz = ZoneInfo(get_settings().timezone)
        today = now.astimezone(tz).date()
        windows = [
            TimeWindow(
                start_at=datetime(d.year, d.month, d.day, 8, tzinfo=tz),
                end_at=datetime(d.year, d.month, d.day, 20, tzinfo=tz),
            )
            for d in (today + timedelta(days=i) for i in range(1, 4))
        ]
    return windows[:10]


def _other_times(db: Session, booking: Booking, now: datetime) -> list[TimeWindow]:
    try:
        out = availability_service.propose_viewing_times(
            db, booking.property_id, ViewingTimesRequest(windows=_buyer_windows(db, booking, now))
        )
    except Exception:
        # The home may no longer be bookable (sold, withdrawn): just no other times
        return []
    slots = out.proposals or out.alternatives
    return [s for s in slots if s.start_at != booking.start_at][:_MAX_TIMES]


def _similar_homes(db: Session, booking: Booking) -> list[Property]:
    """Homes like the requested one, ranked against what the buyer asked for."""
    prop = booking.property
    remembered = buyer_memory.known_criteria(db, booking.customer_id)
    criteria = remembered or {
        "project_codes": [prop.building.project.code],
        "bedrooms_min": prop.bedrooms,
        "budget_max": int(prop.price_vnd * 1.15),
        "preferred_bedrooms": prop.bedrooms,
    }
    busy = set(
        db.scalars(
            select(Booking.property_id).where(
                Booking.customer_id == booking.customer_id,
                Booking.status.in_((BookingStatus.REQUESTED, BookingStatus.CONFIRMED)),
            )
        )
    )
    result = property_service.search(db, SearchCriteria.model_validate({**criteria, "limit": 8}))
    ids = [r.property.id for r in result.results if r.property.id != prop.id and r.property.id not in busy]
    return [db.get(Property, i) for i in ids[:_MAX_SIMILAR]]


def _follow_up(db: Session, booking: Booking, kind: str, key: str, now: datetime) -> None:
    times = _other_times(db, booking, now)
    similar = _similar_homes(db, booking)
    prop, code = booking.property, booking.deal.code
    opening = (
        f"Chủ căn {_label(prop)} chưa phản hồi yêu cầu xem lúc {_when(booking.start_at)} (deal {code}); "
        "yêu cầu vẫn đang chờ."
        if kind == "waiting"
        else f"Chủ căn {_label(prop)} đã từ chối lịch xem lúc {_when(booking.start_at)} (deal {code})."
    )
    options = []
    if times:
        options.append(f"Giờ trống khác của căn này: {', '.join(_when(t.start_at) for t in times)}.")
    if similar:
        homes = ", ".join(f"{_label(p)} – {_price(p.price_vnd)}, {p.bedrooms} PN" for p in similar)
        options.append(f"Căn tương tự còn trống: {homes}.")
    if options:
        closing = "Nhắn Trợ lý AI trong mục Tìm nhà để đặt một lựa chọn."
    else:
        closing = "Trợ lý AI chưa tìm được lựa chọn thay thế; bộ phận hỗ trợ của Chủ đầu tư sẽ theo dõi giúp bạn."
    template = " ".join([opening, *options, closing])

    buyer = db.get(User, booking.customer_id)
    body = agent_writer.compose(
        "Báo người mua tình trạng yêu cầu xem nhà và gợi ý lựa chọn thay thế để họ đặt",
        {
            "tên người mua": buyer.full_name if buyer else "",
            "tình trạng": opening,
            "giờ khác": options[0] if times else "",
            "căn tương tự": options[-1] if similar else "",
            "cách đặt": closing,
        },
        template,
        must_include=[code],
    )
    notification_service.notify(
        db,
        booking.customer_id,
        "AGENT_FOLLOWUP",
        "Trợ lý AI gợi ý lựa chọn khác" if options else "Cập nhật yêu cầu xem nhà",
        body,
        booking=booking,
        payload={
            "kind": kind,
            "times": [t.model_dump(mode="json") for t in times],
            "property_ids": [p.id for p in similar],
        },
        dedupe_key=key,
    )


# ---------- 2. New listing that fits a buyer ----------


def announce_listing(db: Session, prop: Property) -> int:
    """On approval: tell buyers whose remembered criteria this home fits (same transaction as the approval)."""
    profiles = db.scalars(select(BuyerProfile).where(BuyerProfile.preferences != {})).all()
    told = 0
    for profile in profiles:
        try:
            criteria = SearchCriteria.model_validate(profile.preferences)
        except Exception:
            continue
        rec = property_service.match(prop, criteria)
        has_preferences = rec is not None and rec.matched + rec.unmatched
        if rec is None or (has_preferences and rec.match_score < _NEW_MATCH_MIN_SCORE):
            continue
        key = f"agent-new-match:property:{prop.id}:user:{profile.user_id}"
        if _already_sent(db, key):
            continue
        notification_service.notify(
            db,
            profile.user_id,
            "AGENT_NEW_MATCH",
            "Có căn mới hợp với nhu cầu của bạn",
            f"Căn {_label(prop)} vừa mở bán: {_price(prop.price_vnd)}, {prop.bedrooms} PN, "
            f"{float(prop.area_m2):g} m², tầng {prop.floor}"
            + (f" — phù hợp {round(rec.match_score * 100)}% với tiêu chí bạn đã tìm." if has_preferences else ".")
            + " Nhắn Trợ lý AI để xem chi tiết hoặc đặt lịch xem.",
            payload={"property_id": prop.id, "match_score": rec.match_score},
            dedupe_key=key,
        )
        told += 1
    return told


# ---------- 3. Reminders worded for the buyer ----------


def personalize_due_reminders(db: Session, now: datetime | None = None) -> int:
    """Before delivery: reword the buyer's due reminders (the seller's stay as they are)."""
    if not agent_writer.enabled():
        return 0
    now = now or datetime.now(UTC)
    due = db.execute(
        select(Notification, Booking)
        .join(Booking, Booking.id == Notification.booking_id)
        .where(
            Notification.status == NotificationStatus.PENDING,
            Notification.scheduled_at <= now,
            Notification.event_type.like("REMINDER_%"),
            Notification.user_id == Booking.customer_id,
        )
    ).all()
    done = 0
    for note, booking in due:
        if note.payload.get("personalized"):
            continue
        prop, code = booking.property, booking.deal.code
        buyer = db.get(User, booking.customer_id)
        note.body = agent_writer.compose(
            "Nhắc người mua sắp đến giờ xem nhà",
            {
                "tên người mua": buyer.full_name if buyer else "",
                "căn": f"{prop.unit_code}, {prop.building.name}, {prop.building.project.name}",
                "giờ xem": _when(booking.start_at),
                "mã deal": code,
                "lưu ý": "Căn được giữ riêng cho bạn trong khung giờ này; muốn đổi giờ hãy nhắn Trợ lý AI.",
            },
            note.body,
            must_include=[code],
        )
        note.payload = {**note.payload, "personalized": True}
        done += 1
    db.commit()
    return done
