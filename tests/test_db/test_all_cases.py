"""--ensure-all-cases: every case of each role's pages, for the demo accounts only, added once."""

from sqlalchemy import func, select

from src.db.models import (
    Booking,
    BookingStatus,
    DealStatus,
    Escalation,
    EscalationStatus,
    EscalationType,
    Property,
    PropertyHold,
    PropertyStatus,
    User,
    UserRole,
)
from src.db.seed import (
    DEMO_BUYER_PHONES,
    DEMO_SELLER_PHONES,
    ensure_all_cases,
    ensure_demo_accounts_only,
    ensure_listings,
    ensure_red_book_units,
    ensure_seller_story,
    ensure_sellers_verified,
    ensure_slots,
)


def _start_sh_seed(db) -> None:
    """The steps src/db/seed_once.py runs before ensure_all_cases."""
    ensure_listings(db)
    ensure_seller_story(db)
    ensure_red_book_units(db)
    ensure_sellers_verified(db)
    ensure_demo_accounts_only(db)
    ensure_slots(db, 14)


def _user(db, phone: str) -> User:
    return db.scalar(select(User).where(User.phone == phone))


def test_every_case_for_the_demo_accounts_once(db):
    _start_sh_seed(db)
    people = db.scalar(select(func.count()).select_from(User))

    result = ensure_all_cases(db)
    db.expire_all()
    assert result.startswith("32 case(s)") and "Left out" not in result, result
    # No new people: only the demo accounts and the operators
    assert db.scalar(select(func.count()).select_from(User)) == people

    an, binh = (_user(db, p) for p in DEMO_BUYER_PHONES)
    lan, tuan = (_user(db, p) for p in DEMO_SELLER_PHONES)

    def statuses(buyer: User) -> list[BookingStatus]:
        return sorted(db.scalars(select(Booking.status).where(Booking.customer_id == buyer.id)))

    assert set(statuses(an)) == {
        BookingStatus.REQUESTED,
        BookingStatus.CONFIRMED,
        BookingStatus.RESCHEDULE_REQUESTED,
        BookingStatus.REJECTED,
        BookingStatus.CANCELLED,
        BookingStatus.EXPIRED,
        BookingStatus.COMPLETED,
        BookingStatus.NO_SHOW,
        BookingStatus.OWNER_ABSENT,
    }
    assert {
        BookingStatus.REQUESTED,
        BookingStatus.CONFIRMED,
        BookingStatus.RESCHEDULE_REQUESTED,
        BookingStatus.COMPLETED,
        BookingStatus.UNREPORTED,
    } <= set(statuses(binh))
    # Declined with times offered, closed by another buyer's confirmation, declined with the time closed
    rejected = db.scalars(select(Booking).where(Booking.customer_id == an.id, Booking.status == "REJECTED")).all()
    assert len(rejected) == 3 and any(b.suggested_starts for b in rejected)
    # Both sellers have requests to answer, and Lan two buyers at the same time
    for seller in (lan, tuan):
        assert db.scalar(
            select(Booking.id).where(Booking.owner_id == seller.id, Booking.status == "REQUESTED").limit(1)
        )
    waiting = db.scalars(select(Booking.start_at).where(Booking.owner_id == lan.id, Booking.status == "REQUESTED"))
    starts = list(waiting)
    assert len(starts) > len(set(starts))
    # Every confirmed viewing still ahead holds its home
    ahead = db.scalars(select(Booking.id).where(Booking.status == "CONFIRMED", Booking.start_at > func.now())).all()
    assert ahead and all(db.scalar(select(PropertyHold.id).where(PropertyHold.booking_id == b)) for b in ahead)
    deals = set(db.scalars(select(Booking.deal_id).where(Booking.customer_id.in_((an.id, binh.id)))))
    assert len(deals) == db.scalar(
        select(func.count()).select_from(Booking).where(Booking.customer_id.in_((an.id, binh.id)))
    )
    from src.db.models import Deal

    deal_statuses = set(db.scalars(select(Deal.status).where(Deal.id.in_(deals))))
    assert {DealStatus.VIEWED, DealStatus.INTERESTED, DealStatus.CLOSED} <= deal_statuses

    # Listings in every state
    assert {
        PropertyStatus.AVAILABLE,
        PropertyStatus.PENDING_REVIEW,
        PropertyStatus.REJECTED,
        PropertyStatus.SOLD,
    } <= set(db.scalars(select(Property.status).where(Property.owner_id == lan.id)))
    assert PropertyStatus.WITHDRAWN in set(db.scalars(select(Property.status).where(Property.owner_id == tuan.id)))

    # Operator queue: every kind of case, open, taken and closed
    cases = {(e.type, e.status) for e in db.scalars(select(Escalation))}
    assert {
        (EscalationType.SELLER_NO_RESPONSE, EscalationStatus.OPEN),
        (EscalationType.VIEWING_DISPUTE, EscalationStatus.OPEN),
        (EscalationType.VIEWING_DISPUTE, EscalationStatus.IN_PROGRESS),
        (EscalationType.VIEWING_DISPUTE, EscalationStatus.RESOLVED),
        (EscalationType.NO_COMMON_SLOT, EscalationStatus.OPEN),
        (EscalationType.PROPERTY_ISSUE, EscalationStatus.IN_PROGRESS),
        (EscalationType.OTHER, EscalationStatus.RESOLVED),
        (EscalationType.OWNERSHIP_SUPPORT, EscalationStatus.OPEN),
        (EscalationType.OWNERSHIP_SUPPORT, EscalationStatus.RESOLVED),
    } <= cases
    # The assistant's cases show the buyer's chat to the operator
    from src.services import escalation_service

    slot_case = db.scalar(select(Escalation.id).where(Escalation.type == EscalationType.NO_COMMON_SLOT))
    assert len(escalation_service.case_context(db, slot_case).messages) == 4
    assert all(u.role != UserRole.CUSTOMER or u.phone in DEMO_BUYER_PHONES for u in db.scalars(select(User)))

    counts = (
        db.scalar(select(func.count()).select_from(Booking)),
        db.scalar(select(func.count()).select_from(Escalation)),
        db.scalar(select(func.count()).select_from(Property)),
    )
    assert ensure_all_cases(db) == "already added"
    # The periodic jobs leave the fresh cases as they are (nothing expires, escalates or closes yet)
    from src.services import booking_service, viewing_outcome_service

    before = sorted(db.execute(select(Booking.id, Booking.status)).all())
    assert booking_service.expire_unanswered(db) == 0
    assert escalation_service.escalate_unanswered_requests(db) == 0
    assert escalation_service.settle_stale_cases(db) == 0
    assert viewing_outcome_service.remind_and_close(db)[1] == 0
    assert sorted(db.execute(select(Booking.id, Booking.status)).all()) == before
    assert counts == (
        db.scalar(select(func.count()).select_from(Booking)),
        db.scalar(select(func.count()).select_from(Escalation)),
        db.scalar(select(func.count()).select_from(Property)),
    )
