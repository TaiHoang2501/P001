"""Schema-level guarantees for deals, bookings and viewing holds (spec §4.9, §4.12, §4.13, AC-08)."""

import re
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from src.db.models import (
    Booking,
    BookingStatus,
    Deal,
    DealStatus,
    HoldStatus,
    Property,
    PropertyHold,
    User,
    UserRole,
)

START = datetime(2030, 1, 5, 7, 0, tzinfo=UTC)


def _buyers(db) -> list[User]:
    return db.query(User).filter_by(role=UserRole.CUSTOMER).order_by(User.id).all()


def _property(db) -> Property:
    return db.query(Property).order_by(Property.id).first()


def _deal(db, buyer: User, prop: Property) -> Deal:
    deal = Deal(buyer_id=buyer.id, seller_id=prop.owner_id, property_id=prop.id)
    db.add(deal)
    db.flush()
    return deal


def _booking(db, deal: Deal, start: datetime, status: BookingStatus = BookingStatus.CONFIRMED) -> Booking:
    booking = Booking(
        deal_id=deal.id,
        property_id=deal.property_id,
        customer_id=deal.buyer_id,
        start_at=start,
        end_at=start + timedelta(hours=1),
        status=status,
    )
    db.add(booking)
    db.flush()
    return booking


def _hold(db, booking: Booking) -> PropertyHold:
    hold = PropertyHold(
        booking_id=booking.id,
        deal_id=booking.deal_id,
        property_id=booking.property_id,
        buyer_id=booking.customer_id,
        start_at=booking.start_at,
        end_at=booking.end_at,
    )
    db.add(hold)
    db.flush()
    return hold


def test_deal_gets_sequential_human_readable_code(db):
    an, binh = _buyers(db)[:2]
    prop = _property(db)
    first, second = _deal(db, an, prop), _deal(db, binh, prop)
    db.commit()

    assert re.fullmatch(r"VH-\d{4}-\d{5}", first.code)
    assert int(second.code[-5:]) == int(first.code[-5:]) + 1
    assert first.status == DealStatus.MATCHED
    assert first.disclosure_level == 1


def test_buyer_has_one_open_deal_per_property(db):
    buyer = _buyers(db)[0]
    prop = _property(db)
    _deal(db, buyer, prop)
    with pytest.raises(IntegrityError, match="uq_deals_open_buyer_property"):
        _deal(db, buyer, prop)


def test_new_deal_allowed_after_previous_one_closed(db):
    buyer = _buyers(db)[0]
    prop = _property(db)
    old = _deal(db, buyer, prop)
    old.status = DealStatus.CLOSED
    db.flush()

    assert _deal(db, buyer, prop).id != old.id


def test_two_active_holds_cannot_overlap(db):
    an, binh = _buyers(db)[:2]
    prop = _property(db)
    _hold(db, _booking(db, _deal(db, an, prop), START))
    # The overlapping booking is cancelled, so only the hold constraint can stop a second hold
    other = _booking(db, _deal(db, binh, prop), START + timedelta(minutes=30), BookingStatus.CANCELLED)

    with pytest.raises(IntegrityError, match="ex_property_holds_no_overlap"):
        _hold(db, other)


def test_released_hold_frees_the_window(db):
    an, binh = _buyers(db)[:2]
    prop = _property(db)
    first = _hold(db, _booking(db, _deal(db, an, prop), START))
    first.status = HoldStatus.RELEASED
    db.flush()

    other = _booking(db, _deal(db, binh, prop), START, BookingStatus.CANCELLED)
    assert _hold(db, other).status == HoldStatus.ACTIVE


def test_reschedule_requested_booking_still_blocks_its_window(db):
    an, binh = _buyers(db)[:2]
    prop = _property(db)
    _booking(db, _deal(db, an, prop), START, BookingStatus.RESCHEDULE_REQUESTED)

    with pytest.raises(IntegrityError, match="ex_bookings_no_overlap"):
        _booking(db, _deal(db, binh, prop), START, BookingStatus.REQUESTED)


def test_proposed_time_must_be_complete_and_ordered(db):
    booking = _booking(db, _deal(db, _buyers(db)[0], _property(db)), START)
    booking.proposed_start_at = START + timedelta(days=1)
    with pytest.raises(IntegrityError, match="ck_bookings_proposed_time_order"):
        db.flush()
