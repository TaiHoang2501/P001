from pydantic import BaseModel, Field

from src.models.booking import BookingOut, ViewingTimesOut
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
