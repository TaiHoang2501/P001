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
- Deliberately NOT exposed: confirm_viewing (only the Owner confirms, AC-05) and
  create/release_property_hold (holds are created/released by the booking service in the
  same transaction as the owner's decision, spec §4.13).

Error codes: NOT_FOUND, FORBIDDEN, STATE_CONFLICT, SLOT_UNAVAILABLE, SELLER_UNVERIFIED,
BUSINESS_RULE_VIOLATION, VALIDATION_ERROR, INTERNAL_ERROR.
"""

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from src.core.actor import Actor
from src.core.errors import AppError, NotAuthenticatedError, NotFoundError
from src.db.models import Channel, Property, PropertyStatus, User, UserStatus
from src.db.session import get_sessionmaker
from src.models.booking import BookingCreate, RescheduleRequest, ViewingTimesRequest
from src.models.property import SearchCriteria
from src.services import availability_service, booking_service, deal_service, property_service, seller_service

logger = logging.getLogger(__name__)

Envelope = dict[str, Any]


def _run(fn: Callable[[Session], Any]) -> Envelope:
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
        return {
            "ok": False,
            "error": {"code": "INTERNAL_ERROR", "message": "System error, escalate to an operator", "details": {}},
        }
    finally:
        db.close()


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
        ]
    )


def search_properties(criteria: dict[str, Any]) -> Envelope:
    """Hard-filter + rank AVAILABLE properties of verified sellers (SearchCriteria fields)."""
    return _run(lambda db: _dump(property_service.search(db, SearchCriteria.model_validate(criteria))))


def get_property_detail(property_id: int) -> Envelope:
    return _run(lambda db: _dump(property_service.get_property(db, property_id)))


def get_seller_status(property_id: int) -> Envelope:
    """Whether the property's seller is verified. Never returns seller PII."""

    def fn(db: Session) -> Any:
        prop = _available_property(db, property_id)
        return {"property_id": prop.id, "seller_verified": seller_service.is_verified(db, prop.owner_id)}

    return _run(fn)


def check_seller_availability(property_id: int) -> Envelope:
    """The seller's upcoming free viewing windows (already-booked/held times removed)."""
    return _run(lambda db: _dump(availability_service.seller_free_windows(db, property_id)))


def check_property_availability(property_id: int, buyer_windows: list[dict[str, Any]]) -> Envelope:
    """Buyer's free windows ∩ seller availability -> proposed start times, or alternatives (AC-06/07)."""
    return _run(
        lambda db: _dump(
            availability_service.propose_viewing_times(
                db, property_id, ViewingTimesRequest.model_validate({"windows": buyer_windows})
            )
        )
    )


def get_deal_status(user_id: int, deal_id: int | None = None) -> Envelope:
    """One of the buyer's deals, or all of them when deal_id is None."""

    def fn(db: Session) -> Any:
        actor = _actor(db, user_id)
        if deal_id is None:
            return _dump(deal_service.list_for(db, actor))
        return _dump(deal_service.get(db, actor, deal_id))

    return _run(fn)


def get_booking_status(user_id: int, booking_id: int | None = None) -> Envelope:
    """One booking, or all of the buyer's bookings when booking_id is None."""

    def fn(db: Session) -> Any:
        actor = _actor(db, user_id)
        if booking_id is None:
            return _dump(booking_service.list_for(db, actor))
        return _dump(booking_service.get(db, actor, booking_id))

    return _run(fn)


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
        return _dump(booking_service.create_request(db, _actor(db, user_id), data))

    return _run(fn)


def cancel_viewing(user_id: int, booking_id: int) -> Envelope:
    return _run(lambda db: _dump(booking_service.cancel(db, _actor(db, user_id), booking_id)))


def reschedule_viewing(user_id: int, booking_id: int, start_at: datetime | str) -> Envelope:
    """Asks the owner to move a CONFIRMED viewing; it stays at the old time until the owner confirms."""
    return _run(
        lambda db: _dump(
            booking_service.reschedule(
                db, _actor(db, user_id), booking_id, RescheduleRequest.model_validate({"start_at": start_at})
            )
        )
    )
