import pytest
from sqlalchemy import select

from src.db.models import AuditLog
from tests.helpers import CUSTOMER_AN, CUSTOMER_BINH, OPERATOR, OWNER_LAN, OWNER_TUAN, auth, first_free_slot

TUAN_PROPERTY = 1


async def _request(client, headers, slot):
    return await client.post(
        "/api/v1/bookings",
        json={"property_id": slot["property_id"], "slot_id": slot["id"], "note": "Đi 2 người"},
        headers=headers,
    )


@pytest.mark.asyncio
async def test_happy_path_request_approve(client, db):
    an = await auth(client, CUSTOMER_AN)
    tuan = await auth(client, OWNER_TUAN)
    slot = await first_free_slot(client, TUAN_PROPERTY)

    r = await _request(client, an, slot)
    assert r.status_code == 201, r.text
    booking = r.json()
    assert booking["status"] == "REQUESTED"

    # Owner sees the request but not the customer's phone until confirming (spec §4.14)
    r = await client.get("/api/v1/owner/bookings", params={"status": "REQUESTED"}, headers=tuan)
    listed = next(b for b in r.json() if b["id"] == booking["id"])
    assert listed["customer_phone"] is None

    r = await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=tuan)
    assert r.status_code == 200
    assert r.json()["status"] == "CONFIRMED"
    assert r.json()["customer_phone"] == "0901111222"

    # Slot is now held: no longer offered as free
    free = (await client.get(f"/api/v1/properties/{TUAN_PROPERTY}/slots")).json()
    assert slot["id"] not in [s["id"] for s in free]

    actions = db.scalars(select(AuditLog.action).where(AuditLog.target_id == booking["id"])).all()
    assert actions == ["booking.request", "booking.approve"]


@pytest.mark.asyncio
async def test_second_customer_gets_slot_unavailable_with_alternatives(client):
    an = await auth(client, CUSTOMER_AN)
    binh = await auth(client, CUSTOMER_BINH)
    slot = await first_free_slot(client, TUAN_PROPERTY)

    assert (await _request(client, an, slot)).status_code == 201
    r = await _request(client, binh, slot)
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "SLOT_UNAVAILABLE"
    alternatives = err["details"]["free_slots"]
    assert alternatives and slot["id"] not in [s["id"] for s in alternatives]


@pytest.mark.asyncio
async def test_cancel_frees_the_slot(client):
    an = await auth(client, CUSTOMER_AN)
    binh = await auth(client, CUSTOMER_BINH)
    slot = await first_free_slot(client, TUAN_PROPERTY)

    booking = (await _request(client, an, slot)).json()
    r = await client.post(f"/api/v1/bookings/{booking['id']}/cancel", headers=an)
    assert r.json()["status"] == "CANCELLED"

    assert (await _request(client, binh, slot)).status_code == 201


@pytest.mark.asyncio
async def test_invalid_transitions_rejected(client):
    an = await auth(client, CUSTOMER_AN)
    tuan = await auth(client, OWNER_TUAN)
    slot = await first_free_slot(client, TUAN_PROPERTY)
    booking = (await _request(client, an, slot)).json()

    await client.post(f"/api/v1/bookings/{booking['id']}/cancel", headers=an)
    r = await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=tuan)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "STATE_CONFLICT"

    # Completing a future viewing is not allowed
    slot2 = await first_free_slot(client, TUAN_PROPERTY)
    b2 = (await _request(client, an, slot2)).json()
    await client.post(f"/api/v1/owner/bookings/{b2['id']}/approve", headers=tuan)
    r = await client.post(f"/api/v1/owner/bookings/{b2['id']}/complete", headers=tuan)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_only_the_property_owner_can_approve(client):
    an = await auth(client, CUSTOMER_AN)
    lan = await auth(client, OWNER_LAN)
    slot = await first_free_slot(client, TUAN_PROPERTY)
    booking = (await _request(client, an, slot)).json()

    # Another owner: not found (does not leak existence)
    assert (await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=lan)).status_code == 404
    # The customer: wrong role
    assert (await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=an)).status_code == 403


@pytest.mark.asyncio
async def test_customer_cannot_see_others_bookings(client):
    an = await auth(client, CUSTOMER_AN)
    binh = await auth(client, CUSTOMER_BINH)
    slot = await first_free_slot(client, TUAN_PROPERTY)
    booking = (await _request(client, an, slot)).json()

    assert (await client.get(f"/api/v1/bookings/{booking['id']}", headers=binh)).status_code == 404
    assert (await client.post(f"/api/v1/bookings/{booking['id']}/cancel", headers=binh)).status_code == 404
    assert (await client.get("/api/v1/bookings", headers=binh)).json() == []


@pytest.mark.asyncio
async def test_operator_can_cancel_as_fallback(client):
    an = await auth(client, CUSTOMER_AN)
    op = await auth(client, OPERATOR)
    slot = await first_free_slot(client, TUAN_PROPERTY)
    booking = (await _request(client, an, slot)).json()

    r = await client.post(f"/api/v1/operator/bookings/{booking['id']}/cancel", headers=op)
    assert r.status_code == 200
    assert r.json()["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_cannot_book_unapproved_listing(client):
    an = await auth(client, CUSTOMER_AN)
    r = await client.post("/api/v1/bookings", json={"property_id": 33, "slot_id": 1}, headers=an)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_owner_slot_management(client):
    tuan = await auth(client, OWNER_TUAN)
    slots = (await client.get(f"/api/v1/owner/properties/{TUAN_PROPERTY}/slots", headers=tuan)).json()
    first = slots[0]

    # Overlapping slot is refused
    r = await client.post(
        f"/api/v1/owner/properties/{TUAN_PROPERTY}/slots",
        json={"start_at": first["start_at"], "end_at": first["end_at"]},
        headers=tuan,
    )
    assert r.status_code == 409

    # A slot with an active booking cannot be deleted
    an = await auth(client, CUSTOMER_AN)
    await _request(client, an, first)
    assert (await client.delete(f"/api/v1/owner/slots/{first['id']}", headers=tuan)).status_code == 409
    assert (await client.delete(f"/api/v1/owner/slots/{slots[1]['id']}", headers=tuan)).status_code == 204
