from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.db.models import OwnershipVerificationStatus


class OwnershipClaim(BaseModel):
    """What the seller reads off their red book (sổ đỏ/sổ hồng)."""

    red_book_holder_name: str = Field(..., min_length=2, max_length=255, description="Tên người đứng tên trên sổ")
    red_book_code: str = Field(..., min_length=3, max_length=100, description="Số seri sổ, vd. SD-2017-0332211")


class OwnershipChallengeOut(BaseModel):
    """Result of a claim: an OTP was sent to the phone on record (or the red book is already the caller's)."""

    verification_id: int
    status: OwnershipVerificationStatus
    # e.g. "090****777": the seller recognises the phone without the API revealing it
    masked_phone: str
    expires_in: int | None = None
    # Only filled outside production, until an SMS/Zalo provider exists
    debug_code: str | None = None


class OwnershipOtpConfirm(BaseModel):
    code: str = Field(..., pattern=r"^\d{6}$")


class OwnershipVerificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    red_book_holder_name: str
    red_book_code: str
    status: OwnershipVerificationStatus
    verified_at: datetime | None
    # Listing backed by this red book, if any (one red book = one listing)
    property_id: int | None = None
