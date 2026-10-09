"""Showcase demo cases: added once on top of the demo requests, through the same rules as real users."""

from sqlalchemy import func, select

from src.db.models import (
    Booking,
    BookingStatus,
    Escalation,
    EscalationType,
    MediaFile,
    Property,
    PropertyOwnershipVerification,
    PropertyStatus,
    User,
)
from src.db.seed import (
    SHOWCASE_LISTING_BOOK,
    SHOWCASE_OVERLAP,
    SHOWCASE_PAST,
    STORY_SELLER_PHONE,
    ensure_demo_requests,
    ensure_listings,
    ensure_red_book_units,
    ensure_seller_story,
    ensure_showcase,
    ensure_slots,
)


def _deploy_seed(db) -> None:
    """The steps scripts/start.sh runs before the showcase."""
    ensure_listings(db)
    ensure_seller_story(db)
    ensure_red_book_units(db)
    ensure_slots(db, 7)
    ensure_demo_requests(db)


def test_showcase_adds_every_case_once(db):
    _deploy_seed(db)
    result = ensure_showcase(db)
    for case in ("uploaded photos", "overlapping request", "past viewing", "dispute", "ownership support"):
        assert case in result, result

    seller = db.scalar(select(User.id).where(User.phone == STORY_SELLER_PHONE))
    # A listing waiting for review, its photos stored as the seller's uploads
    listing = db.scalar(
        select(Property)
        .join(PropertyOwnershipVerification, PropertyOwnershipVerification.id == Property.verification_id)
        .where(PropertyOwnershipVerification.red_book_code == SHOWCASE_LISTING_BOOK)
    )
    assert (listing.owner_id, listing.status, len(listing.media)) == (seller, PropertyStatus.PENDING_REVIEW, 3)
    assert all(m.s3_key.startswith("/api/v1/media/") for m in listing.media)
    assert db.scalar(select(func.count()).select_from(MediaFile).where(MediaFile.owner_id == seller)) == 3

    # Same time on two of her homes, both waiting for her answer
    phones = [phone for _, phone, *_ in SHOWCASE_OVERLAP]
    overlap = db.scalars(select(Booking).join(User, User.id == Booking.customer_id).where(User.phone.in_(phones))).all()
    assert len(overlap) == 2 and {b.status for b in overlap} == {BookingStatus.REQUESTED}
    assert overlap[0].start_at == overlap[1].start_at and overlap[0].property_id != overlap[1].property_id

    past = db.scalar(select(Booking).join(User, User.id == Booking.customer_id).where(User.phone == SHOWCASE_PAST[1]))
    assert past.status == BookingStatus.CONFIRMED

    cases = set(db.scalars(select(Escalation.type)))
    assert {EscalationType.VIEWING_DISPUTE, EscalationType.OWNERSHIP_SUPPORT} <= cases

    counts = (
        db.scalar(select(func.count()).select_from(Booking)),
        db.scalar(select(func.count()).select_from(Escalation)),
    )
    assert ensure_showcase(db) == "nothing to add"
    assert counts == (
        db.scalar(select(func.count()).select_from(Booking)),
        db.scalar(select(func.count()).select_from(Escalation)),
    )
