from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.db.models import BookingStatus, Channel


class SlotCreate(BaseModel):
    start_at: datetime
    end_at: datetime

    @model_validator(mode="after")
    def _check(self) -> "SlotCreate":
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError("start_at/end_at must include a timezone offset")
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class TimeWindow(BaseModel):
    start_at: datetime
    end_at: datetime

    @model_validator(mode="after")
    def _check(self) -> "TimeWindow":
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError("start_at/end_at must include a timezone offset")
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class ViewingTimesRequest(BaseModel):
    """When the buyer is free, e.g. Saturday 14:00-17:00 (spec §4.8)."""

    windows: list[TimeWindow] = Field(..., min_length=1, max_length=10)


class ViewingTimesOut(BaseModel):
    property_id: int
    viewing_duration_minutes: int
    # Buyer ∩ seller availability, minus times already booked/held
    common_windows: list[TimeWindow]
    # Up to N start times to offer the buyer (e.g. 14:30 / 15:00 / 15:30)
    proposals: list[TimeWindow]
    # Only when there is no common slot (AC-07): the seller's next free times outside the buyer's windows
    alternatives: list[TimeWindow] = Field(default_factory=list)


class SlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    start_at: datetime
    end_at: datetime
    is_free: bool = True


class BookingCreate(BaseModel):
    property_id: int
    slot_id: int
    note: str | None = Field(default=None, max_length=1000)


class BookingOut(BaseModel):
    id: int
    property_id: int
    property_label: str = Field(..., description="e.g. 'Vinhomes Ocean Park · S2.01 · S2.01-1208'")
    customer_id: int
    # Customer contact details are only shown to the owner once the booking is CONFIRMED (spec §4.14)
    customer_name: str | None = None
    customer_phone: str | None = None
    start_at: datetime
    end_at: datetime
    status: BookingStatus
    created_via: Channel
    customer_note: str | None
    rejection_reason: str | None
    responded_at: datetime | None
    created_at: datetime


class BookingRejectRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=1000)
