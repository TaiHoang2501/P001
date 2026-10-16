"""Demo seller story: more verified red books than homes on sale, buyers keep the same homes."""

from sqlalchemy import func, select

from src.db.models import Property, PropertyOwnershipVerification, PropertyStatus, User
from src.db.seed import (
    STORY_OTHER_SELLER_PHONE,
    STORY_SELLER_PHONE,
    STORY_SELLING,
    STORY_UNLISTED,
    ensure_listings,
    ensure_seller_story,
)


def _available(db) -> int:
    return db.scalar(select(func.count()).select_from(Property).where(Property.status == PropertyStatus.AVAILABLE))


def test_seller_verified_more_than_she_sells_and_buyers_lose_nothing(db):
    ensure_listings(db)
    on_sale_before = _available(db)
    ensure_seller_story(db)

    seller = db.scalar(select(User).where(User.phone == STORY_SELLER_PHONE))
    verified = db.scalar(
        select(func.count())
        .select_from(PropertyOwnershipVerification)
        .where(
            PropertyOwnershipVerification.user_id == seller.id,
            PropertyOwnershipVerification.status == "VERIFIED",
            PropertyOwnershipVerification.red_book_code.in_([*STORY_SELLING.values(), *STORY_UNLISTED]),
        )
    )
    selling = db.scalars(
        select(Property).where(Property.owner_id == seller.id, Property.status == PropertyStatus.AVAILABLE)
    ).all()
    assert verified == 8
    assert 0 < len(selling) < verified
    assert all(p.verification_id is not None for p in selling)
    # Every listing of hers is backed by a red book in her name (her own, or one made for an older listing)
    mine = db.scalars(select(Property).where(Property.owner_id == seller.id)).all()
    assert all(p.verification and p.verification.user_id == seller.id for p in mine)
    assert _available(db) == on_sale_before  # moved, not removed
    other = db.scalar(select(User).where(User.phone == STORY_OTHER_SELLER_PHONE))
    assert db.scalar(select(func.count()).select_from(Property).where(Property.owner_id == other.id)) > 0

    # Running it again changes nothing
    assert ensure_seller_story(db).startswith("0 red book(s) added, 0 listing(s) linked, 0 listing(s) moved")
