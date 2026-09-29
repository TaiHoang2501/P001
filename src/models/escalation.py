from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.db.models import ActorType, EscalationStatus, EscalationType


class EscalationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: EscalationType
    status: EscalationStatus
    raised_by: ActorType
    requester_id: int | None
    deal_id: int | None
    booking_id: int | None
    property_id: int | None
    summary: str
    context: dict[str, Any]
    assigned_to: int | None
    resolution: str | None
    resolved_at: datetime | None
    created_at: datetime


class ResolveRequest(BaseModel):
    resolution: str = Field(..., min_length=3, max_length=2000, description="What was done / told to the buyer")
