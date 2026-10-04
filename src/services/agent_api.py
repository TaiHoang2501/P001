"""Tool contract for the AI agent (spec §4.18).

Each function below is wrapped as a LangChain tool in src/agents/tools.py. Rules:
- `user_id` comes from the authenticated chat session, NEVER from LLM output.
- Every call goes through the same service layer as the web UI, so permissions,
  business rules, locking and audit logging are identical. Actions are logged
  with actor_type = AI_AGENT.
- Functions never raise business errors; they return a structured envelope:
      {"ok": true,  "data": {...}}
      {"ok": false, "error": {"code": "SLOT_UNAVAILABLE", "message": "...", "details": {...}}}
  The agent must only tell the buyer an action succeeded when ok is true.
- An unexpected failure (spec §6.4) stops the action, is logged, and opens a SYSTEM_FAILURE
  escalation so a human follows up; the agent only tells the buyer that support will help.
- Deliberately NOT exposed: confirm_viewing (only the Owner confirms, AC-05) and
  create/release_property_hold (holds are created/released by the booking service in the
  same transaction as the owner's decision, spec §4.13).

Error codes: NOT_FOUND, FORBIDDEN, STATE_CONFLICT, SLOT_UNAVAILABLE, SELLER_UNVERIFIED,
BUSINESS_RULE_VIOLATION, VALIDATION_ERROR, INTERNAL_ERROR.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.core.actor import Actor
from src.core.errors import AppError, BusinessRuleViolationError, NotAuthenticatedError, NotFoundError
from src.db.models import (
    ActorType,
    Booking,
    Channel,
    Deal,
    EscalationType,
    Property,
    PropertyStatus,
    User,
    UserStatus,
)
from src.db.session import get_sessionmaker
from src.models.booking import BookingCreate, RescheduleRequest, ViewingTimesRequest
from src.models.escalation import EscalationOut
from src.models.property import SearchCriteria
from src.services import (
    availability_service,
    booking_service,
    deal_service,
    escalation_service,
    property_service,
    seller_service,
)

logger = logging.getLogger(__name__)

Envelope = dict[str, Any]


def _run(fn: Callable[[Session], Any], *, tool: str, user_id: int | None = None) -> Envelope:
    db = get_sessionmaker()()
    try:
        return {"ok": True, "data": fn(db)}
    except AppError as e:
        return {"ok": False, "error": e.to_dict()}
    except ValidationError as e:
        return {
            "ok": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid tool arguments",
                "details": {"errors": e.errors(include_url=False, include_context=False)},
            },
        }
    except Exception:
        # System failure (spec §6.4): never pretend success; the agent should hand off to a human
        logger.exception("agent tool failed")
        db.rollback()
        escalated = _escalate_failure(tool, user_id)
        return {
            "ok": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "System error; a support operator has been notified",
                "details": {"escalated": escalated},
            },
        }
    finally:
        db.close()


def _escalate_failure(tool: str, user_id: int | None) -> bool:
    try:
        with get_sessionmaker()() as db:
            escalation_service.create(
                db,
                type=EscalationType.SYSTEM_FAILURE,
                summary=f"Công cụ AI '{tool}' gặp lỗi hệ thống.",
                raised_by=ActorType.SYSTEM,
                requester_id=user_id,
                context={"tool": tool},
            )
            db.commit()
        return True
    except Exception:
        logger.exception("could not open a SYSTEM_FAILURE escalation")
        return False


def _actor(db: Session, user_id: int) -> Actor:
    user = db.get(User, user_id)
    if user is None or user.status == UserStatus.SUSPENDED:
        raise NotAuthenticatedError("Chat session user not found")
    return Actor(user=user, via=Channel.AI_AGENT)


def _dump(model: Any) -> Any:
    if isinstance(model, list):
        return [_dump(m) for m in model]
    if isinstance(model, dict):
        return {k: _dump(v) for k, v in model.items()}
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model


def _available_property(db: Session, property_id: int) -> Property:
    prop = db.get(Property, property_id)
    if prop is None or prop.status != PropertyStatus.AVAILABLE:
        raise NotFoundError(f"Property {property_id} not found")
    return prop


# ---------- Read tools ----------


def list_projects() -> Envelope:
    """Vinhomes projects the buyer can choose from (codes are used in search criteria)."""
    return _run(
        lambda db: [
            {"code": p.code, "name": p.name, "city": p.city, "district": p.district}
            for p in property_service.list_projects(db)
        ],
        tool="list_projects",
    )


def search_properties(criteria: dict[str, Any]) -> Envelope:
    """Hard-filter + rank AVAILABLE properties of verified sellers (SearchCriteria fields)."""
    return _run(
        lambda db: _dump(property_service.search(db, SearchCriteria.model_validate(criteria))),
        tool="search_properties",
    )


def _default_windows() -> list[dict[str, Any]]:
    """08:00-20:00 today and the next 2 days (local time), when the buyer has not said when they are free."""
    tz = ZoneInfo(get_settings().timezone)
    today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    return [
        {"start_at": today + timedelta(days=d, hours=8), "end_at": today + timedelta(days=d, hours=20)}
        for d in range(3)
    ]


def search_with_viewing_times(criteria: dict[str, Any], buyer_windows: list[dict[str, Any]] | None = None) -> Envelope:
    """search_properties plus the best match's viewing times, so the agent needs no extra
    check_property_availability round before offering times (each round is one more LLM call)."""

    def fn(db: Session) -> Any:
        result = property_service.search(db, SearchCriteria.model_validate(criteria))
        data = _dump(result)
        data["top_viewing_times"] = None
        if result.results:
            windows = buyer_windows or _default_windows()
            request = ViewingTimesRequest.model_validate({"windows": windows})
            try:
                times = availability_service.propose_viewing_times(db, result.results[0].property.id, request)
            except AppError:
                # Times are a convenience: the search itself still succeeded
                logger.warning("no viewing times for top search result", exc_info=True)
            else:
                data["top_viewing_times"] = _dump(times)
                data["top_viewing_times"]["buyer_windows"] = _dump(request.windows)
        return data

    return _run(fn, tool="search_properties")


def get_property_detail(property_id: int) -> Envelope:
    return _run(lambda db: _dump(property_service.get_property(db, property_id)), tool="get_property_detail")


def get_seller_status(property_id: int) -> Envelope:
    """Whether the property's seller is verified. Never returns seller PII."""

    def fn(db: Session) -> Any:
        prop = _available_property(db, property_id)
        return {"property_id": prop.id, "seller_verified": seller_service.is_verified(db, prop.owner_id)}

    return _run(fn, tool="get_seller_status")


def check_seller_availability(property_id: int) -> Envelope:
    """The seller's upcoming free viewing windows (already-booked/held times removed)."""
    return _run(
        lambda db: _dump(availability_service.seller_free_windows(db, property_id)), tool="check_seller_availability"
    )


def check_property_availability(property_id: int, buyer_windows: list[dict[str, Any]]) -> Envelope:
    """Buyer's free windows ∩ seller availability -> proposed start times, or alternatives (AC-06/07)."""
    return _run(
        lambda db: _dump(
            availability_service.propose_viewing_times(
                db, property_id, ViewingTimesRequest.model_validate({"windows": buyer_windows})
            )
        ),
        tool="check_property_availability",
    )


def get_deal_status(user_id: int, deal_id: int | None = None) -> Envelope:
    """One of the buyer's deals, or all of them when deal_id is None."""

    def fn(db: Session) -> Any:
        actor = _actor(db, user_id)
        if deal_id is None:
            return _dump(deal_service.list_for(db, actor))
        return _dump(deal_service.get(db, actor, deal_id))

    return _run(fn, tool="get_deal_status", user_id=user_id)


def get_booking_status(user_id: int, booking_id: int | None = None) -> Envelope:
    """One booking, or all of the buyer's bookings when booking_id is None."""

    def fn(db: Session) -> Any:
        actor = _actor(db, user_id)
        if booking_id is None:
            return _dump(booking_service.list_for(db, actor))
        return _dump(booking_service.get(db, actor, booking_id))

    return _run(fn, tool="get_booking_status", user_id=user_id)


# ---------- Action tools ----------


def create_viewing_request(
    user_id: int,
    property_id: int,
    *,
    start_at: datetime | str | None = None,
    slot_id: int | None = None,
    buyer_windows: list[dict[str, Any]] | None = None,
    note: str | None = None,
) -> Envelope:
    """Opens/reuses the Deal and creates a REQUESTED booking. NOT confirmed until the owner approves."""

    def fn(db: Session) -> Any:
        data = BookingCreate.model_validate(
            {
                "property_id": property_id,
                "start_at": start_at,
                "slot_id": slot_id,
                "buyer_windows": buyer_windows or [],
                "note": note,
            }
        )
        _require_inside_buyer_windows(data)
        return _dump(booking_service.create_request(db, _actor(db, user_id), data))

    return _run(fn, tool="create_viewing_request", user_id=user_id)


def _require_inside_buyer_windows(data: BookingCreate) -> None:
    """The agent may pick a time for the buyer, but never outside the free time the buyer gave."""
    if not data.buyer_windows or data.start_at is None:
        return
    end_at = data.start_at + timedelta(minutes=get_settings().viewing_duration_minutes)
    if not any(w.start_at <= data.start_at and end_at <= w.end_at for w in data.buyer_windows):
        raise BusinessRuleViolationError(
            "start_at is outside the buyer's free windows; pick one of the proposals from check_property_availability",
            details={"reason": "OUTSIDE_BUYER_WINDOWS"},
        )


def cancel_viewing(user_id: int, booking_id: int) -> Envelope:
    return _run(
        lambda db: _dump(booking_service.cancel(db, _actor(db, user_id), booking_id)),
        tool="cancel_viewing",
        user_id=user_id,
    )


def reschedule_viewing(user_id: int, booking_id: int, start_at: datetime | str) -> Envelope:
    """Moves a viewing: an unanswered request just changes time (still REQUESTED); a CONFIRMED one
    stays at the old time until the owner confirms the new one."""
    return _run(
        lambda db: _dump(
            booking_service.reschedule(
                db, _actor(db, user_id), booking_id, RescheduleRequest.model_validate({"start_at": start_at})
            )
        ),
        tool="reschedule_viewing",
        user_id=user_id,
    )


_AGENT_ESCALATION_TYPES = {
    EscalationType.NO_COMMON_SLOT,
    EscalationType.SCHEDULE_CONFLICT,
    EscalationType.PROPERTY_ISSUE,
    EscalationType.OTHER,
}


def create_human_escalation(
    user_id: int,
    type: str,
    summary: str,
    *,
    property_id: int | None = None,
    booking_id: int | None = None,
    thread_id: str | None = None,
) -> Envelope:
    """Hand the buyer's case to an operator (spec §4.3 HITL), e.g. no common viewing slot (AC-07)."""

    def fn(db: Session) -> Any:
        actor = _actor(db, user_id)
        esc_type = EscalationType(type)
        if esc_type not in _AGENT_ESCALATION_TYPES:
            raise BusinessRuleViolationError(f"The assistant cannot open a {esc_type.value} escalation")
        prop_id, deal_id = property_id, None
        if booking_id is not None:
            booking = db.get(Booking, booking_id)
            if booking is None or booking.customer_id != actor.id:
                raise NotFoundError(f"Booking {booking_id} not found")
            prop_id, deal_id = booking.property_id, booking.deal_id
        elif prop_id is not None:
            # Only existence: a PROPERTY_ISSUE may be about a listing that just went off the market
            if db.get(Property, prop_id) is None:
                raise NotFoundError(f"Property {prop_id} not found")
            deal_id = db.scalar(select(Deal.id).where(Deal.buyer_id == actor.id, Deal.property_id == prop_id).limit(1))
        esc = escalation_service.create(
            db,
            type=esc_type,
            summary=summary,
            raised_by=ActorType.AI_AGENT,
            actor=actor,
            requester_id=actor.id,
            deal_id=deal_id,
            booking_id=booking_id,
            property_id=prop_id,
            context={"thread_id": thread_id} if thread_id else {},
        )
        db.commit()
        return _dump(EscalationOut.model_validate(esc))

    return _run(fn, tool="create_human_escalation", user_id=user_id)
