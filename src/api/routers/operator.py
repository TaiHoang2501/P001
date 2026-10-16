"""Investor/Operator endpoints: listing moderation and booking monitoring.

Operators do not approve sellers: a seller is verified by their red book (claim + OTP to the owner's phone),
and exceptions go through ownership support cases (routers/escalations.py)."""

from fastapi import APIRouter

from src.core.deps import DbSession, OperatorActor
from src.db.models import BookingStatus, PropertyStatus
from src.models.booking import BookingOut, OperatorCancelRequest
from src.models.property import PropertyOut, RejectRequest
from src.services import booking_service, property_service

router = APIRouter(prefix="/operator", tags=["operator"])


@router.get("/properties", response_model=list[PropertyOut])
def properties_by_status(
    actor: OperatorActor, db: DbSession, status: PropertyStatus = PropertyStatus.PENDING_REVIEW
) -> list[PropertyOut]:
    return property_service.list_by_status(db, status)


@router.post("/properties/{property_id}/approve", response_model=PropertyOut)
def approve_property(property_id: int, actor: OperatorActor, db: DbSession) -> PropertyOut:
    return property_service.approve(db, actor, property_id)


@router.post("/properties/{property_id}/reject", response_model=PropertyOut)
def reject_property(property_id: int, data: RejectRequest, actor: OperatorActor, db: DbSession) -> PropertyOut:
    return property_service.reject(db, actor, property_id, data.reason)


@router.post("/properties/{property_id}/take-down", response_model=PropertyOut)
def take_down_property(property_id: int, data: RejectRequest, actor: OperatorActor, db: DbSession) -> PropertyOut:
    """Take a live listing off the market with a reason (back to the seller to fix); viewings ahead are closed."""
    return property_service.take_down(db, actor, property_id, data.reason)


@router.get("/bookings", response_model=list[BookingOut])
def all_bookings(actor: OperatorActor, db: DbSession, status: BookingStatus | None = None) -> list[BookingOut]:
    return booking_service.list_for(db, actor, status)


@router.post("/bookings/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(booking_id: int, data: OperatorCancelRequest, actor: OperatorActor, db: DbSession) -> BookingOut:
    """Manual fallback: operator cancels a stuck booking (before its viewing time); both sides are told why."""
    return booking_service.operator_cancel(db, actor, booking_id, data.reason)
