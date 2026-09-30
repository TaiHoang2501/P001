"""Seed helpers used at deploy start-up: seed once, add missing red books, keep demo viewing slots in the future."""

from datetime import UTC, datetime

from src.db.models import (
    AvailabilitySlot,
    OwnershipVerificationStatus,
    Property,
    PropertyOwnershipVerification,
    SellerProfile,
    User,
)
from src.db.seed import DEMO_OWNER_IDS, ensure_red_books, ensure_slots, has_data


def test_has_data_after_seed(db):
    assert has_data(db)


def test_ensure_slots_tops_up_demo_owners_only_and_is_idempotent(db):
    demo_available = (
        db.query(Property).filter(Property.owner_id.in_(DEMO_OWNER_IDS), Property.status == "AVAILABLE").count()
    )
    before = db.query(AvailabilitySlot).count()

    # Seed made 3 days; 7 days adds 4 more days x 3 slots per demo listing
    added = ensure_slots(db, days=7)
    assert added == demo_available * 4 * 3
    assert db.query(AvailabilitySlot).count() == before + added
    assert ensure_slots(db, days=7) == 0

    latest = db.query(AvailabilitySlot).order_by(AvailabilitySlot.start_at.desc()).first()
    assert latest.start_at > datetime.now(UTC)


def _wipe_red_books(db) -> None:
    # A database seeded before red books existed: the table is there but empty
    db.query(Property).update({Property.verification_id: None})
    db.query(PropertyOwnershipVerification).delete()
    db.commit()


def test_ensure_red_books_fills_an_older_database_once(db):
    _wipe_red_books(db)

    assert ensure_red_books(db) == 8
    assert db.query(PropertyOwnershipVerification).count() == 8
    lan = db.query(PropertyOwnershipVerification).filter_by(red_book_code="SD-2021-0778902").one()
    assert (lan.red_book_holder_name, lan.user_id, lan.status) == (
        "Hoàng Thị Lan",
        5,
        OwnershipVerificationStatus.VERIFIED,
    )

    assert ensure_red_books(db) == 0


def test_ensure_red_books_never_changes_existing_rows(db):
    record = db.query(PropertyOwnershipVerification).filter_by(red_book_code="SD-2017-0332211").one()
    record.status = OwnershipVerificationStatus.VERIFIED
    record.user_id = 1
    db.commit()

    assert ensure_red_books(db) == 0
    db.refresh(record)
    assert (record.status, record.user_id) == (OwnershipVerificationStatus.VERIFIED, 1)


def test_ensure_red_books_adapts_to_a_different_database(db):
    _wipe_red_books(db)
    # A real seller already used id 1 for another red book, and user 6 does not exist here
    db.add(
        PropertyOwnershipVerification(
            id=1, red_book_holder_name="Người Khác", red_book_code="SD-OTHER-1", owner_phone="0900000000"
        )
    )
    for prop in db.query(Property).filter_by(owner_id=6):
        db.delete(prop)  # media and slots go with it
    db.flush()
    db.query(SellerProfile).filter_by(user_id=6).delete()
    db.query(User).filter_by(id=6).delete()
    db.commit()

    assert ensure_red_books(db) == 8
    tuan = db.query(PropertyOwnershipVerification).filter_by(red_book_code="SD-2019-0456123").one()
    assert tuan.id != 1 and tuan.user_id == 4
    khoa = db.query(PropertyOwnershipVerification).filter_by(red_book_code="SD-2022-0991234").one()
    assert khoa.user_id is None

    # The id sequence moved past every row, so a new red book still gets a free id
    db.add(
        PropertyOwnershipVerification(red_book_holder_name="Mới", red_book_code="SD-NEW-1", owner_phone="0900000001")
    )
    db.commit()
