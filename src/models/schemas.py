from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.db.models import ConversationStatus, MessageRole
from src.models.booking import BookingOut, TimeWindow, ViewingTimesOut
from src.models.property import Recommendation


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000, description="Tin nhắn từ người mua")
    conversation_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="Client-generated id; a new id starts a new conversation",
    )


class PendingViewingRequest(BaseModel):
    """A viewing request the agent tried to send for a guest; the client sends it once the guest has an account."""

    property_id: int
    start_at: datetime
    buyer_windows: list[TimeWindow] = Field(default_factory=list)
    note: str | None = None


class ChatResponse(BaseModel):
    reply: str = Field(..., description="Agent reply to show the buyer")
    conversation_id: str
    recommendations: list[Recommendation] = Field(
        default_factory=list, description="Properties the agent recommended in this turn (latest search)"
    )
    viewing_times: ViewingTimesOut | None = Field(
        default=None, description="Latest proposed viewing times in this turn, for clickable choices"
    )
    bookings: list[BookingOut] = Field(
        default_factory=list, description="Viewing requests the agent created, cancelled or rescheduled in this turn"
    )
    needs_account: bool = Field(
        default=False, description="Guest chat only: the buyer asked for something that needs an account (booking)"
    )
    trace_id: str | None = Field(default=None, description="Developer trace of this turn (table ai_turns)")
    pending_viewing: PendingViewingRequest | None = Field(
        default=None, description="Guest chat only: the viewing request to send after the guest signs up"
    )


class GuestClaimResponse(BaseModel):
    # False when there was no guest conversation, or the account already had this conversation
    claimed: bool


class ConversationOut(BaseModel):
    conversation_id: str
    status: ConversationStatus
    # Latest search criteria the agent used (budget, bedrooms, project...)
    extracted_criteria: dict[str, Any]
    created_at: datetime
    last_message_at: datetime


class ChatMessageOut(BaseModel):
    role: MessageRole
    content: str
    created_at: datetime


class AssistantStatusOut(BaseModel):
    """Whether the AI assistant answers (operator kill switch); `message` is shown in the chat while it is off."""

    enabled: bool
    message: str | None = None
    hotline: str


class AssistantControlOut(AssistantStatusOut):
    reason: str | None = None
    updated_at: datetime | None = None
    updated_by: int | None = None


class AssistantToggle(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    enabled: bool
    # Why (kept in the audit log), e.g. "model provider down"; required to turn the assistant off
    reason: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _reason_to_turn_off(self) -> "AssistantToggle":
        if not self.enabled and not (self.reason and len(self.reason) >= 5):
            raise ValueError("say why the assistant is turned off (reason, at least 5 characters)")
        return self
