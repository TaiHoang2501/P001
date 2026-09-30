"""Red book ownership verification: a seller must prove they own a home before listing it.

The investor's records (`property_ownership_verifications`) hold each red book's holder name, code and
the owner's phone. A seller names the holder + code; if they match, an OTP goes to the phone on record,
and entering it binds the red book to the seller. A verified red book can back exactly one listing.
"""

import unicodedata
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.core.actor import Actor
from src.core.errors import (
    BusinessRuleViolationError,
    InvalidCredentialsError,
    NotFoundError,
    OwnershipNotMatchedError,
    OwnershipOtpInvalidError,
    StateConflictError,
)
from src.db.models import (
    OtpPurpose,
    OwnershipVerificationStatus,
    Property,
    PropertyOwnershipVerification,
    SellerProfile,
    SellerVerificationStatus,
)
from src.models.ownership import (
    OwnershipChallengeOut,
    OwnershipClaim,
    OwnershipOtpConfirm,
    OwnershipVerificationOut,
)
from src.services import audit, otp_service

# Seller statuses that a newly verified red book sends (back) to the operator's queue
_AWAITING_EVIDENCE = {SellerVerificationStatus.UNVERIFIED, SellerVerificationStatus.REJECTED}


def _same_name(a: str, b: str) -> bool:
    """Case- and spacing-insensitive, but accents must match (Tuấn ≠ Tuan)."""

    def norm(s: str) -> str:
        return " ".join(unicodedata.normalize("NFC", s).split()).casefold()

    return norm(a) == norm(b)


def _normalize_code(code: str) -> str:
    return code.strip().upper()


def mask_phone(phone: str) -> str:
    return f"{phone[:3]}****{phone[-3:]}" if len(phone) >= 7 else "****"


def claim(db: Session, actor: Actor, data: OwnershipClaim) -> OwnershipChallengeOut:
    """Check holder name + code against the records and send an OTP to the owner's phone on record."""
    record = db.scalar(
        select(PropertyOwnershipVerification)
        .where(PropertyOwnershipVerification.red_book_code == _normalize_code(data.red_book_code))
        .with_for_update()
    )
    if record is None or not _same_name(record.red_book_holder_name, data.red_book_holder_name):
        raise OwnershipNotMatchedError("Holder name and red book code do not match our records")

    if record.status == OwnershipVerificationStatus.VERIFIED:
        if record.user_id != actor.id:
            raise StateConflictError(
                "This red book is already verified by another account", details={"reason": "CLAIMED"}
            )
        return OwnershipChallengeOut(
            verification_id=record.id, status=record.status, masked_phone=mask_phone(record.owner_phone)
        )
    if record.status == OwnershipVerificationStatus.FAILED:
        raise StateConflictError(
            "Too many wrong codes for this red book; contact the investor to unlock it", details={"reason": "LOCKED"}
        )

    code, ttl = otp_service.request_code(db, record.owner_phone, OtpPurpose.OWNERSHIP)
    record.status = OwnershipVerificationStatus.OTP_SENT
    audit.record(db, actor, "ownership.otp_sent", "ownership_verification", record.id, after={"status": record.status})
    db.commit()
    return OwnershipChallengeOut(
        verification_id=record.id,
        status=record.status,
        masked_phone=mask_phone(record.owner_phone),
        expires_in=ttl,
        debug_code=None if get_settings().app_env == "production" else code,
    )


def confirm(db: Session, actor: Actor, verification_id: int, data: OwnershipOtpConfirm) -> OwnershipVerificationOut:
    """Check the OTP; on success the red book becomes the seller's and the seller goes to the operator's review queue."""
    record = _load(db, verification_id)
    if record.status != OwnershipVerificationStatus.OTP_SENT:
        raise StateConflictError(f"No code is pending for this red book (status {record.status.value})")

    try:
        otp = otp_service.check_code(db, record.owner_phone, data.code, OtpPurpose.OWNERSHIP)
    except InvalidCredentialsError as e:
        # check_code already committed its own attempt counter; count the miss on the red book too
        record = _load(db, verification_id)
        record.otp_attempts += 1
        max_attempts = get_settings().otp_max_attempts
        if record.otp_attempts >= max_attempts:
            record.status = OwnershipVerificationStatus.FAILED
        audit.record(
            db,
            actor,
            "ownership.otp_failed",
            "ownership_verification",
            record.id,
            after={"status": record.status, "otp_attempts": record.otp_attempts},
        )
        db.commit()
        raise OwnershipOtpInvalidError(
            "Code is invalid or expired",
            details={"attempts_left": max(0, max_attempts - record.otp_attempts), "status": record.status.value},
        ) from e

    otp_service.consume(otp)
    now = datetime.now(UTC)
    record.status = OwnershipVerificationStatus.VERIFIED
    record.user_id = actor.id
    record.verified_at = now
    audit.record(db, actor, "ownership.verified", "ownership_verification", record.id, after={"user_id": actor.id})

    # The red book is the seller's evidence; the operator still verifies the seller (spec §4.5, AC-04)
    profile = db.get(SellerProfile, actor.id, with_for_update=True)
    if profile is not None and profile.verification_status in _AWAITING_EVIDENCE:
        before = profile.verification_status
        profile.verification_status = SellerVerificationStatus.PENDING
        profile.rejection_reason = None
        audit.record(
            db,
            actor,
            "seller.submit_verification",
            "user",
            actor.id,
            before={"verification_status": before},
            after={"verification_status": profile.verification_status, "verification_id": record.id},
        )
    db.commit()
    return _out(db, record)


def list_own(db: Session, actor: Actor) -> list[OwnershipVerificationOut]:
    records = db.scalars(
        select(PropertyOwnershipVerification)
        .where(PropertyOwnershipVerification.user_id == actor.id)
        .order_by(PropertyOwnershipVerification.verified_at.desc().nulls_last())
    )
    return [_out(db, r) for r in records]


def require_usable(db: Session, actor: Actor, verification_id: int) -> None:
    """A new listing needs a red book the seller verified that no other listing uses yet."""
    record = db.get(PropertyOwnershipVerification, verification_id, with_for_update=True)
    if record is None or record.user_id != actor.id or record.status != OwnershipVerificationStatus.VERIFIED:
        raise BusinessRuleViolationError(
            "Verify ownership of this home (red book + OTP) before listing it",
            details={"missing": "OWNERSHIP_VERIFICATION"},
        )
    if _property_id(db, record.id) is not None:
        raise StateConflictError("This red book already backs another listing")


def _load(db: Session, verification_id: int) -> PropertyOwnershipVerification:
    record = db.get(PropertyOwnershipVerification, verification_id, with_for_update=True, populate_existing=True)
    if record is None:
        raise NotFoundError(f"Ownership verification {verification_id} not found")
    return record


def _property_id(db: Session, verification_id: int) -> int | None:
    return db.scalar(select(Property.id).where(Property.verification_id == verification_id))


def _out(db: Session, record: PropertyOwnershipVerification) -> OwnershipVerificationOut:
    return OwnershipVerificationOut(
        id=record.id,
        red_book_holder_name=record.red_book_holder_name,
        red_book_code=record.red_book_code,
        status=record.status,
        verified_at=record.verified_at,
        property_id=_property_id(db, record.id),
    )
