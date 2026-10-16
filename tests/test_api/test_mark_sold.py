"""Marking a home sold closes every viewing still ahead of it and tells those buyers; a viewing that already took
place stays for its outcome (no more "resolve the bookings first" dead end)."""

from datetime import UTC, datetime, timedelta

import pytest

from src.db.models import Booking, BookingStatus, Deal, DealStatus, PropertyHold
from tests.helpers import CUSTOMER_AN, CUSTOMER_BINH, OWNER_TUAN, auth, otp_auth

TUAN_PROPERTY = 1


async def _book(client, headers, slot):
    r = await client.post(
        "/api/v1/bookings", json={"property_id": TUAN_PROPERTY, "slot_id": slot["id"]}, headers=headers
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.asyncio
async def test_sold_closes_viewings_ahead_and_tells_the_buyers(client, db):
    an = await auth(client, CUSTOMER_AN)
    binh = await auth(client, CUSTOMER_BINH)
    cuong = await otp_auth(client, "0938000111", full_name="Lê Văn Cường", role="CUSTOMER")
    tuan = await auth(client, OWNER_TUAN)
    slots = (await client.get(f"/api/v1/properties/{TUAN_PROPERTY}/slots")).json()
    assert len(slots) >= 5

    # Cường viewed on Monday 9:00 (the buyer the home is sold to): confirmed, then its time passed
    early = await _book(client, cuong, slots[0])
    assert (await client.post(f"/api/v1/owner/bookings/{early['id']}/approve", headers=tuan)).status_code == 200
    past = db.get(Booking, early["id"])
    past.start_at, past.end_at = datetime.now(UTC) - timedelta(hours=3), datetime.now(UTC) - timedelta(hours=2)
    db.commit()
    # Bình has a confirmed viewing later in the week; An's request is still unanswered
    later = await _book(client, binh, slots[2])
    assert (await client.post(f"/api/v1/owner/bookings/{later['id']}/approve", headers=tuan)).status_code == 200
    pending = await _book(client, an, slots[4])

    # Sold to Cường, the Monday buyer
    cuong_id = db.get(Booking, early["id"]).customer_id
    r = await client.post(f"/api/v1/owner/properties/{TUAN_PROPERTY}/sold", json={"buyer_id": cuong_id}, headers=tuan)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "SOLD"

    db.expire_all()
    assert db.get(Booking, pending["id"]).status == BookingStatus.REJECTED
    assert db.get(Booking, pending["id"]).rejection_reason == "Căn đã được bán"
    assert db.get(Booking, later["id"]).status == BookingStatus.CANCELLED
    assert db.query(PropertyHold).filter_by(booking_id=later["id"], status="ACTIVE").count() == 0
    # The viewing that took place stays, waiting for its outcome
    assert db.get(Booking, early["id"]).status == BookingStatus.CONFIRMED
    # Those buyers' deals are over; Cường's is not
    deals = {b["id"]: db.get(Deal, db.get(Booking, b["id"]).deal_id).status for b in (pending, later, early)}
    assert deals[pending["id"]] == deals[later["id"]] == DealStatus.CLOSED
    assert deals[early["id"]] != DealStatus.CLOSED

    for headers, booking in ((an, pending), (binh, later)):
        notes = (await client.get("/api/v1/notifications", headers=headers)).json()
        sold = [n for n in notes if n["event_type"] == "PROPERTY_SOLD"]
        assert [n["booking_id"] for n in sold] == [booking["id"]]
        assert "đã bán" in sold[0]["body"]
    notes = (await client.get("/api/v1/notifications", headers=cuong)).json()
    assert not [n for n in notes if n["event_type"] == "PROPERTY_SOLD"]

    # Nobody can ask to view it any more
    r = await client.post(
        "/api/v1/bookings", json={"property_id": TUAN_PROPERTY, "slot_id": slots[6]["id"]}, headers=an
    )
    assert r.status_code in (404, 409, 422)


@pytest.mark.asyncio
async def test_sold_without_viewings_still_works(client):
    tuan = await auth(client, OWNER_TUAN)
    r = await client.post(f"/api/v1/owner/properties/{TUAN_PROPERTY}/sold", headers=tuan)
    assert r.status_code == 200 and r.json()["status"] == "SOLD"


@pytest.mark.asyncio
async def test_sold_home_drops_reminders_and_takes_no_new_times(client, db):
    from src.db.models import Notification, NotificationStatus

    binh = await auth(client, CUSTOMER_BINH)
    tuan = await auth(client, OWNER_TUAN)
    slots = (await client.get(f"/api/v1/properties/{TUAN_PROPERTY}/slots")).json()
    booking = await _book(client, binh, slots[0])
    assert (await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=tuan)).status_code == 200

    def pending():
        return (
            db.query(Notification)
            .filter(Notification.booking_id == booking["id"], Notification.status == NotificationStatus.PENDING)
            .count()
        )

    assert pending() > 0  # T-24h / T-2h reminders

    assert (await client.post(f"/api/v1/owner/properties/{TUAN_PROPERTY}/sold", headers=tuan)).status_code == 200
    db.expire_all()
    assert pending() == 0
    r = await client.post(
        f"/api/v1/bookings/{booking['id']}/reschedule", json={"start_at": slots[2]["start_at"]}, headers=binh
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_no_new_time_once_the_viewing_time_has_come(client, db):
    binh = await auth(client, CUSTOMER_BINH)
    tuan = await auth(client, OWNER_TUAN)
    slots = (await client.get(f"/api/v1/properties/{TUAN_PROPERTY}/slots")).json()
    booking = await _book(client, binh, slots[0])
    assert (await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=tuan)).status_code == 200
    past = db.get(Booking, booking["id"])
    past.start_at, past.end_at = datetime.now(UTC) - timedelta(hours=3), datetime.now(UTC) - timedelta(hours=2)
    db.commit()
    r = await client.post(
        f"/api/v1/bookings/{booking['id']}/reschedule", json={"start_at": slots[2]["start_at"]}, headers=binh
    )
    assert r.status_code == 422 and r.json()["error"]["details"]["reason"] == "VIEWING_STARTED", r.text


async def _viewed(client, db, buyer, tuan, slot) -> dict:
    """A viewing of Tuấn's home that took place and was recorded as done."""
    booking = await _book(client, buyer, slot)
    assert (await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=tuan)).status_code == 200
    row = db.get(Booking, booking["id"])
    row.start_at, row.end_at = datetime.now(UTC) - timedelta(hours=3), datetime.now(UTC) - timedelta(hours=2)
    db.commit()
    assert (await client.post(f"/api/v1/owner/bookings/{booking['id']}/complete", headers=tuan)).status_code == 200
    return booking


@pytest.mark.asyncio
async def test_only_the_buyer_it_was_sold_to_keeps_interest(client, db):
    """A and B both viewed it. Before the sale both may say "Quan tâm"; sold to A: only A still can, B is told."""
    a = await otp_auth(client, "0938000111", full_name="Người Mua A", role="CUSTOMER")
    b = await auth(client, CUSTOMER_AN)
    tuan = await auth(client, OWNER_TUAN)
    slots = (await client.get(f"/api/v1/properties/{TUAN_PROPERTY}/slots")).json()
    seen_a = await _viewed(client, db, a, tuan, slots[0])
    seen_b = await _viewed(client, db, b, tuan, slots[2])
    a_id = db.get(Booking, seen_a["id"]).customer_id

    # A buyer who never viewed it cannot be named
    binh_id = 2
    r = await client.post(f"/api/v1/owner/properties/{TUAN_PROPERTY}/sold", json={"buyer_id": binh_id}, headers=tuan)
    assert r.status_code == 422 and r.json()["error"]["details"]["reason"] == "BUYER_DID_NOT_VIEW"

    r = await client.post(f"/api/v1/owner/properties/{TUAN_PROPERTY}/sold", json={"buyer_id": a_id}, headers=tuan)
    assert r.status_code == 200, r.text

    # B: told, deal closed, no "Quan tâm" any more
    bk = (await client.get(f"/api/v1/bookings/{seen_b['id']}", headers=b)).json()
    assert bk["sold_to_other"] is True and bk["deal_status"] == "CLOSED"
    r = await client.post(f"/api/v1/bookings/{seen_b['id']}/feedback", json={"interest": "INTERESTED"}, headers=b)
    assert r.status_code == 409
    notes = (await client.get("/api/v1/notifications", headers=b)).json()
    assert [n["title"] for n in notes if n["event_type"] == "PROPERTY_SOLD"] == ["Căn bạn đã xem đã được bán"]

    # A: the buyer it went to, still says "Quan tâm"
    ak = (await client.get(f"/api/v1/bookings/{seen_a['id']}", headers=a)).json()
    assert ak["sold_to_other"] is False and ak["deal_status"] == "VIEWED"
    r = await client.post(f"/api/v1/bookings/{seen_a['id']}/feedback", json={"interest": "INTERESTED"}, headers=a)
    assert r.status_code == 200, r.text
    notes = (await client.get("/api/v1/notifications", headers=a)).json()
    assert not [n for n in notes if n["event_type"] == "PROPERTY_SOLD"]


@pytest.mark.asyncio
async def test_sold_outside_bookingbot_tells_every_viewer(client, db):
    b = await auth(client, CUSTOMER_AN)
    tuan = await auth(client, OWNER_TUAN)
    slots = (await client.get(f"/api/v1/properties/{TUAN_PROPERTY}/slots")).json()
    seen = await _viewed(client, db, b, tuan, slots[0])
    assert (await client.post(f"/api/v1/owner/properties/{TUAN_PROPERTY}/sold", headers=tuan)).status_code == 200
    bk = (await client.get(f"/api/v1/bookings/{seen['id']}", headers=b)).json()
    assert bk["sold_to_other"] is True


@pytest.mark.asyncio
async def test_operator_takes_down_a_live_listing(client, db):
    from tests.helpers import OPERATOR

    an = await auth(client, CUSTOMER_AN)
    tuan = await auth(client, OWNER_TUAN)
    op = await auth(client, OPERATOR)
    slots = (await client.get(f"/api/v1/properties/{TUAN_PROPERTY}/slots")).json()
    booking = await _book(client, an, slots[0])

    r = await client.post(
        f"/api/v1/operator/properties/{TUAN_PROPERTY}/take-down", json={"reason": "Ảnh không phải căn này"}, headers=op
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "REJECTED" and r.json()["rejection_reason"] == "Ảnh không phải căn này"
    db.expire_all()
    assert db.get(Booking, booking["id"]).status == BookingStatus.REJECTED
    # The seller sees why; the buyer's request is closed and they are told
    assert (await client.get(f"/api/v1/properties/{TUAN_PROPERTY}")).status_code == 404
    notes = (await client.get("/api/v1/notifications", headers=tuan)).json()
    assert any(n["event_type"] == "LISTING_TAKEN_DOWN" for n in notes)
    notes = (await client.get("/api/v1/notifications", headers=an)).json()
    assert any(n["event_type"] == "VIEWING_CANCELLED" and n["booking_id"] == booking["id"] for n in notes)
    # Only live listings
    r = await client.post(
        f"/api/v1/operator/properties/{TUAN_PROPERTY}/take-down", json={"reason": "Ảnh không phải căn này"}, headers=op
    )
    assert r.status_code == 409
