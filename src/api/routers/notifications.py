"""In-app notifications for every signed-in user (spec §4.19)."""

from fastapi import APIRouter

from src.core.deps import AnyActor, DbSession
from src.models.notification import NotificationOut, UnreadCount
from src.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def my_notifications(actor: AnyActor, db: DbSession, unread_only: bool = False) -> list[NotificationOut]:
    return notification_service.list_for(db, actor, unread_only=unread_only)


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
