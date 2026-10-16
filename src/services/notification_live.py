"""Live notifications: a Server-Sent Events stream that pushes each new in-app notification of the signed-in user
as soon as it is sent, so the web app pops it up (a toast, like Facebook) for buyers, sellers and operators.

The stream reads the notifications table every few seconds instead of an in-process event bus: notifications are
written by many places (API requests, background jobs) on any API instance (Render, Cloud Run), and the database
is the one place they all meet. A stream ends after a few minutes (below the platforms' request timeout) and the
client opens a new one, carrying on from the last notification it received.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select

from src.config import get_settings
from src.db.models import Notification, NotificationStatus
from src.db.session import get_sessionmaker
from src.models.notification import NotificationOut

logger = logging.getLogger(__name__)

# A notification is stamped when it is created but seen only once its transaction commits: look back this far so
# one committed a moment after a later one is not skipped (already sent ids are remembered)
_LOOKBACK = timedelta(seconds=30)
_HEARTBEAT_SECONDS = 20.0


def _sent_since(user_id: int, since: datetime) -> list[NotificationOut]:
    with get_sessionmaker()() as db:
        rows = db.scalars(
            select(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.status == NotificationStatus.SENT,
                Notification.sent_at >= since,
            )
            .order_by(Notification.sent_at, Notification.id)
            .limit(50)
        )
        return [NotificationOut.model_validate(n) for n in rows]


def _event(name: str, data: object) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


async def stream(user_id: int, after: datetime | None = None) -> AsyncIterator[str]:
    """`notification` events for what is sent from now on (or after `after`, when the client reconnects)."""
    settings = get_settings()
    cursor = after or datetime.now(UTC)
    seen: dict[int, datetime] = {}
    if after is None:
        # What is already there when a new stream opens is in the bell, not popped up. Taken before `ready`, so
        # everything sent once the client sees `ready` is new (decided by id, not by comparing clocks)
        for note in await run_in_threadpool(_sent_since, user_id, cursor - _LOOKBACK):
            if note.sent_at is not None:
                seen[note.id] = note.sent_at
                cursor = max(cursor, note.sent_at)
    started = last_beat = asyncio.get_running_loop().time()
    yield _event("ready", {"poll_seconds": settings.notification_stream_poll_seconds})
    while True:
        try:
            rows = await run_in_threadpool(_sent_since, user_id, cursor - _LOOKBACK)
        except Exception:
            # A database blip: try again on the next tick rather than dropping the stream
            logger.exception("live notifications: could not read new notifications for user %s", user_id)
            rows = []
        for note in rows:
            if note.id in seen or note.sent_at is None:
                continue
            seen[note.id] = note.sent_at
            cursor = max(cursor, note.sent_at)
            # A reconnect (`after`) gets what was sent while the client was away
            if after is None or note.sent_at > after:
                yield _event("notification", note.model_dump(mode="json"))
        # Forget ids that have left the look-back window
        seen = {i: t for i, t in seen.items() if t >= cursor - _LOOKBACK}
        now = asyncio.get_running_loop().time()
        if now - started >= settings.notification_stream_max_seconds:
            # Ends cleanly before the platform's request timeout; the client reconnects with `after`
            yield _event("bye", {"after": cursor.isoformat()})
            return
        if now - last_beat >= _HEARTBEAT_SECONDS:
            # Keeps proxies from closing an idle connection
            last_beat = now
            yield ": ping\n\n"
        await asyncio.sleep(settings.notification_stream_poll_seconds)
