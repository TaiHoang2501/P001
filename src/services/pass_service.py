"""Viewing pass: a QR code the buyer shows to the building's guard or reception on the day of the viewing.

The QR holds a link with a signed token (booking id + expiry, audience "viewing-pass"), never personal data.
Scanning it opens a public check page; the check always reads the booking's current state, so a cancelled or
moved viewing makes an old pass invalid. It shows the home and who is meeting whom, never a phone number.
A pass token cannot be used to sign in (no `sub`, its own audience), and a sign-in token is not a pass.
"""

from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from sqlalchemy.orm import Session

from src.config import get_settings
from src.core.actor import Actor
from src.core.errors import NotFoundError, StateConflictError
from src.db.models import Booking, BookingStatus
from src.models.booking import PassCheckOut, ViewingPassOut

_AUDIENCE = "viewing-pass"
# The guard can let the buyer in from a little before the viewing until a little after it ends
EARLY = timedelta(minutes=60)
LATE = timedelta(minutes=30)
# A confirmed viewing (RESCHEDULE_REQUESTED keeps its confirmed time until the seller accepts the new one)
_CONFIRMED = {BookingStatus.CONFIRMED, BookingStatus.RESCHEDULE_REQUESTED}


def _now() -> datetime:
    return datetime.now(UTC)


def issue(db: Session, actor: Actor, booking_id: int) -> ViewingPassOut:
    """The buyer's pass for a viewing the seller has confirmed."""
    booking = db.get(Booking, booking_id)
    if booking is None or booking.customer_id != actor.id:
        raise NotFoundError(f"Booking {booking_id} not found")
    if booking.status not in _CONFIRMED:
        raise StateConflictError(
            "A viewing pass exists only once the seller has confirmed the viewing",
            details={"current_status": booking.status.value},
        )
    settings = get_settings()
    payload = {
        "aud": _AUDIENCE,
        "bid": booking.id,
        "iat": _now(),
        # Lasts a day past the viewing; whether it lets the buyer in is decided at each scan
        "exp": booking.end_at + timedelta(days=1),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return ViewingPassOut(token=token, valid_from=booking.start_at - EARLY, valid_until=booking.end_at + LATE)


def check(db: Session, token: str) -> PassCheckOut:
    """What the guard sees after scanning: may this person come in now, and to which home."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm], audience=_AUDIENCE)
    except jwt.ExpiredSignatureError:
        return PassCheckOut(result="expired", message="Mã này đã quá hạn sử dụng.")
    except jwt.PyJWTError:
        return PassCheckOut(result="invalid", message="Không tìm thấy lịch hẹn ứng với mã này.")

    booking = db.get(Booking, int(payload["bid"]))
    if booking is None:
        return PassCheckOut(result="invalid", message="Không tìm thấy lịch hẹn ứng với mã này.")

    now = _now()
    result: Literal["valid", "too_early", "expired", "cancelled"]
    if booking.status not in _CONFIRMED and booking.status != BookingStatus.COMPLETED:
        result, message = "cancelled", "Lịch xem này đã bị hủy hoặc không còn hiệu lực."
    elif booking.status == BookingStatus.COMPLETED or now > booking.end_at + LATE:
        result, message = "expired", "Buổi xem đã kết thúc."
    elif now < booking.start_at - EARLY:
        result, message = "too_early", "Mã có hiệu lực từ 60 phút trước giờ xem."
    else:
        result, message = "valid", "Mời khách vào và đưa tới căn hộ để gặp chủ nhà."

    prop = booking.property
    return PassCheckOut(
        result=result,
        message=message,
        deal_code=booking.deal.code,
        unit_code=prop.unit_code,
        building=prop.building.name,
        project=prop.building.project.name,
        floor=prop.floor,
        start_at=booking.start_at,
        end_at=booking.end_at,
        buyer_name=booking.customer.full_name,
        seller_name=prop.owner.full_name,
    )
