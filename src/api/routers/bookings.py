"""Customer booking endpoints."""

from fastapi import APIRouter

from src.core.deps import AnyActor, CustomerActor, DbSession
from src.models.booking import BookingCreate, BookingOut
from src.services import booking_service

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("", response_model=BookingOut, status_code=201)
def request_viewing(data: BookingCreate, actor: CustomerActor, db: DbSession) -> BookingOut:
    return booking_service.create_request(db, actor, data)


@router.get("", response_model=list[BookingOut])
def my_bookings(actor: CustomerActor, db: DbSession) -> list[BookingOut]:
    return booking_service.list_for(db, actor)


@router.get("/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: int, actor: AnyActor, db: DbSession) -> BookingOut:
    return booking_service.get(db, actor, booking_id)


@router.post("/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(booking_id: int, actor: CustomerActor, db: DbSession) -> BookingOut:
    return booking_service.cancel(db, actor, booking_id)
