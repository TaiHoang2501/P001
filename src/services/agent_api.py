"""Tool contract for the AI agent (spec §4.15).

The AI member wraps each function below in a LangChain `@tool`. Rules:
- `user_id` must come from the authenticated chat session, NEVER from LLM output.
- Every call goes through the same service layer as the web UI, so permissions,
  business rules, locking and audit logging are identical. Actions are logged
  with actor_type = AI_AGENT.
- Functions never raise business errors; they return a structured envelope:
      {"ok": true,  "data": {...}}
      {"ok": false, "error": {"code": "SLOT_UNAVAILABLE", "message": "...", "details": {...}}}
  The agent must only tell the customer an action succeeded when ok is true.

Error codes: NOT_FOUND, FORBIDDEN, STATE_CONFLICT, SLOT_UNAVAILABLE,
BUSINESS_RULE_VIOLATION, VALIDATION_ERROR, INTERNAL_ERROR.
"""

import logging
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from src.core.actor import Actor
from src.core.errors import AppError, NotAuthenticatedError
from src.db.models import Channel, User, UserStatus
from src.db.session import get_sessionmaker
from src.models.booking import BookingCreate
from src.models.property import SearchCriteria
from src.services import availability_service, booking_service, property_service

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
                "details": {"errors": e.errors()},
            },
        }
    except Exception:
        # System failure (F9): never pretend success; the agent should hand off to an operator
        logger.exception("agent tool failed")
        db.rollback()
        return {
            "ok": False,
            "error": {"code": "INTERNAL_ERROR", "message": "System error, escalate to operator", "details": {}},
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


# ---------- Read tools ----------


def search_properties(criteria: dict[str, Any]) -> Envelope:
    """Hard-filter + rank AVAILABLE properties. `criteria` follows models.property.SearchCriteria."""
    return _run(lambda db: _dump(property_service.search(db, SearchCriteria.model_validate(criteria))))


def get_property_detail(property_id: int) -> Envelope:
    return _run(lambda db: _dump(property_service.get_property(db, property_id)))


def compare_properties(property_ids: list[int]) -> Envelope:
    return _run(lambda db: [_dump(property_service.get_property(db, pid)) for pid in property_ids[:5]])


def check_availability(property_id: int, slot_id: int | None = None) -> Envelope:
    return _run(lambda db: _dump(availability_service.check_availability(db, property_id, slot_id)))


def get_booking_status(user_id: int, booking_id: int | None = None) -> Envelope:
    """One booking, or all of the user's bookings when booking_id is None."""

    def fn(db: Session) -> Any:
        actor = _actor(db, user_id)
        if booking_id is None:
            return _dump(booking_service.list_for(db, actor))
        return _dump(booking_service.get(db, actor, booking_id))

    return _run(fn)


# ---------- Action tools ----------


def create_booking_request(user_id: int, property_id: int, slot_id: int, note: str | None = None) -> Envelope:
    """Creates a REQUESTED booking. It is NOT confirmed until the owner approves."""
    return _run(
        lambda db: _dump(
            booking_service.create_request(
                db, _actor(db, user_id), BookingCreate(property_id=property_id, slot_id=slot_id, note=note)
            )
        )
    )


def cancel_booking(user_id: int, booking_id: int) -> Envelope:
    return _run(lambda db: _dump(booking_service.cancel(db, _actor(db, user_id), booking_id)))
