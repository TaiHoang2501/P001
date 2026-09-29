"""Owner endpoints: listings, viewing slots, booking approval (HITL)."""

from fastapi import APIRouter, Response

from src.core.deps import DbSession, OwnerActor
from src.core.errors import NotFoundError
from src.db.models import BookingStatus, Property
from src.models.booking import BookingOut, BookingRejectRequest, SlotCreate, SlotOut
from src.models.property import PropertyCreate, PropertyOut, PropertyUpdate
from src.services import availability_service, booking_service, property_service

router = APIRouter(prefix="/owner", tags=["owner"])


# ---------- Listings ----------


@router.get("/properties", response_model=list[PropertyOut])
def my_properties(actor: OwnerActor, db: DbSession) -> list[PropertyOut]:
    return property_service.list_owned(db, actor)


@router.post("/properties", response_model=PropertyOut, status_code=201)
def create_property(data: PropertyCreate, actor: OwnerActor, db: DbSession) -> PropertyOut:
    return property_service.create(db, actor, data)


@router.patch("/properties/{property_id}", response_model=PropertyOut)
def update_property(property_id: int, data: PropertyUpdate, actor: OwnerActor, db: DbSession) -> PropertyOut:
    return property_service.update(db, actor, property_id, data)


@router.post("/properties/{property_id}/submit", response_model=PropertyOut)
def submit_property(property_id: int, actor: OwnerActor, db: DbSession) -> PropertyOut:
    return property_service.submit_for_review(db, actor, property_id)


@router.post("/properties/{property_id}/sold", response_model=PropertyOut)
def mark_sold(property_id: int, actor: OwnerActor, db: DbSession) -> PropertyOut:
    return property_service.mark_sold(db, actor, property_id)


# ---------- Viewing slots ----------


@router.get("/properties/{property_id}/slots", response_model=list[SlotOut])
def property_slots(property_id: int, actor: OwnerActor, db: DbSession) -> list[SlotOut]:
    prop = db.get(Property, property_id)
    if prop is None or prop.owner_id != actor.id:
        raise NotFoundError(f"Property {property_id} not found")
    return availability_service.list_slots(db, property_id, only_free=False)


@router.post("/properties/{property_id}/slots", response_model=SlotOut, status_code=201)
def add_slot(property_id: int, data: SlotCreate, actor: OwnerActor, db: DbSession) -> SlotOut:
    return availability_service.add_slot(db, actor, property_id, data)


@router.delete("/slots/{slot_id}", status_code=204)
def delete_slot(slot_id: int, actor: OwnerActor, db: DbSession) -> Response:
    availability_service.delete_slot(db, actor, slot_id)
    return Response(status_code=204)


# ---------- Booking approval ----------


@router.get("/bookings", response_model=list[BookingOut])
def my_property_bookings(actor: OwnerActor, db: DbSession, status: BookingStatus | None = None) -> list[BookingOut]:
    return booking_service.list_for(db, actor, status)


@router.post("/bookings/{booking_id}/approve", response_model=BookingOut)
def approve_booking(booking_id: int, actor: OwnerActor, db: DbSession) -> BookingOut:
    return booking_service.approve(db, actor, booking_id)


@router.post("/bookings/{booking_id}/reject", response_model=BookingOut)
def reject_booking(booking_id: int, data: BookingRejectRequest, actor: OwnerActor, db: DbSession) -> BookingOut:
    return booking_service.reject(db, actor, booking_id, data.reason)


@router.post("/bookings/{booking_id}/complete", response_model=BookingOut)
def complete_booking(booking_id: int, actor: OwnerActor, db: DbSession) -> BookingOut:
    return booking_service.complete(db, actor, booking_id)
