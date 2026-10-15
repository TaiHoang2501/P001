"""Investor/Operator endpoints: seller verification, listing moderation and booking monitoring."""

from fastapi import APIRouter, Request

from src.config import get_settings
from src.core.deps import DbSession, OperatorActor
from src.db.models import BookingStatus, PropertyStatus, SellerVerificationStatus
from src.models.booking import BookingOut
from src.models.property import PropertyOut, RejectRequest
from src.models.schemas import AssistantControlOut, AssistantToggle
from src.models.seller import SellerProfileOut, SellerReviewItem
from src.services import assistant_control, booking_service, property_service, rate_limit, seller_service

router = APIRouter(prefix="/operator", tags=["operator"])


@router.get("/sellers", response_model=list[SellerReviewItem])
def sellers_by_status(
    actor: OperatorActor, db: DbSession, status: SellerVerificationStatus = SellerVerificationStatus.PENDING
) -> list[SellerReviewItem]:
    return seller_service.list_by_status(db, status)


@router.post("/sellers/{user_id}/verify", response_model=SellerProfileOut)
def verify_seller(user_id: int, actor: OperatorActor, db: DbSession) -> SellerProfileOut:
    return seller_service.verify(db, actor, user_id)


@router.post("/sellers/{user_id}/reject", response_model=SellerProfileOut)
def reject_seller(user_id: int, data: RejectRequest, actor: OperatorActor, db: DbSession) -> SellerProfileOut:
    return seller_service.reject(db, actor, user_id, data.reason)


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


@router.get("/bookings", response_model=list[BookingOut])
def all_bookings(actor: OperatorActor, db: DbSession, status: BookingStatus | None = None) -> list[BookingOut]:
    return booking_service.list_for(db, actor, status)


@router.post("/bookings/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(booking_id: int, actor: OperatorActor, db: DbSession) -> BookingOut:
    """Manual fallback: operator cancels a stuck booking (before its viewing time)."""
    return booking_service.operator_cancel(db, actor, booking_id)


@router.get("/ai-assistant", response_model=AssistantControlOut)
def ai_assistant(actor: OperatorActor, db: DbSession) -> AssistantControlOut:
    return AssistantControlOut.model_validate(assistant_control.status(db))


@router.put("/ai-assistant", response_model=AssistantControlOut)
def set_ai_assistant(data: AssistantToggle, actor: OperatorActor, db: DbSession) -> AssistantControlOut:
    """Kill switch: turn the AI assistant off (buyers see a maintenance notice) or back on. Audited."""
    return AssistantControlOut.model_validate(assistant_control.set_enabled(db, actor, data.enabled))


@router.get("/diagnostics/client-ip")
def client_ip(request: Request, actor: OperatorActor) -> dict[str, str | int | None]:
    """After a deploy: which address guest rate limits use for this request. `client_ip` must be your own public IP;
    if it is the platform's proxy instead, adjust TRUSTED_PROXY_HOPS / CLIENT_IP_HEADER."""
    settings = get_settings()
    return {
        "client_ip": rate_limit.client_ip(request),
        "x_forwarded_for": request.headers.get("x-forwarded-for"),
        "client_ip_header": settings.client_ip_header or None,
        "trusted_proxy_hops": settings.trusted_proxy_hops,
    }
