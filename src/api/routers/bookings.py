"""Customer booking endpoints."""

from fastapi import APIRouter

from src.core.deps import AnyActor, CustomerActor, DbSession
from src.models.booking import (
    ActivityOut,
    BookingCreate,
    BookingOut,
    PassCheckOut,
    RescheduleRequest,
    ViewingDispute,
    ViewingFeedback,
    ViewingPassOut,
)
from src.services import booking_service, pass_service, viewing_outcome_service

router = APIRouter(prefix="/bookings", tags=["bookings"])
# Public: opened by the guard's phone camera from the buyer's QR code
passes = APIRouter(prefix="/passes", tags=["viewing pass"])


@router.post("", response_model=BookingOut, status_code=201)
def request_viewing(data: BookingCreate, actor: CustomerActor, db: DbSession) -> BookingOut:
    return booking_service.create_request(db, actor, data)


@router.get("", response_model=list[BookingOut])
def my_bookings(actor: CustomerActor, db: DbSession) -> list[BookingOut]:
    return booking_service.list_for(db, actor)


@router.get("/activity", response_model=list[ActivityOut])
def my_activity(actor: CustomerActor, db: DbSession) -> list[ActivityOut]:
    """Important events of the buyer's viewings: requests, the owner's answers, time changes, cancellations."""
    return booking_service.activity_for(db, actor)


@router.get("/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: int, actor: AnyActor, db: DbSession) -> BookingOut:
    return booking_service.get(db, actor, booking_id)


@router.post("/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(booking_id: int, actor: CustomerActor, db: DbSession) -> BookingOut:
    return booking_service.cancel(db, actor, booking_id)


@router.post("/{booking_id}/reschedule", response_model=BookingOut)
def reschedule_booking(booking_id: int, data: RescheduleRequest, actor: CustomerActor, db: DbSession) -> BookingOut:
    """Ask the owner to move a confirmed viewing; it stays at the old time until the owner confirms."""
    return booking_service.reschedule(db, actor, booking_id, data)


@router.post("/{booking_id}/feedback", response_model=BookingOut)
def viewing_feedback(booking_id: int, data: ViewingFeedback, actor: CustomerActor, db: DbSession) -> BookingOut:
    """After a viewing that took place: interested (the owner is told) or not suitable (the deal closes)."""
    return viewing_outcome_service.feedback(db, actor, booking_id, data.interest, data.note.strip())


@router.post("/{booking_id}/dispute", response_model=BookingOut)
def viewing_dispute(booking_id: int, data: ViewingDispute, actor: CustomerActor, db: DbSession) -> BookingOut:
    """The buyer disagrees with the recorded outcome; the operator checks with both sides."""
    return viewing_outcome_service.dispute(db, actor, booking_id, data.claim, data.note.strip())


@router.get("/{booking_id}/pass", response_model=ViewingPassOut)
def viewing_pass(booking_id: int, actor: CustomerActor, db: DbSession) -> ViewingPassOut:
    """The entry QR for a viewing the seller has confirmed (shown to the building's guard or reception)."""
    return pass_service.issue(db, actor, booking_id)


@passes.get("/{token}", response_model=PassCheckOut)
def check_pass(token: str, db: DbSession) -> PassCheckOut:
    """Scanned at the building: valid now or not, which home, who meets whom. No phone numbers."""
    return pass_service.check(db, token)
