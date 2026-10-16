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

    r = await client.post(f"/api/v1/owner/properties/{TUAN_PROPERTY}/sold", headers=tuan)
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
