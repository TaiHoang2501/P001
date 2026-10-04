from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.db.models import SellerSource, SellerVerificationStatus


class SellerVerificationSubmit(BaseModel):
    # S3 key of the uploaded ID / ownership document (upload itself goes through presigned URLs)
    id_document_s3_key: str = Field(..., min_length=3, max_length=512)


class SellerProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    verification_status: SellerVerificationStatus
    source: SellerSource
    id_document_s3_key: str | None
    verified_at: datetime | None
    rejection_reason: str | None


class SellerReviewItem(SellerProfileOut):
    """What an operator sees in the verification queue."""

    full_name: str
    phone: str
    email: str | None
    # Red books this seller proved with an OTP to the owner's phone on record
    red_book_codes: list[str] = []
