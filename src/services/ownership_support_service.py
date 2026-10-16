"""When a seller cannot verify a red book on their own, the investor steps in (spec §4.5, §6.4 human fallback).

The normal path stays automatic (holder + code in the investor's records, then the owner's OTP). A seller who
cannot get through — no OTP (phone changed), red book locked, details not matching, selling for someone else,
co-owners, inheritance, no red book yet, red book claimed by someone else — sends a support request with
documents. It lands in the operator's exception queue (escalation OWNERSHIP_SUPPORT), where the operator can
unlock the red book, update the owner's phone, verify by hand, or revoke a wrong verification. Every action is
audited and the seller is told.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.actor import Actor
from src.core.errors import BusinessRuleViolationError, NotFoundError, StateConflictError
from src.db.models import (
    ACTIVE_BOOKING_STATUSES,
    OPEN_ESCALATION_STATUSES,
    ActorType,
    Booking,
    Escalation,
    EscalationStatus,
    EscalationType,
    OwnershipVerificationStatus,
    Property,
    PropertyOwnershipVerification,
    PropertyStatus,
    SellerProfile,
    SellerVerificationStatus,
    User,
)
from src.models.escalation import EscalationOut
from src.models.ownership import (
    SUPPORT_REASON_LABEL,
    OwnershipCaseOut,
    OwnershipSupportCreate,
    RedBookState,
    SupportSeller,
)
from src.services import audit, booking_service, escalation_service, media_service, notification_service
from src.services.ownership_service import _normalize_code, _same_name, mask_phone


def _record_by_code(db: Session, code: str) -> PropertyOwnershipVerification | None:
    return db.scalar(
        select(PropertyOwnershipVerification)
        .where(PropertyOwnershipVerification.red_book_code == _normalize_code(code))
        .with_for_update()
    )


# ---------- Seller ----------


def request(db: Session, actor: Actor, data: OwnershipSupportCreate) -> EscalationOut:
    """Open a support case for a red book (one open case per seller and red book)."""
    code = _normalize_code(data.red_book_code)
    for key in data.documents:
        if media_service.require_own_upload(db, actor, key) is None:
            raise BusinessRuleViolationError("Attach documents uploaded from your device")
    already = db.scalar(
        select(Escalation.id).where(
            Escalation.type == EscalationType.OWNERSHIP_SUPPORT,
            Escalation.requester_id == actor.id,
            Escalation.status.in_(OPEN_ESCALATION_STATUSES),
            Escalation.context["red_book_code"].astext == code,
        )
    )
    if already is not None:
        raise StateConflictError(
            "A support request for this red book is already open", details={"escalation_id": already}
        )
    esc = escalation_service.create(
        db,
        type=EscalationType.OWNERSHIP_SUPPORT,
        summary=f"Hỗ trợ xác thực sổ đỏ / sổ hồng {code}: {SUPPORT_REASON_LABEL[data.reason]}",
        raised_by=ActorType.USER,
        actor=actor,
        requester_id=actor.id,
        context={
            "reason": data.reason,
            "red_book_code": code,
            "red_book_holder_name": data.red_book_holder_name.strip(),
            "note": data.note.strip(),
            "documents": data.documents,
        },
    )
    db.commit()
    return escalation_service.for_requester(esc)


def list_mine(db: Session, actor: Actor) -> list[EscalationOut]:
    rows = db.scalars(
        select(Escalation)
        .where(Escalation.type == EscalationType.OWNERSHIP_SUPPORT, Escalation.requester_id == actor.id)
        .order_by(Escalation.created_at.desc())
    )
    return [escalation_service.for_requester(e) for e in rows]


# ---------- Operator ----------


def _case(db: Session, escalation_id: int, *, open_only: bool = True) -> Escalation:
    esc = db.get(Escalation, escalation_id, with_for_update=True)
    if esc is None or esc.type != EscalationType.OWNERSHIP_SUPPORT:
        raise NotFoundError(f"Ownership support case {escalation_id} not found")
    if open_only and esc.status not in OPEN_ESCALATION_STATUSES:
        raise StateConflictError(f"This case is already {esc.status.value}")
    return esc


def _state(db: Session, record: PropertyOwnershipVerification | None) -> RedBookState | None:
    if record is None:
        return None
    holder = db.get(User, record.user_id) if record.user_id else None
    listing = db.scalar(select(Property).where(Property.verification_id == record.id))
    return RedBookState(
        id=record.id,
        red_book_code=record.red_book_code,
        red_book_holder_name=record.red_book_holder_name,
        owner_phone=record.owner_phone,
        masked_phone=mask_phone(record.owner_phone),
        status=record.status,
        otp_attempts=record.otp_attempts,
        verified_by_id=holder.id if holder else None,
        verified_by_name=holder.full_name if holder else None,
        property_id=listing.id if listing else None,
        property_label=f"{listing.unit_code} ({listing.status.value})" if listing else None,
    )


def case(db: Session, escalation_id: int) -> OwnershipCaseOut:
    """What the operator needs to decide: the request, the seller, and the red book as it stands now."""
    esc = _case(db, escalation_id, open_only=False)
    seller = db.get(User, esc.requester_id) if esc.requester_id else None
    profile = db.get(SellerProfile, seller.id) if seller else None
    record = _record_by_code(db, esc.context.get("red_book_code", ""))
    holder = record.red_book_holder_name if record is not None else esc.context.get("red_book_holder_name")
    return OwnershipCaseOut(
        escalation_id=esc.id,
        holder_name=holder,
        sender_is_holder=seller is None or holder is None or _same_name(seller.full_name, holder),
        has_documents=bool(esc.context.get("documents")),
        seller=SupportSeller(
            id=seller.id,
            full_name=seller.full_name,
            phone=seller.phone,
            verification_status=profile.verification_status if profile else None,
        )
        if seller
        else None,
        red_book=_state(db, record),
    )


def _close(db: Session, actor: Actor, esc: Escalation, resolution: str) -> None:
    esc.status = EscalationStatus.RESOLVED
    esc.resolution = resolution
    esc.resolved_at = datetime.now(UTC)
    esc.assigned_to = esc.assigned_to or actor.id
    audit.record(db, actor, "escalation.resolve", "escalation", esc.id, after={"resolution": resolution})
    if esc.requester_id is not None:
        notification_service.notify(
            db,
            esc.requester_id,
            "OWNERSHIP_SUPPORT_RESOLVED",
            "Yêu cầu hỗ trợ xác thực sổ đỏ / sổ hồng đã được xử lý",
            resolution,
            payload={"escalation_id": esc.id},
        )


def _require_record(db: Session, esc: Escalation) -> PropertyOwnershipVerification:
    record = _record_by_code(db, esc.context.get("red_book_code", ""))
    if record is None:
        raise NotFoundError("This red book code is not in the investor's records; verify it by hand instead")
    return record


def unlock(db: Session, actor: Actor, escalation_id: int, owner_phone: str | None = None) -> OwnershipCaseOut:
    """Unlock a red book locked by wrong codes, optionally with the owner's new phone; the seller verifies again."""
    esc = _case(db, escalation_id)
    escalation_service.require_handler(esc, actor)
    record = _require_record(db, esc)
    if record.status == OwnershipVerificationStatus.VERIFIED:
        raise StateConflictError("This red book is already verified; revoke it first if it is wrong")
    before = {
        "status": record.status,
        "otp_attempts": record.otp_attempts,
        "owner_phone": mask_phone(record.owner_phone),
    }
    record.status = OwnershipVerificationStatus.UNVERIFIED
    record.otp_attempts = 0
    if owner_phone:
        record.owner_phone = owner_phone
    audit.record(
        db,
        actor,
        "ownership.unlock",
        "ownership_verification",
        record.id,
        before=before,
        after={"status": record.status, "owner_phone": mask_phone(record.owner_phone), "escalation_id": esc.id},
    )
    _close(
        db,
        actor,
        esc,
        (
            f"Đã cập nhật số điện thoại chủ sở hữu (mới: {mask_phone(record.owner_phone)}) và mở khóa sổ {record.red_book_code}. "
            if owner_phone
            else f"Đã mở khóa sổ {record.red_book_code}. "
        )
        + "Bạn vào “Xác thực sổ đỏ / sổ hồng” và làm lại bước nhận mã OTP.",
    )
    db.commit()
    return case(db, esc.id)


def verify(db: Session, actor: Actor, escalation_id: int, note: str) -> OwnershipCaseOut:
    """Verify by hand after checking the documents (proxy, co-owners, inheritance, records wrong, no red book yet).

    A code missing from the investor's records (e.g. only a sale contract so far) is added as a red book here;
    the seller then enters the home's details themselves when listing it.
    """
    esc = _case(db, escalation_id)
    escalation_service.require_handler(esc, actor)
    if esc.requester_id is None:
        raise StateConflictError("This case has no seller to verify")
    record = _record_by_code(db, esc.context.get("red_book_code", ""))
    if (
        record is not None
        and record.status == OwnershipVerificationStatus.VERIFIED
        and record.user_id != esc.requester_id
    ):
        raise StateConflictError("Another account holds this red book; revoke it first")
    if not esc.context.get("documents"):
        # Never on someone's word alone: two people can share a name, and a home could be handed to the wrong one
        raise BusinessRuleViolationError(
            "Verify by hand only after checking the seller's documents; ask them to send a request with documents",
            details={"missing": "DOCUMENTS"},
        )
    seller = db.get(User, esc.requester_id)
    now = datetime.now(UTC)
    if record is None:
        record = PropertyOwnershipVerification(
            red_book_holder_name=esc.context.get("red_book_holder_name") or seller.full_name,
            red_book_code=esc.context["red_book_code"],
            owner_phone=seller.phone or "",
        )
        db.add(record)
    record.user_id = seller.id
    record.status = OwnershipVerificationStatus.VERIFIED
    record.verified_at = now
    record.otp_attempts = 0
    db.flush()
    audit.record(
        db,
        actor,
        "ownership.verified_by_operator",
        "ownership_verification",
        record.id,
        after={"user_id": seller.id, "escalation_id": esc.id, "note": note},
    )
    profile = db.get(SellerProfile, seller.id, with_for_update=True)
    if profile is not None and profile.verification_status != SellerVerificationStatus.VERIFIED:
        before = profile.verification_status
        profile.verification_status = SellerVerificationStatus.VERIFIED
        profile.verified_by = actor.id
        profile.verified_at = now
        profile.rejection_reason = None
        audit.record(
            db,
            actor,
            "seller.verify",
            "user",
            seller.id,
            before={"verification_status": before},
            after={"verification_status": profile.verification_status, "escalation_id": esc.id},
        )
    _close(
        db, actor, esc, f"Chủ đầu tư đã xác thực sổ {record.red_book_code} cho bạn: {note}. Bạn có thể đăng bán ngay."
    )
    db.commit()
    return case(db, esc.id)


def revoke(db: Session, actor: Actor, escalation_id: int, reason: str) -> OwnershipCaseOut:
    """Take back a wrong verification (e.g. someone else claimed the seller's red book).

    Viewings of its listing are cancelled (buyers told), the listing comes off the market and lets go of the red
    book, which can then be verified by its real owner. The case stays open for the next step.
    """
    esc = _case(db, escalation_id)
    escalation_service.require_handler(esc, actor)
    record = _require_record(db, esc)
    if record.status != OwnershipVerificationStatus.VERIFIED or record.user_id is None:
        raise StateConflictError("This red book is not verified by anyone")
    holder_id = record.user_id
    listing = db.scalar(select(Property).where(Property.verification_id == record.id))
    if listing is not None:
        # Viewings still ahead are cancelled (both sides told why), in this one transaction; one whose time has
        # come stays for its outcome
        for booking in db.scalars(
            select(Booking)
            .where(
                Booking.property_id == listing.id,
                Booking.status.in_(ACTIVE_BOOKING_STATUSES),
                Booking.start_at > datetime.now(UTC),
            )
            .with_for_update()
        ).all():
            booking_service.cancel_in_tx(db, actor, booking, "Chủ đầu tư đang kiểm tra lại quyền sở hữu căn này")
        listing = db.get(Property, listing.id, with_for_update=True)
        before = listing.status
        if listing.status != PropertyStatus.SOLD:
            listing.status = PropertyStatus.WITHDRAWN
        listing.verification_id = None
        audit.record(
            db,
            actor,
            "property.ownership_revoked",
            "property",
            listing.id,
            before={"status": before},
            after={"status": listing.status, "escalation_id": esc.id, "reason": reason},
        )
    record = db.get(PropertyOwnershipVerification, record.id, with_for_update=True)
    record.status = OwnershipVerificationStatus.UNVERIFIED
    record.user_id = None
    record.verified_at = None
    record.otp_attempts = 0
    audit.record(
        db,
        actor,
        "ownership.revoked",
        "ownership_verification",
        record.id,
        before={"user_id": holder_id},
        after={"status": record.status, "escalation_id": esc.id, "reason": reason},
    )
    # A seller left without any verified red book is no longer a verified seller
    still = db.scalar(
        select(PropertyOwnershipVerification.id).where(
            PropertyOwnershipVerification.user_id == holder_id,
            PropertyOwnershipVerification.status == OwnershipVerificationStatus.VERIFIED,
        )
    )
    profile = db.get(SellerProfile, holder_id, with_for_update=True)
    if still is None and profile is not None:
        profile.verification_status = SellerVerificationStatus.REJECTED
        profile.rejection_reason = reason
    notification_service.notify(
        db,
        holder_id,
        "OWNERSHIP_REVOKED",
        "Xác thực sổ đỏ / sổ hồng đã bị thu hồi",
        f"Chủ đầu tư đã thu hồi xác thực sổ {record.red_book_code}: {reason}."
        + (" Tin đăng của căn này đã được gỡ." if listing is not None else ""),
        payload={"escalation_id": esc.id},
    )
    db.commit()
    return case(db, esc.id)


def get_esc(db: Session, escalation_id: int) -> EscalationOut:
    return EscalationOut.model_validate(_case(db, escalation_id, open_only=False))
