"""The AI assistant kill switch: a developer turns the assistant off (and on) through the admin API
(src/api/routers/admin.py, scripts/ai_switch.py); operators only see whether it is on.

The state is a row in system_settings, so every API instance (Render, Cloud Run) sees the same switch at once.
While off, chat endpoints answer AI_DISABLED without calling the model, the buyer chat shows a maintenance
notice with the support hotline, and follow-up messages use their fixed templates (agent_writer).
Booking, confirmation and every other non-AI flow keep working. Each change is audited.
"""

import logging
from typing import Any

from sqlalchemy.orm import Session

from src.config import get_settings
from src.core.actor import Actor
from src.core.errors import AiDisabledError
from src.db.models import SystemSetting
from src.db.session import get_sessionmaker
from src.services import audit

logger = logging.getLogger(__name__)

KEY = "ai_assistant"


def maintenance_message() -> str:
    return f"Hệ thống AI đang bảo trì, vui lòng liên hệ Tổng đài {get_settings().support_hotline} để được hỗ trợ."


def status(db: Session) -> dict[str, Any]:
    row = db.get(SystemSetting, KEY)
    enabled = bool(row is None or row.value.get("enabled", True))
    return {
        "enabled": enabled,
        "message": None if enabled else maintenance_message(),
        "hotline": get_settings().support_hotline,
        "reason": row.value.get("reason") if row else None,
        "updated_at": row.updated_at if row else None,
        "updated_by": row.updated_by if row else None,
    }


def is_enabled() -> bool:
    """For code without a request session (chat service, background jobs). A read failure keeps the assistant on:
    the switch is for stopping the AI on purpose, not a reason to stop it when the database blips."""
    try:
        with get_sessionmaker()() as db:
            return status(db)["enabled"]
    except Exception:
        logger.exception("could not read the AI kill switch")
        return True


def ensure_enabled() -> None:
    if not is_enabled():
        raise AiDisabledError(maintenance_message(), details={"hotline": get_settings().support_hotline})


def set_enabled(db: Session, actor: Actor | None, enabled: bool, reason: str | None = None) -> dict[str, Any]:
    """Turn the assistant on or off. `actor` None: a developer through the admin API (audited as SYSTEM)."""
    row = db.get(SystemSetting, KEY, with_for_update=True)
    before = bool(row is None or row.value.get("enabled", True))
    if row is None:
        row = SystemSetting(key=KEY, value={})
        db.add(row)
    row.value = {**row.value, "enabled": enabled, "reason": reason}
    row.updated_by = actor.id if actor else None
    db.flush()
    audit.record(
        db,
        actor,
        "AI_ASSISTANT_ENABLED" if enabled else "AI_ASSISTANT_DISABLED",
        "system_setting",
        0,
        before={"enabled": before},
        after={"enabled": enabled},
        extra={"key": KEY, "reason": reason, "via": "admin_api" if actor is None else "user"},
    )
    db.commit()
    db.refresh(row)
    logger.warning("AI assistant turned %s (%s)", "on" if enabled else "off", reason or "no reason given")
    return status(db)
