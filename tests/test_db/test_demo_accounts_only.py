"""--demo-accounts-only: every home and red book goes to a demo seller; the other sellers and buyers are deleted."""

from sqlalchemy import func, select

from src.db.models import Booking, Deal, Property, PropertyOwnershipVerification, PropertyStatus, User, UserRole
from src.db.seed import (
    DEMO_BUYER_PHONES,
    DEMO_SELLER_PHONES,
    STORY_OTHER_SELLER_PHONE,
    ensure_demo_accounts_only,
    ensure_rich_demo,
    ensure_showcase,
    ensure_slots,
)
from tests.test_db.test_showcase import _deploy_seed


def _phones(db, role: UserRole) -> set[str]:
    return set(db.scalars(select(User.phone).where(User.role == role)))


def test_only_demo_accounts_are_left_and_they_own_every_home(db):
    _deploy_seed(db)
    ensure_showcase(db)
    ensure_slots(db, 14)
    ensure_rich_demo(db)
    operators = _phones(db, UserRole.INVESTOR_OPERATOR)
    homes = db.scalar(select(func.count()).select_from(Property))
    an_bookings = db.scalar(
        select(func.count())
        .select_from(Booking)
        .join(User, User.id == Booking.customer_id)
        .where(User.phone == DEMO_BUYER_PHONES[0])
    )
    assert _phones(db, UserRole.OWNER) > set(DEMO_SELLER_PHONES)
    assert _phones(db, UserRole.CUSTOMER) > set(DEMO_BUYER_PHONES)

    result = ensure_demo_accounts_only(db)
    db.expire_all()

    assert _phones(db, UserRole.OWNER) == set(DEMO_SELLER_PHONES), result
    assert _phones(db, UserRole.CUSTOMER) == set(DEMO_BUYER_PHONES)
    assert _phones(db, UserRole.INVESTOR_OPERATOR) == operators
    sellers = set(db.scalars(select(User.id).where(User.role == UserRole.OWNER)))
    # Every home kept, each owned by a demo seller, with its deals and viewings following it
    assert db.scalar(select(func.count()).select_from(Property)) == homes
    assert set(db.scalars(select(Property.owner_id))) <= sellers
    assert (
        db.scalar(select(func.count()).select_from(Deal).join(Property).where(Deal.seller_id != Property.owner_id)) == 0
    )
    assert (
        db.scalar(select(func.count()).select_from(Booking).join(Property).where(Booking.owner_id != Property.owner_id))
        == 0
    )
    # The demo buyer keeps their viewings
    an = db.scalar(select(User.id).where(User.phone == DEMO_BUYER_PHONES[0]))
    assert db.scalar(select(func.count()).select_from(Booking).where(Booking.customer_id == an)) == an_bookings
    # Red books are the demo sellers' (or still unclaimed), with a demo seller's phone on record
    books = db.scalars(select(PropertyOwnershipVerification)).all()
    assert all(b.user_id is None or b.user_id in sellers for b in books)
    assert {b.owner_phone for b in books} <= set(DEMO_SELLER_PHONES)
    # A home of the seller who was never verified is not put on sale by the move
    heir = db.scalar(select(User.id).where(User.phone == STORY_OTHER_SELLER_PHONE))
    hidden = db.scalar(select(Property).where(Property.unit_code == "GS3-2104"))  # the seed's unverified owner's
    assert (hidden.owner_id, hidden.status) == (heir, PropertyStatus.PENDING_REVIEW)

    # Once only: people who sign up later are kept
    db.add(User(role=UserRole.CUSTOMER, full_name="Người Mua Thật", phone="0977000111"))
    db.commit()
    assert ensure_demo_accounts_only(db) == "already done"
    assert "0977000111" in _phones(db, UserRole.CUSTOMER)
