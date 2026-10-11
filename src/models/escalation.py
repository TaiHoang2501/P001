from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.db.models import ActorType, EscalationStatus, EscalationType, MessageRole


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
    # The staff member handling it (by name, so colleagues with their own accounts do not call the same person)
    assigned_to_name: str | None = None
    resolution: str | None
    resolved_at: datetime | None
    created_at: datetime


class ResolveRequest(BaseModel):
    resolution: str = Field(..., min_length=10, max_length=2000, description="What was done / what the people are told")
    # Who is told the outcome; None = the default for the kind of case (see CaseContext.notify_*_default)
    notify_buyer: bool | None = None
    notify_seller: bool | None = None


class CaseMessage(BaseModel):
    """One message of the buyer's chat with the assistant, as the buyer saw it (no technical details)."""

    role: MessageRole
    content: str
    created_at: datetime


class CaseContext(BaseModel):
    """What an operator needs to handle a case, in plain words: who, which home, which viewing, and (when the
    assistant raised it) the end of the buyer's chat with the assistant."""

    buyer_name: str | None = None
    buyer_phone: str | None = None
    seller_name: str | None = None
    seller_phone: str | None = None
    property_label: str | None = None
    deal_code: str | None = None
    viewing_time: datetime | None = None
    viewing_status: str | None = None
    messages: list[CaseMessage] = Field(default_factory=list)
    # Who is told the outcome when the case is closed, unless the operator changes it
    notify_buyer_default: bool = False
    notify_seller_default: bool = False
    # Older messages of that chat that are not shown
    earlier_messages: int = 0
