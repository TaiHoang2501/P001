"""Seed helpers used at deploy start-up: seed once, keep demo viewing slots in the future."""

from datetime import UTC, datetime

from src.db.models import AvailabilitySlot, Property
from src.db.seed import DEMO_OWNER_IDS, ensure_slots, has_data


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
