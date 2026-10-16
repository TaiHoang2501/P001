"""In-app notifications for every signed-in user (spec §4.19)."""

from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from src.core.deps import AnyActor, DbSession
from src.models.notification import NotificationOut, UnreadCount
from src.services import notification_live, notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def my_notifications(actor: AnyActor, db: DbSession, unread_only: bool = False) -> list[NotificationOut]:
    return notification_service.list_for(db, actor, unread_only=unread_only)


@router.get("/stream", response_class=StreamingResponse)
def live_notifications(actor: AnyActor, after: datetime | None = None) -> StreamingResponse:
    """Server-Sent Events: `notification` {NotificationOut} as soon as a new one is sent to you (the web app shows
    it as a pop-up), `ready` once connected, and `bye` {after} when the stream ends after a few minutes: reconnect
    with `?after=` to carry on without missing any."""
    # No proxy buffering (Render/nginx), so each notification reaches the browser at once
    return StreamingResponse(
        notification_live.stream(actor.id, after),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/unread-count", response_model=UnreadCount)
def unread_count(actor: AnyActor, db: DbSession) -> UnreadCount:
    return UnreadCount(unread=notification_service.unread_count(db, actor))


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: int, actor: AnyActor, db: DbSession) -> NotificationOut:
    return notification_service.mark_read(db, actor, notification_id)


@router.post("/read-all", response_model=UnreadCount)
def mark_all_read(actor: AnyActor, db: DbSession) -> UnreadCount:
    notification_service.mark_all_read(db, actor)
    return UnreadCount(unread=0)
