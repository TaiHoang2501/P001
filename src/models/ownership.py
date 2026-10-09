from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.db.models import Direction, OwnershipVerificationStatus, PropertyType, SellerVerificationStatus


class RedBookUnit(BaseModel):
    """The investor's record of the home behind a red book: a listing takes these facts as they are."""

    project_code: str
    project_name: str
    building_id: int
    building_name: str
    unit_code: str
    property_type: PropertyType
    area_m2: Decimal
    bedrooms: int
    bathrooms: int
    floor: int
    direction: Direction


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
    # The home on this red book (investor's data); None when the record has no unit details
    unit: RedBookUnit | None = None


# ---------- Help from the investor when a red book cannot be verified automatically ----------

SupportReason = Literal[
    "NO_OTP", "LOCKED", "MISMATCH", "PROXY", "CO_OWNER", "INHERITANCE", "NO_RED_BOOK", "CLAIMED_BY_OTHER", "OTHER"
]

SUPPORT_REASON_LABEL: dict[str, str] = {
    "NO_OTP": "Không nhận được mã OTP (chủ sở hữu đã đổi số điện thoại)",
    "LOCKED": "Sổ đỏ / sổ hồng bị khóa do nhập sai OTP",
    "MISMATCH": "Thông tin đúng nhưng hệ thống báo không khớp",
    "PROXY": "Bán thay chủ sở hữu (có giấy ủy quyền)",
    "CO_OWNER": "Sổ đồng sở hữu",
    "INHERITANCE": "Thừa kế, chưa sang tên",
    "NO_RED_BOOK": "Căn chưa có sổ đỏ / sổ hồng (chỉ có hợp đồng mua bán)",
    "CLAIMED_BY_OTHER": "Sổ đỏ / sổ hồng đã bị một tài khoản khác xác thực",
    "OTHER": "Lý do khác",
}


class OwnershipSupportCreate(BaseModel):
    reason: SupportReason
    red_book_holder_name: str = Field(..., min_length=2, max_length=255)
    # For a home without a red book yet: the sale contract number
    red_book_code: str = Field(..., min_length=3, max_length=100)
    note: str = Field(default="", max_length=2000)
    # Keys of documents uploaded with POST /owner/media (private): ID card, power of attorney, contract...
    documents: list[str] = Field(default_factory=list, max_length=8)


class SupportSeller(BaseModel):
    id: int
    full_name: str
    phone: str | None
    verification_status: SellerVerificationStatus | None


class RedBookState(BaseModel):
    """The red book as it stands now, for the operator (full phone included)."""

    id: int
    red_book_code: str
    red_book_holder_name: str
    owner_phone: str
    masked_phone: str
    status: OwnershipVerificationStatus
    otp_attempts: int
    verified_by_id: int | None
    verified_by_name: str | None
    property_id: int | None
    property_label: str | None


class OwnershipCaseOut(BaseModel):
    escalation_id: int
    seller: SupportSeller | None
    # None: the code is not in the investor's records (e.g. no red book yet)
    red_book: RedBookState | None


class UnlockRequest(BaseModel):
    # The owner's new phone, when the old one no longer works (the OTP goes there)
    owner_phone: str | None = Field(default=None, pattern=r"^0\d{9,10}$")


class OperatorNote(BaseModel):
    note: str = Field(..., min_length=3, max_length=1000)
