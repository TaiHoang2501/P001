from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    title: str
    body: str
    payload: dict[str, Any]
    deal_id: int | None
    booking_id: int | None
    sent_at: datetime | None
    read_at: datetime | None


class UnreadCount(BaseModel):
    unread: int
