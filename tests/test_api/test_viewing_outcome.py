"""After the viewing time: the owner records it, the buyer says how they found the home or disagrees,
the operator settles a disagreement, and viewings nobody recorded close without blaming anyone."""

from datetime import UTC, datetime, timedelta

import pytest

from src.db.models import Booking, Notification
from src.services import viewing_outcome_service
from tests.helpers import CUSTOMER_AN, OPERATOR, OWNER_TUAN, auth, first_free_slot

PROPERTY = 1  # Tuấn's listing


async def _past_viewing(client, db, hours_ago: float = 1) -> tuple[dict, dict, dict]:
    """A confirmed viewing whose time is over (moved into the past)."""
    an = await auth(client, CUSTOMER_AN)
    tuan = await auth(client, OWNER_TUAN)
    slot = await first_free_slot(client, PROPERTY)
    booking = (
        await client.post("/api/v1/bookings", json={"property_id": PROPERTY, "slot_id": slot["id"]}, headers=an)
    ).json()
    await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=tuan)
    row = db.get(Booking, booking["id"])
    length = row.end_at - row.start_at
    row.end_at = datetime.now(UTC) - timedelta(hours=hours_ago)
    row.start_at = row.end_at - length
    db.commit()
    return an, tuan, booking


def _events(db, user_email_or_id) -> list[str]:
    db.expire_all()
    return [n.event_type for n in db.query(Notification).filter_by(user_id=user_email_or_id)]


@pytest.mark.asyncio
async def test_owner_records_the_viewing_and_the_buyer_is_interested(client, db):
    an, tuan, booking = await _past_viewing(client, db)
    r = await client.post(f"/api/v1/owner/bookings/{booking['id']}/complete", headers=tuan)
    assert r.json()["status"] == "COMPLETED"

    mine = (await client.get(f"/api/v1/bookings/{booking['id']}", headers=an)).json()
    assert (mine["status"], mine["deal_status"]) == ("COMPLETED", "VIEWED")  # asked how it went
    assert "VIEWING_COMPLETED" in _events(db, booking["customer_id"])

    r = await client.post(f"/api/v1/bookings/{booking['id']}/feedback", json={"interest": "INTERESTED"}, headers=an)
    assert r.status_code == 200, r.text
    assert r.json()["deal_status"] == "INTERESTED"
    owner_id = db.get(Booking, booking["id"]).owner_id
    assert "BUYER_INTERESTED" in _events(db, owner_id)
    # Asked once
    again = await client.post(
        f"/api/v1/bookings/{booking['id']}/feedback", json={"interest": "NOT_SUITABLE"}, headers=an
    )
    assert again.status_code == 409
    latest = (await client.get("/api/v1/bookings/activity", headers=an)).json()[0]
    assert (latest["kind"], latest["booking_id"]) == ("INTERESTED", booking["id"])


@pytest.mark.asyncio
async def test_not_suitable_closes_the_deal_and_the_assistant_offers_more(client, db):
    an, tuan, booking = await _past_viewing(client, db)
    await client.post(f"/api/v1/owner/bookings/{booking['id']}/complete", headers=tuan)
    r = await client.post(
        f"/api/v1/bookings/{booking['id']}/feedback", json={"interest": "NOT_SUITABLE", "note": "Hơi tối"}, headers=an
    )
    assert r.json()["deal_status"] == "CLOSED"
    assert "AGENT_FOLLOWUP" in _events(db, booking["customer_id"])


@pytest.mark.asyncio
async def test_no_show_disputed_then_settled_by_the_operator(client, db):
    an, tuan, booking = await _past_viewing(client, db)
    r = await client.post(f"/api/v1/owner/bookings/{booking['id']}/no-show", headers=tuan)
    assert r.json()["status"] == "NO_SHOW"
    assert "VIEWING_NO_SHOW" in _events(db, booking["customer_id"])
    # No "how was it" for a viewing that did not happen
    r = await client.post(f"/api/v1/bookings/{booking['id']}/feedback", json={"interest": "INTERESTED"}, headers=an)
    assert r.status_code == 409

    r = await client.post(
        f"/api/v1/bookings/{booking['id']}/dispute", json={"claim": "I_CAME", "note": "Tôi tới đúng 14h"}, headers=an
    )
    assert r.status_code == 200, r.text
    assert (
        await client.post(f"/api/v1/bookings/{booking['id']}/dispute", json={"claim": "I_CAME"}, headers=an)
    ).status_code == 409

    op = await auth(client, OPERATOR)
    case = next(
        e
        for e in (await client.get("/api/v1/operator/escalations", headers=op)).json()
        if e["type"] == "VIEWING_DISPUTE"
    )
    assert case["booking_id"] == booking["id"] and case["context"]["buyer_no_shows"] >= 1
    r = await client.post(
        f"/api/v1/operator/escalations/{case['id']}/viewing-outcome",
        json={"outcome": "VIEWED", "note": "Bảo vệ toà nhà xác nhận khách có đến"},
        headers=op,
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "COMPLETED"
    mine = (await client.get(f"/api/v1/bookings/{booking['id']}", headers=an)).json()
    assert mine["deal_status"] == "VIEWED"  # now the buyer can say how it went
    assert "VIEWING_OUTCOME_RECORDED" in _events(db, booking["customer_id"])


@pytest.mark.asyncio
async def test_owner_absent_reported_by_the_buyer(client, db):
    an, tuan, booking = await _past_viewing(client, db)
    # Not before the viewing time is over
    r = await client.post(f"/api/v1/bookings/{booking['id']}/dispute", json={"claim": "I_CAME"}, headers=an)
    assert r.status_code == 409
    r = await client.post(f"/api/v1/bookings/{booking['id']}/dispute", json={"claim": "OWNER_ABSENT"}, headers=an)
    assert r.status_code == 200, r.text

    op = await auth(client, OPERATOR)
    case = next(
        e
        for e in (await client.get("/api/v1/operator/escalations", headers=op)).json()
        if e["type"] == "VIEWING_DISPUTE"
    )
    r = await client.post(
        f"/api/v1/operator/escalations/{case['id']}/viewing-outcome",
        json={"outcome": "OWNER_ABSENT", "note": "Chủ căn xác nhận có việc đột xuất"},
        headers=op,
    )
    assert r.json()["status"] == "OWNER_ABSENT"
    latest = (await client.get("/api/v1/bookings/activity", headers=an)).json()[0]
    assert (latest["kind"], latest["by"]) == ("OWNER_ABSENT", "BOOKINGBOT")


@pytest.mark.asyncio
async def test_owner_reminded_once_then_unrecorded_viewing_closes(client, db):
    _, _, recent = await _past_viewing(client, db, hours_ago=1)
    viewing_outcome_service.remind_and_close(db)
    viewing_outcome_service.remind_and_close(db)
    owner_id = db.get(Booking, recent["id"]).owner_id
    assert _events(db, owner_id).count("VIEWING_OUTCOME_DUE") == 1

    # Nobody recorded it for more than 48 hours: closed, nobody blamed
    row = db.get(Booking, recent["id"])
    row.end_at = datetime.now(UTC) - timedelta(hours=49)
    row.start_at = row.end_at - timedelta(minutes=30)
    db.commit()
    viewing_outcome_service.remind_and_close(db)
    db.expire_all()
    assert db.get(Booking, recent["id"]).status.value == "UNREPORTED"


@pytest.mark.asyncio
async def test_no_show_only_after_the_viewing_time(client, db):
    an = await auth(client, CUSTOMER_AN)
    tuan = await auth(client, OWNER_TUAN)
    slot = await first_free_slot(client, PROPERTY)
    booking = (
        await client.post("/api/v1/bookings", json={"property_id": PROPERTY, "slot_id": slot["id"]}, headers=an)
    ).json()
    await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=tuan)
    assert (await client.post(f"/api/v1/owner/bookings/{booking['id']}/no-show", headers=tuan)).status_code == 422
