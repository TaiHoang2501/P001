"""AC-03: concurrent requests for the same property/time window -> at most one wins."""

import threading

from src.core.actor import Actor
from src.core.errors import SlotUnavailableError
from src.core.security import hash_password
from src.db.models import AvailabilitySlot, Booking, BookingStatus, User, UserRole
from src.db.session import get_sessionmaker
from src.models.booking import BookingCreate
from src.services import booking_service

N = 10


def test_ten_concurrent_requests_for_one_slot_only_one_succeeds(db):
    customer_ids = []
    pw = hash_password("x" * 8)
    for i in range(N):
        user = User(role=UserRole.CUSTOMER, full_name=f"Racer {i}", phone=f"09880000{i:02d}", password_hash=pw)
        db.add(user)
        db.flush()
        customer_ids.append(user.id)
    db.commit()
    slot = db.query(AvailabilitySlot).filter_by(property_id=1).order_by(AvailabilitySlot.start_at).first()

    barrier = threading.Barrier(N)
    outcomes: list[str] = []
    lock = threading.Lock()

    def attempt(customer_id: int) -> None:
        with get_sessionmaker()() as session:
            actor = Actor(user=session.get(User, customer_id))
            barrier.wait()  # release all threads at the same moment
            try:
                booking_service.create_request(session, actor, BookingCreate(property_id=1, slot_id=slot.id))
                result = "ok"
            except SlotUnavailableError:
                result = "slot_unavailable"
            with lock:
                outcomes.append(result)

    threads = [threading.Thread(target=attempt, args=(cid,)) for cid in customer_ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert sorted(outcomes) == ["ok"] + ["slot_unavailable"] * (N - 1)
    active = (
        db.query(Booking)
        .filter(Booking.property_id == 1, Booking.status.in_([BookingStatus.REQUESTED, BookingStatus.CONFIRMED]))
        .count()
    )
    assert active == 1
