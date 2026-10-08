"""Demo viewing requests: every case for the story seller, created once, through the same rules as real users."""

from sqlalchemy import func, select

from src.db.models import Booking, BookingStatus, Property, User
from src.db.seed import STORY_SELLER_PHONE, ensure_demo_requests, ensure_listings, ensure_seller_story, ensure_slots


def test_story_seller_gets_every_kind_of_request_once(db):
    ensure_listings(db)
    ensure_seller_story(db)
    ensure_slots(db, 7)
    assert ensure_demo_requests(db) == 10

    seller = db.scalar(select(User.id).where(User.phone == STORY_SELLER_PHONE))
    statuses = set(
        db.scalars(
            select(Booking.status).join(Property, Property.id == Booking.property_id).where(Property.owner_id == seller)
        )
    )
    assert {
        BookingStatus.REQUESTED,
        BookingStatus.CONFIRMED,
        BookingStatus.RESCHEDULE_REQUESTED,
        BookingStatus.REJECTED,
        BookingStatus.CANCELLED,
        BookingStatus.COMPLETED,
        BookingStatus.NO_SHOW,
    } <= statuses

    count = db.scalar(select(func.count()).select_from(Booking))
    assert ensure_demo_requests(db) == 0
    assert db.scalar(select(func.count()).select_from(Booking)) == count
