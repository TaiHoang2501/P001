"""Red book ownership verification: a seller must prove they own a home before listing it.

The investor's records (`property_ownership_verifications`) hold each red book's holder name, code and
the owner's phone. A seller names the holder + code; if they match and the seller signed in with that same
phone (the owner themselves), an OTP goes to the phone on record, and entering it binds the red book to the
seller. Anyone else (selling for the owner, co-owners, a changed phone...) goes through a support request that
the investor checks by hand. A verified red book can back exactly one listing.
"""

import re
import unicodedata
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.core.actor import Actor
from src.core.errors import (
    BusinessRuleViolationError,
    InvalidCredentialsError,
    NotFoundError,
    OwnershipNotMatchedError,
    OwnershipOtpInvalidError,
    RateLimitedError,
    StateConflictError,
)
from src.db.models import (
    AuditLog,
    Building,
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
    RedBookUnit,
)
from src.services import audit, otp_service

# Seller statuses that a newly verified red book sends (back) to the operator's queue


def _same_name(a: str, b: str) -> bool:
    """Case- and spacing-insensitive, but accents must match (Tuấn ≠ Tuan)."""

    def norm(s: str) -> str:
        return " ".join(unicodedata.normalize("NFC", s).split()).casefold()

    return norm(a) == norm(b)


def _digits(phone: str | None) -> str:
    """Phone digits only, with +84 written as 0 ("+84 912 345 678" -> "0912345678")."""
    d = re.sub(r"\D", "", phone or "")
    return "0" + d[2:] if d.startswith("84") and len(d) > 10 else d


def _claim_failed(db: Session, actor: Actor, code: str, reason: str) -> None:
    """Recorded (and committed) before the error is raised, so repeated guesses can be counted."""
    audit.record(db, actor, "ownership.claim_failed", "user", actor.id, after={"red_book_code": code, "reason": reason})
    db.commit()


def _require_not_guessing(db: Session, actor: Actor) -> None:
    limit = get_settings().ownership_claim_failures_per_hour
    since = datetime.now(UTC) - timedelta(hours=1)
    failures = db.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.actor_id == actor.id, AuditLog.action == "ownership.claim_failed", AuditLog.created_at > since)
    )
    if failures >= limit:
        raise RateLimitedError(
            "Too many red books that did not match; try again in an hour", details={"limit_per_hour": limit}
        )


def _normalize_code(code: str) -> str:
    return code.strip().upper()


def mask_phone(phone: str) -> str:
    return f"{phone[:3]}****{phone[-3:]}" if len(phone) >= 7 else "****"


def claim(db: Session, actor: Actor, data: OwnershipClaim) -> OwnershipChallengeOut:
    """Check holder name + code against the records and send an OTP to the owner's phone on record.

    Only the owner signed in with the phone on record verifies on their own; the OTP alone is not enough
    (an owner could be talked into reading the code out to someone else).
    """
    _require_not_guessing(db, actor)
    book_code = _normalize_code(data.red_book_code)
    record = db.scalar(
        select(PropertyOwnershipVerification)
        .where(PropertyOwnershipVerification.red_book_code == book_code)
        .with_for_update()
    )
    if record is None or not _same_name(record.red_book_holder_name, data.red_book_holder_name):
        _claim_failed(db, actor, book_code, "NOT_MATCHED")
        raise OwnershipNotMatchedError("Holder name and red book code do not match our records")

    if record.status == OwnershipVerificationStatus.VERIFIED and record.user_id == actor.id:
        # Already this seller's red book
        return OwnershipChallengeOut(
            verification_id=record.id, status=record.status, masked_phone=mask_phone(record.owner_phone)
        )
    # Before anything else about the red book: someone who is not its owner (signed in with another phone) gets
    # one and the same answer, with no part of the owner's phone and nothing on the red book's state
    # (verified by someone, locked...). The investor checks a sale for someone else by hand.
    if _digits(actor.user.phone) != _digits(record.owner_phone):
        _claim_failed(db, actor, book_code, "NOT_OWNER_PHONE")
        raise BusinessRuleViolationError(
            "This red book is registered to another phone; send a support request to sell for its owner",
            details={"reason": "NOT_OWNER_PHONE"},
        )
    if record.status == OwnershipVerificationStatus.VERIFIED:
        # The owner, but another account of theirs (or a wrong one) verified it: a case for the investor
        raise StateConflictError("This red book is already verified by another account", details={"reason": "CLAIMED"})
    if record.status == OwnershipVerificationStatus.FAILED:
        raise StateConflictError(
            "Too many wrong codes for this red book; contact the investor to unlock it", details={"reason": "LOCKED"}
        )
    if record.unit_code is not None:
        # One home, one valid red book: another verified red book for the same unit is a case for the investor
        other = db.scalar(
            select(PropertyOwnershipVerification.id).where(
                PropertyOwnershipVerification.building_id == record.building_id,
                PropertyOwnershipVerification.unit_code == record.unit_code,
                PropertyOwnershipVerification.status == OwnershipVerificationStatus.VERIFIED,
                PropertyOwnershipVerification.id != record.id,
            )
        )
        if other is not None:
            raise StateConflictError(
                "Another verified red book exists for this home; contact the investor",
                details={"reason": "UNIT_CLAIMED", "unit_code": record.unit_code},
            )

    firebase = otp_service.uses_firebase(record.owner_phone)
    if firebase:
        # The browser has Firebase send the SMS to the phone on record (the seller's own, checked above)
        code, ttl = None, get_settings().otp_ttl_seconds
    else:
        code, ttl = otp_service.request_code(db, record.owner_phone, OtpPurpose.OWNERSHIP)
    record.status = OwnershipVerificationStatus.OTP_SENT
    audit.record(db, actor, "ownership.otp_sent", "ownership_verification", record.id, after={"status": record.status})
    db.commit()
    return OwnershipChallengeOut(
        verification_id=record.id,
        status=record.status,
        masked_phone=mask_phone(record.owner_phone),
        expires_in=ttl,
        provider="firebase" if firebase else "local",
        firebase=otp_service.firebase_config() if firebase else None,
        debug_code=code if code is not None and otp_service.code_visible(record.owner_phone) else None,
        demo=otp_service.is_demo(record.owner_phone),
    )


def confirm(db: Session, actor: Actor, verification_id: int, data: OwnershipOtpConfirm) -> OwnershipVerificationOut:
    """Check the OTP; on success the red book becomes the seller's and the seller goes to the operator's review queue."""
    record = _load(db, verification_id)
    # Same rule as the claim: only the owner, signed in with the phone on the red book, may finish it. Checked
    # before the code, so nobody else can take the red book with a code they got hold of, nor burn its attempts
    if _digits(actor.user.phone) != _digits(record.owner_phone):
        raise BusinessRuleViolationError(
            "This red book is registered to another phone; send a support request to sell for its owner",
            details={"reason": "NOT_OWNER_PHONE"},
        )
    if record.status != OwnershipVerificationStatus.OTP_SENT:
        raise StateConflictError(f"No code is pending for this red book (status {record.status.value})")

    try:
        otp = otp_service.check_proof(
            db,
            record.owner_phone,
            code=data.code,
            firebase_id_token=data.firebase_id_token,
            purpose=OtpPurpose.OWNERSHIP,
        )
    except InvalidCredentialsError as e:
        # A local code's own attempt counter is already committed; count the miss on the red book too
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

    # The red book (holder + code in the investor's records, then the owner's OTP) verifies the seller too:
    # no separate review by the operator (spec §4.5, AC-04)
    profile = db.get(SellerProfile, actor.id, with_for_update=True)
    if profile is not None and profile.verification_status != SellerVerificationStatus.VERIFIED:
        before = profile.verification_status
        profile.verification_status = SellerVerificationStatus.VERIFIED
        profile.verified_at = now
        profile.rejection_reason = None
        audit.record(
            db,
            actor,
            "seller.verified_by_red_book",
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


def require_usable(db: Session, actor: Actor, verification_id: int) -> PropertyOwnershipVerification:
    """A new listing needs a red book the seller verified that no other listing uses yet."""
    record = db.get(PropertyOwnershipVerification, verification_id, with_for_update=True)
    if record is None or record.user_id != actor.id or record.status != OwnershipVerificationStatus.VERIFIED:
        raise BusinessRuleViolationError(
            "Verify ownership of this home (red book + OTP) before listing it",
            details={"missing": "OWNERSHIP_VERIFICATION"},
        )
    if _property_id(db, record.id) is not None:
        raise StateConflictError("This red book already backs another listing")
    return record


def _load(db: Session, verification_id: int) -> PropertyOwnershipVerification:
    record = db.get(PropertyOwnershipVerification, verification_id, with_for_update=True, populate_existing=True)
    if record is None:
        raise NotFoundError(f"Ownership verification {verification_id} not found")
    return record


def _property_id(db: Session, verification_id: int) -> int | None:
    return db.scalar(select(Property.id).where(Property.verification_id == verification_id))


def unit_of(db: Session, record: PropertyOwnershipVerification) -> RedBookUnit | None:
    """The home on the red book, when the investor's record has all of it."""
    facts = (record.building_id, record.unit_code, record.property_type, record.area_m2)
    rooms = (record.bedrooms, record.bathrooms, record.floor, record.direction)
    if any(v is None for v in (*facts, *rooms)):
        return None
    building = db.get(Building, record.building_id)
    return RedBookUnit(
        project_code=building.project.code,
        project_name=building.project.name,
        building_id=building.id,
        building_name=building.name,
        unit_code=record.unit_code,
        property_type=record.property_type,
        area_m2=record.area_m2,
        bedrooms=record.bedrooms,
        bathrooms=record.bathrooms,
        floor=record.floor,
        direction=record.direction,
    )


def _out(db: Session, record: PropertyOwnershipVerification) -> OwnershipVerificationOut:
    return OwnershipVerificationOut(
        id=record.id,
        red_book_holder_name=record.red_book_holder_name,
        red_book_code=record.red_book_code,
        status=record.status,
        verified_at=record.verified_at,
        property_id=_property_id(db, record.id),
        # The seller sees the home on their red book once they proved it is theirs
        unit=unit_of(db, record) if record.status == OwnershipVerificationStatus.VERIFIED else None,
    )
