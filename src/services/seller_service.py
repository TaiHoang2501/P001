"""Seller (Owner) verification by the operator (spec §2.3 principle 5, §4.5, AC-04)."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.actor import Actor
from src.core.errors import NotFoundError, SellerUnverifiedError, StateConflictError
from src.db.models import SellerProfile, SellerVerificationStatus, User, UserRole
from src.models.seller import SellerProfileOut, SellerReviewItem, SellerVerificationSubmit
from src.services import audit

_SUBMITTABLE = {SellerVerificationStatus.UNVERIFIED, SellerVerificationStatus.REJECTED}


def _profile(db: Session, user_id: int, *, for_update: bool = False) -> SellerProfile:
    profile = db.get(SellerProfile, user_id, with_for_update=for_update)
    if profile is None:
        raise NotFoundError(f"Seller {user_id} not found")
    return profile


def is_verified(db: Session, user_id: int) -> bool:
    status = db.scalar(select(SellerProfile.verification_status).where(SellerProfile.user_id == user_id))
    return status == SellerVerificationStatus.VERIFIED


def require_verified(db: Session, user_id: int) -> None:
    if not is_verified(db, user_id):
        raise SellerUnverifiedError("The owner of this property has not been verified yet")


# ---------- Seller ----------


def get_own(db: Session, actor: Actor) -> SellerProfileOut:
    return SellerProfileOut.model_validate(_profile(db, actor.id))


def submit(db: Session, actor: Actor, data: SellerVerificationSubmit) -> SellerProfileOut:
    profile = _profile(db, actor.id, for_update=True)
    if profile.verification_status not in _SUBMITTABLE:
        raise StateConflictError(f"Verification is already {profile.verification_status.value}")
    before = profile.verification_status
    profile.verification_status = SellerVerificationStatus.PENDING
    profile.id_document_s3_key = data.id_document_s3_key
    profile.rejection_reason = None
    audit.record(
        db,
        actor,
        "seller.submit_verification",
        "user",
        actor.id,
        before={"verification_status": before},
        after={"verification_status": profile.verification_status},
    )
    db.commit()
    return SellerProfileOut.model_validate(profile)


# ---------- Operator ----------


def list_by_status(db: Session, status: SellerVerificationStatus) -> list[SellerReviewItem]:
    rows = db.execute(
        select(SellerProfile, User)
        .join(User, User.id == SellerProfile.user_id)
        .where(SellerProfile.verification_status == status, User.role == UserRole.OWNER)
        .order_by(SellerProfile.updated_at)
    )
    return [
        SellerReviewItem(
            **SellerProfileOut.model_validate(p).model_dump(), full_name=u.full_name, phone=u.phone, email=u.email
        )
        for p, u in rows
    ]


def verify(db: Session, actor: Actor, user_id: int) -> SellerProfileOut:
    return _review(db, actor, user_id, SellerVerificationStatus.VERIFIED)


def reject(db: Session, actor: Actor, user_id: int, reason: str) -> SellerProfileOut:
    return _review(db, actor, user_id, SellerVerificationStatus.REJECTED, reason)


def _review(
    db: Session, actor: Actor, user_id: int, to: SellerVerificationStatus, reason: str | None = None
) -> SellerProfileOut:
    profile = _profile(db, user_id, for_update=True)
    if profile.verification_status != SellerVerificationStatus.PENDING:
        raise StateConflictError(f"Cannot review a seller in status {profile.verification_status.value}")
    profile.verification_status = to
    profile.verified_by = actor.id
    profile.verified_at = datetime.now(UTC)
    profile.rejection_reason = reason
    audit.record(
        db,
        actor,
        "seller.verify" if to == SellerVerificationStatus.VERIFIED else "seller.reject",
        "user",
        user_id,
        before={"verification_status": SellerVerificationStatus.PENDING},
        after={"verification_status": to, **({"reason": reason} if reason else {})},
    )
    db.commit()
    return SellerProfileOut.model_validate(profile)
