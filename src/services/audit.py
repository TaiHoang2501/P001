from typing import Any

from sqlalchemy.orm import Session

from src.core.actor import Actor
from src.db.models import ActorType, AuditLog


def record(
    db: Session,
    actor: Actor | None,
    action: str,
    target_type: str,
    target_id: int,
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Add an audit row to the *current* transaction.

    Call this before `db.commit()` in the same unit of work as the change, so the
    log row and the change are saved together or rolled back together.
    """
    db.add(
        AuditLog(
            actor_id=actor.id if actor else None,
            actor_type=actor.actor_type if actor else ActorType.SYSTEM,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before=before,
            after=after,
            extra=extra,
        )
    )
