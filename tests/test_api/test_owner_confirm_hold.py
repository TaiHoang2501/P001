"""Owner confirmation, viewing hold and reschedule (spec §4.12, §4.13, AC-05, AC-08)."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.db.models import AuditLog, Booking, BookingStatus, Deal, HoldStatus, PropertyHold
from src.services import hold_service
from tests.helpers import CUSTOMER_AN, CUSTOMER_BINH, OWNER_TUAN, auth

VN = ZoneInfo("Asia/Ho_Chi_Minh")
PROPERTY_ID = 1
SAT = datetime(2030, 1, 5, tzinfo=VN)


def at(hour: float) -> str:
    return (SAT + timedelta(hours=hour)).isoformat()


async def _setup(client, start: float = 14, end: float = 17) -> tuple[dict, dict]:
    tuan = await auth(client, OWNER_TUAN)
    r = await client.post(
        f"/api/v1/owner/properties/{PROPERTY_ID}/slots", json={"start_at": at(start), "end_at": at(end)}, headers=tuan
    )
    assert r.status_code == 201, r.text
    return tuan, await auth(client, CUSTOMER_AN)


async def _request(client, buyer, hour: float) -> dict:
    r = await client.post("/api/v1/bookings", json={"property_id": PROPERTY_ID, "start_at": at(hour)}, headers=buyer)
    assert r.status_code == 201, r.text
    return r.json()


def _holds(db, booking_id: int) -> list[PropertyHold]:
    db.expire_all()
    return db.query(PropertyHold).filter_by(booking_id=booking_id).all()


@pytest.mark.asyncio
async def test_ac05_request_is_not_confirmed_or_held_until_owner_approves(client, db):
    _, an = await _setup(client)
    booking = await _request(client, an, 15)
    assert booking["status"] == "REQUESTED"
    assert booking["hold_status"] is None
    assert _holds(db, booking["id"]) == []


@pytest.mark.asyncio
async def test_owner_confirm_creates_hold_for_the_viewing_window_only(client, db):
    tuan, an = await _setup(client)
    booking = await _request(client, an, 15)

    r = await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=tuan)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "CONFIRMED"
    assert r.json()["hold_status"] == "ACTIVE"

    [hold] = _holds(db, booking["id"])
    assert (hold.start_at, hold.end_at) == (SAT + timedelta(hours=15), SAT + timedelta(hours=15.5))
    assert hold.deal_id == booking["deal_id"]
    deal = (await client.get(f"/api/v1/deals/{booking['deal_id']}", headers=an)).json()
    assert deal["status"] == "VIEWING_CONFIRMED"


@pytest.mark.asyncio
async def test_cancel_releases_hold(client, db):
    tuan, an = await _setup(client)
    booking = await _request(client, an, 15)
    await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=tuan)

    r = await client.post(f"/api/v1/bookings/{booking['id']}/cancel", headers=an)
    assert r.json()["status"] == "CANCELLED"
    [hold] = _holds(db, booking["id"])
    assert hold.status == HoldStatus.RELEASED
    assert hold.release_reason == "cancelled"


def test_hold_expires_after_viewing_window(db):
    # A confirmed viewing whose window has ended (inserted directly, the API refuses past times)
    deal = Deal(buyer_id=1, seller_id=4, property_id=PROPERTY_ID)
    db.add(deal)
    db.flush()
    start = datetime.now(UTC) - timedelta(hours=2)
    booking = Booking(
        deal_id=deal.id,
        property_id=PROPERTY_ID,
        customer_id=1,
        start_at=start,
        end_at=start + timedelta(minutes=30),
        status=BookingStatus.CONFIRMED,
    )
    db.add(booking)
    db.flush()
    db.add(
        PropertyHold(
            booking_id=booking.id,
            deal_id=deal.id,
            property_id=PROPERTY_ID,
            buyer_id=1,
            start_at=booking.start_at,
            end_at=booking.end_at,
        )
    )
    db.commit()

    assert hold_service.expire_finished(db) == 1
    [hold] = _holds(db, booking.id)
    assert hold.status == HoldStatus.EXPIRED
    assert hold_service.expire_finished(db) == 0


@pytest.mark.asyncio
async def test_reschedule_accepted_moves_booking_and_hold(client, db):
    tuan, an = await _setup(client)
    booking = await _request(client, an, 15)
    await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=tuan)

    r = await client.post(f"/api/v1/bookings/{booking['id']}/reschedule", json={"start_at": at(16)}, headers=an)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "RESCHEDULE_REQUESTED"
    # Old time and its hold stay until the owner accepts
    assert datetime.fromisoformat(r.json()["start_at"]) == SAT + timedelta(hours=15)
    assert r.json()["hold_status"] == "ACTIVE"

    r = await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=tuan)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "CONFIRMED"
    assert datetime.fromisoformat(r.json()["start_at"]) == SAT + timedelta(hours=16)
    assert r.json()["proposed_start_at"] is None
    [hold] = _holds(db, booking["id"])
    assert hold.start_at == SAT + timedelta(hours=16)
    assert hold.status == HoldStatus.ACTIVE


@pytest.mark.asyncio
async def test_reschedule_declined_keeps_original_time(client, db):
    tuan, an = await _setup(client)
    booking = await _request(client, an, 15)
    await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=tuan)
    await client.post(f"/api/v1/bookings/{booking['id']}/reschedule", json={"start_at": at(16)}, headers=an)

    r = await client.post(
        f"/api/v1/owner/bookings/{booking['id']}/reject", json={"reason": "16h tôi bận"}, headers=tuan
    )
    assert r.json()["status"] == "CONFIRMED"
    assert datetime.fromisoformat(r.json()["start_at"]) == SAT + timedelta(hours=15)
    assert r.json()["proposed_start_at"] is None
    actions = [a for (a,) in db.query(AuditLog.action).filter_by(target_type="booking", target_id=booking["id"])]
    assert actions[-1] == "booking.reschedule_decline"


@pytest.mark.asyncio
async def test_reschedule_to_taken_time_fails_at_confirmation(client):
    tuan, an = await _setup(client)
    binh = await auth(client, CUSTOMER_BINH)
    mine = await _request(client, an, 15)
    await client.post(f"/api/v1/owner/bookings/{mine['id']}/approve", headers=tuan)
    await client.post(f"/api/v1/bookings/{mine['id']}/reschedule", json={"start_at": at(16)}, headers=an)
    # Someone else books 16:00 before the owner answers
    await _request(client, binh, 16)

    r = await client.post(f"/api/v1/owner/bookings/{mine['id']}/approve", headers=tuan)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "SLOT_UNAVAILABLE"
    # Nothing changed: still waiting on the reschedule, old time still held
    r = await client.get(f"/api/v1/bookings/{mine['id']}", headers=an)
    assert r.json()["status"] == "RESCHEDULE_REQUESTED"
    assert r.json()["hold_status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_unanswered_request_moves_to_the_new_time_and_still_needs_the_owner(client, db):
    tuan, an = await _setup(client)
    booking = await _request(client, an, 15)

    r = await client.post(f"/api/v1/bookings/{booking['id']}/reschedule", json={"start_at": at(16)}, headers=an)
    assert r.status_code == 200, r.text
    moved = r.json()
    assert moved["id"] == booking["id"] and moved["deal_code"] == booking["deal_code"]
    assert moved["status"] == "REQUESTED"
    assert datetime.fromisoformat(moved["start_at"]) == SAT + timedelta(hours=16)
    assert moved["proposed_start_at"] is None
    assert moved["hold_status"] is None
    actions = [a for (a,) in db.query(AuditLog.action).filter_by(target_type="booking", target_id=booking["id"])]
    assert actions[-1] == "booking.request_time_change"

    # The owner is told and confirms the new time as usual (AC-05)
    r = await client.get("/api/v1/notifications", headers=tuan)
    assert r.json()[0]["event_type"] == "VIEWING_REQUEST_UPDATED"
    r = await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=tuan)
    assert r.json()["status"] == "CONFIRMED"
    [hold] = _holds(db, booking["id"])
    assert hold.start_at == SAT + timedelta(hours=16)


@pytest.mark.asyncio
async def test_unanswered_request_cannot_move_onto_a_taken_time(client):
    _, an = await _setup(client)
    binh = await auth(client, CUSTOMER_BINH)
    mine = await _request(client, an, 15)
    await _request(client, binh, 16)

    r = await client.post(f"/api/v1/bookings/{mine['id']}/reschedule", json={"start_at": at(16)}, headers=an)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "SLOT_UNAVAILABLE"
    r = await client.get(f"/api/v1/bookings/{mine['id']}", headers=an)
    assert datetime.fromisoformat(r.json()["start_at"]) == SAT + timedelta(hours=15)


@pytest.mark.asyncio
async def test_ended_viewings_cannot_be_rescheduled(client):
    tuan, an = await _setup(client)
    booking = await _request(client, an, 15)
    await client.post(f"/api/v1/bookings/{booking['id']}/cancel", headers=an)
    r = await client.post(f"/api/v1/bookings/{booking['id']}/reschedule", json={"start_at": at(16)}, headers=an)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_other_buyer_cannot_reschedule(client):
    tuan, an = await _setup(client)
    booking = await _request(client, an, 15)
    await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=tuan)
    binh = await auth(client, CUSTOMER_BINH)
    r = await client.post(f"/api/v1/bookings/{booking['id']}/reschedule", json={"start_at": at(16)}, headers=binh)
    assert r.status_code == 404
