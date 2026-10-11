"""The owner cannot take a request: they offer other times of their own, or close the time they are busy."""

from datetime import datetime

import pytest

from src.db.models import AvailabilitySlot, Notification
from tests.helpers import CUSTOMER_AN, OWNER_TUAN, auth

PROPERTY = 1  # Tuấn's listing


async def _request(client) -> tuple[dict, dict, dict, list[dict]]:
    an = await auth(client, CUSTOMER_AN)
    tuan = await auth(client, OWNER_TUAN)
    slots = (await client.get(f"/api/v1/properties/{PROPERTY}/slots")).json()
    booking = (
        await client.post("/api/v1/bookings", json={"property_id": PROPERTY, "slot_id": slots[0]["id"]}, headers=an)
    ).json()
    return an, tuan, booking, slots[1:]


@pytest.mark.asyncio
async def test_owner_suggests_other_times_and_the_buyer_books_one(client, db):
    an, tuan, booking, others = await _request(client)
    offered = [others[0]["start_at"], others[1]["start_at"]]
    r = await client.post(
        f"/api/v1/owner/bookings/{booking['id']}/reject",
        json={"reason": "Giờ đó tôi bận, mời anh chọn giờ khác", "suggested_starts": offered},
        headers=tuan,
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "REJECTED"

    mine = (await client.get(f"/api/v1/bookings/{booking['id']}", headers=an)).json()
    assert [t[:16] for t in mine["suggested_starts"]] == [t[:16] for t in offered]
    note = db.query(Notification).filter_by(user_id=booking["customer_id"], event_type="VIEWING_TIMES_SUGGESTED").one()
    assert note.payload["property_id"] == PROPERTY and len(note.payload["suggested_starts"]) == 2

    # One tap: a new request at the suggested time, same deal
    r = await client.post("/api/v1/bookings", json={"property_id": PROPERTY, "start_at": offered[0]}, headers=an)
    assert r.status_code == 201, r.text
    assert (r.json()["status"], r.json()["deal_id"]) == ("REQUESTED", booking["deal_id"])


@pytest.mark.asyncio
async def test_suggested_times_must_be_the_owners_free_times(client):
    _, tuan, booking, _ = await _request(client)
    r = await client.post(
        f"/api/v1/owner/bookings/{booking['id']}/reject",
        json={"reason": "Mời chọn giờ khác", "suggested_starts": ["2031-01-01T03:00:00+07:00"]},
        headers=tuan,
    )
    assert r.status_code == 422
    # At most three
    r = await client.post(
        f"/api/v1/owner/bookings/{booking['id']}/reject",
        json={"reason": "Mời chọn giờ khác", "suggested_starts": [booking["start_at"]] * 4},
        headers=tuan,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_busy_owner_closes_the_declined_time(client, db):
    _, tuan, booking, _ = await _request(client)
    r = await client.post(
        f"/api/v1/owner/bookings/{booking['id']}/reject",
        json={"reason": "Khung giờ này tôi bận", "close_time": True},
        headers=tuan,
    )
    assert r.status_code == 200, r.text
    db.expire_all()
    start, end = datetime.fromisoformat(booking["start_at"]), datetime.fromisoformat(booking["end_at"])
    open_at_that_time = (
        db.query(AvailabilitySlot)
        .filter(
            AvailabilitySlot.property_id == PROPERTY,
            AvailabilitySlot.start_at < end,
            AvailabilitySlot.end_at > start,
        )
        .count()
    )
    assert open_at_that_time == 0
    # Nobody is offered that time any more
    starts = [s["start_at"] for s in (await client.get(f"/api/v1/properties/{PROPERTY}/slots")).json()]
    assert booking["start_at"] not in starts
