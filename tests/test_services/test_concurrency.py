"""AC-08: concurrent requests/confirmations for the same property/time window -> at most one wins."""

import threading

import pytest
from sqlalchemy.exc import OperationalError

from src.core.actor import Actor
from src.core.errors import SlotUnavailableError, StateConflictError
from src.core.security import hash_password
from src.db.models import AvailabilitySlot, Booking, BookingStatus, HoldStatus, PropertyHold, User, UserRole
from src.db.session import get_sessionmaker
from src.models.booking import BookingCreate
from src.services import booking_service

N = 10


def _racers(db, n: int) -> list[int]:
    ids = []
    pw = hash_password("x" * 8)
    for i in range(n):
        user = User(role=UserRole.CUSTOMER, full_name=f"Racer {i}", phone=f"09880000{i:02d}", password_hash=pw)
        db.add(user)
        db.flush()
        ids.append(user.id)
    db.commit()
    return ids


def _run_together(n: int, attempt) -> list[str]:
    barrier = threading.Barrier(n)
    outcomes: list[str] = []
    lock = threading.Lock()

    def run(i: int) -> None:
        barrier.wait()  # release all threads at the same moment
        try:
            result = attempt(i)
        except Exception as e:  # surface anything unexpected in the assertion message
            result = f"error:{type(e).__name__}:{e}"
        with lock:
            outcomes.append(result)

    threads = [threading.Thread(target=run, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not any(t.is_alive() for t in threads), f"threads still blocked; finished: {outcomes}"
    return outcomes


def test_ten_buyers_may_ask_for_one_slot_at_the_same_moment(db):
    """Unanswered requests do not take the time: all ten are kept, the owner chooses."""
    customer_ids = _racers(db, N)
    slot = db.query(AvailabilitySlot).filter_by(property_id=1).order_by(AvailabilitySlot.start_at).first()

    def attempt(i: int) -> str:
        with get_sessionmaker()() as session:
            actor = Actor(user=session.get(User, customer_ids[i]))
            booking_service.create_request(session, actor, BookingCreate(property_id=1, slot_id=slot.id))
            return "ok"

    assert _run_together(N, attempt) == ["ok"] * N
    assert db.query(Booking).filter_by(property_id=1, status=BookingStatus.REQUESTED).count() == N


def test_owner_confirming_overlapping_requests_at_once_receives_only_one(db):
    """AC-08 per owner: two overlapping requests (on two of the owner's homes) confirmed at the same moment."""
    a, b = _racers(db, 2)
    owner_id = 4
    first = db.query(AvailabilitySlot).filter_by(property_id=1).order_by(AvailabilitySlot.start_at).first()
    second = db.query(AvailabilitySlot).filter_by(property_id=3, start_at=first.start_at).one()
    with get_sessionmaker()() as session:
        ids = [
            booking_service.create_request(
                session, Actor(user=session.get(User, buyer)), BookingCreate(property_id=prop, slot_id=slot.id)
            ).id
            for buyer, prop, slot in ((a, 1, first), (b, 3, second))
        ]

    def attempt(i: int) -> str:
        with get_sessionmaker()() as session:
            try:
                booking_service.approve(session, Actor(user=session.get(User, owner_id)), ids[i])
                return "ok"
            except (StateConflictError, SlotUnavailableError):
                return "too_late"

    assert sorted(_run_together(2, attempt)) == ["ok", "too_late"]
    db.expire_all()
    statuses = sorted(db.get(Booking, i).status for i in ids)
    assert statuses == [BookingStatus.CONFIRMED, BookingStatus.REJECTED]
    assert (
        db.query(PropertyHold)
        .filter(PropertyHold.booking_id.in_(ids), PropertyHold.status == HoldStatus.ACTIVE)
        .count()
        == 1
    )


def test_concurrent_owner_confirmations_create_one_hold(db):
    slot = db.query(AvailabilitySlot).filter_by(property_id=1).order_by(AvailabilitySlot.start_at).first()
    with get_sessionmaker()() as session:
        buyer = Actor(user=session.get(User, 1))
        booking_id = booking_service.create_request(session, buyer, BookingCreate(property_id=1, slot_id=slot.id)).id

    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    lock = threading.Lock()

    def attempt() -> None:
        with get_sessionmaker()() as session:
            owner = Actor(user=session.get(User, 4))
            barrier.wait()
            try:
                booking_service.approve(session, owner, booking_id)
                result = "ok"
            except StateConflictError:
                result = "conflict"
            except Exception as e:
                result = f"error:{type(e).__name__}:{e}"
            with lock:
                outcomes.append(result)

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not any(t.is_alive() for t in threads), f"threads still blocked; finished: {outcomes}"

    assert sorted(outcomes) == ["conflict", "ok"]
    holds = db.query(PropertyHold).filter_by(booking_id=booking_id, status=HoldStatus.ACTIVE).count()
    assert holds == 1


class _PgError(Exception):
    def __init__(self, sqlstate: str) -> None:
        super().__init__(sqlstate)
        self.sqlstate = sqlstate


def test_exclusion_deadlock_is_reported_as_slot_unavailable(db, monkeypatch):
    """Two overlapping inserts can deadlock while checking the exclusion constraint; the loser gets
    SLOT_UNAVAILABLE with alternatives, not a server error."""
    slot = db.query(AvailabilitySlot).filter_by(property_id=1).order_by(AvailabilitySlot.start_at).first()
    with get_sessionmaker()() as session:
        buyer = Actor(user=session.get(User, 1))
        real_flush = session.flush

        def flush_then_deadlock(*args, **kwargs):
            if any(isinstance(o, Booking) for o in session.new):
                raise OperationalError("INSERT INTO bookings ...", {}, _PgError("40P01"))
            return real_flush(*args, **kwargs)

        monkeypatch.setattr(session, "flush", flush_then_deadlock)
        try:
            booking_service.create_request(session, buyer, BookingCreate(property_id=1, slot_id=slot.id))
        except SlotUnavailableError as e:
            assert e.details["free_slots"]
        else:
            raise AssertionError("expected SlotUnavailableError")


def test_other_operational_errors_are_not_hidden(db, monkeypatch):
    slot = db.query(AvailabilitySlot).filter_by(property_id=1).order_by(AvailabilitySlot.start_at).first()
    with get_sessionmaker()() as session:
        buyer = Actor(user=session.get(User, 1))
        real_flush = session.flush

        def flush_connection_lost(*args, **kwargs):
            if any(isinstance(o, Booking) for o in session.new):
                raise OperationalError("INSERT INTO bookings ...", {}, _PgError("08006"))
            return real_flush(*args, **kwargs)

        monkeypatch.setattr(session, "flush", flush_connection_lost)
        with pytest.raises(OperationalError):
            booking_service.create_request(session, buyer, BookingCreate(property_id=1, slot_id=slot.id))
