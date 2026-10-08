from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.db.models import BookingStatus, Channel, DealStatus, HoldStatus


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
    """Viewing request: pick a seller slot (`slot_id`) or a proposed start time (`start_at`)."""

    property_id: int
    slot_id: int | None = None
    start_at: datetime | None = Field(default=None, description="From POST /properties/{id}/viewing-times")
    # When the buyer said they are free; kept on the deal for rescheduling (spec §4.8)
    buyer_windows: list[TimeWindow] = Field(default_factory=list, max_length=10)
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _one_time_source(self) -> "BookingCreate":
        if (self.slot_id is None) == (self.start_at is None):
            raise ValueError("Give exactly one of slot_id or start_at")
        if self.start_at is not None and self.start_at.tzinfo is None:
            raise ValueError("start_at must include a timezone offset")
        return self


class BookingOut(BaseModel):
    id: int
    deal_id: int
    deal_code: str = Field(..., description="e.g. VH-2026-00128")
    property_id: int
    property_label: str = Field(..., description="e.g. 'Vinhomes Ocean Park · S2.01 · S2.01-1208'")
    customer_id: int
    # Privacy level 1 (spec §4.7, AC-03): the seller only sees a buyer reference and budget range.
    # Name/phone are shown to the seller only once the deal reaches disclosure level 3.
    buyer_ref: str
    buyer_budget_min_vnd: int | None = None
    buyer_budget_max_vnd: int | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    start_at: datetime
    end_at: datetime
    status: BookingStatus
    # Viewing hold (spec §4.13): ACTIVE while the property is locked for this viewing
    hold_status: HoldStatus | None = None
    # New time asked for while RESCHEDULE_REQUESTED
    proposed_start_at: datetime | None = None
    proposed_end_at: datetime | None = None
    created_via: Channel
    customer_note: str | None
    rejection_reason: str | None
    responded_at: datetime | None
    created_at: datetime
    # Where the deal stands (VIEWED: the buyer has not said yet how they found the home)
    deal_status: DealStatus | None = None


ActivityKind = Literal[
    "REQUESTED",
    "TIME_CHANGED",
    "RESCHEDULE_REQUESTED",
    "CONFIRMED",
    "REJECTED",
    "RESCHEDULE_APPROVED",
    "RESCHEDULE_DECLINED",
    "CANCELLED",
    "COMPLETED",
    # The owner confirmed another buyer at an overlapping time, so this request was closed
    "SUPERSEDED",
    # After the viewing time: the buyer did not come / the owner was not there / nobody recorded it
    "NO_SHOW",
    "OWNER_ABSENT",
    "UNREPORTED",
    # The buyer's answer after the viewing, and a disagreement sent to the operator
    "INTERESTED",
    "NOT_SUITABLE",
    "DISPUTED",
]


class ActivityOut(BaseModel):
    """One important event in a buyer's viewing history (kept server-side, so a new chat does not lose it)."""

    id: int
    at: datetime
    kind: ActivityKind
    # Who did it: the buyer themselves, the home's owner, or BookingBot (operator / system)
    by: Literal["BUYER", "OWNER", "BOOKINGBOT"]
    booking_id: int
    property_id: int
    property_label: str
    deal_code: str
    # The viewing time this event is about (the new time for a time change); None when not recorded
    start_at: datetime | None = None
    reason: str | None = None
    # Where the viewing stands now
    booking_status: BookingStatus
    booking_start_at: datetime
    booking_end_at: datetime


class ViewingFeedback(BaseModel):
    interest: Literal["INTERESTED", "NOT_SUITABLE"]
    note: str = Field(default="", max_length=1000)


class ViewingDispute(BaseModel):
    # I_CAME: recorded as a no-show but the buyer came; OWNER_ABSENT: the owner was not there
    claim: Literal["I_CAME", "OWNER_ABSENT"]
    note: str = Field(default="", max_length=1000)


class ViewingOutcome(BaseModel):
    """What the operator found after calling both sides."""

    outcome: Literal["VIEWED", "BUYER_NO_SHOW", "OWNER_ABSENT"]
    note: str = Field(..., min_length=3, max_length=1000)


class RescheduleRequest(BaseModel):
    start_at: datetime = Field(..., description="New start time, e.g. from POST /properties/{id}/viewing-times")

    @model_validator(mode="after")
    def _check(self) -> "RescheduleRequest":
        if self.start_at.tzinfo is None:
            raise ValueError("start_at must include a timezone offset")
        return self


class BookingRejectRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=1000)


class ViewingPassOut(BaseModel):
    """The buyer's entry pass: the QR links to /pass/{token}."""

    token: str
    valid_from: datetime = Field(description="The guard can let the buyer in from this time...")
    valid_until: datetime = Field(description="...until this time")


class PassCheckOut(BaseModel):
    """What the guard / reception sees after scanning a pass (no phone numbers)."""

    result: Literal["valid", "too_early", "expired", "cancelled", "invalid"]
    message: str
    deal_code: str | None = None
    unit_code: str | None = None
    building: str | None = None
    project: str | None = None
    floor: int | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    buyer_name: str | None = None
    seller_name: str | None = None
