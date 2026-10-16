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

    # Privacy level 1 (AC-03): the owner sees a buyer reference and name, never the phone
    r = await client.get("/api/v1/owner/bookings", params={"status": "REQUESTED"}, headers=tuan)
    listed = next(b for b in r.json() if b["id"] == booking["id"])
    assert listed["buyer_ref"] == f"Buyer #{booking['customer_id']}"
    assert listed["customer_name"]
    assert listed["customer_phone"] is None

    r = await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=tuan)
    assert r.status_code == 200
    assert r.json()["status"] == "CONFIRMED"
    # Confirming the viewing (level 2) still does not share contact details
    assert r.json()["customer_phone"] is None

    # Slot is now held: no longer offered as free
    free = (await client.get(f"/api/v1/properties/{TUAN_PROPERTY}/slots")).json()
    assert slot["id"] not in [s["id"] for s in free]

    actions = db.scalars(
        select(AuditLog.action).where(AuditLog.target_type == "booking", AuditLog.target_id == booking["id"])
    ).all()
    assert actions == ["booking.request", "booking.approve"]


@pytest.mark.asyncio
async def test_several_buyers_may_ask_for_one_time_and_the_owner_chooses(client):
    an = await auth(client, CUSTOMER_AN)
    binh = await auth(client, CUSTOMER_BINH)
    tuan = await auth(client, OWNER_TUAN)
    slot = await first_free_slot(client, TUAN_PROPERTY)

    mine = (await _request(client, an, slot)).json()
    r = await _request(client, binh, slot)
    assert r.status_code == 201, r.text  # not answered yet: Bình may ask for the same time
    theirs = r.json()
    pending = (await client.get("/api/v1/owner/bookings", params={"status": "REQUESTED"}, headers=tuan)).json()
    assert {mine["id"], theirs["id"]} <= {b["id"] for b in pending}

    # The owner receives Bình: An's overlapping request is closed and the assistant tells An
    r = await client.post(f"/api/v1/owner/bookings/{theirs['id']}/approve", headers=tuan)
    assert r.json()["status"] == "CONFIRMED", r.text
    closed = (await client.get(f"/api/v1/bookings/{mine['id']}", headers=an)).json()
    assert closed["status"] == "REJECTED"
    assert "lịch xem khác" in closed["rejection_reason"]
    notes = (await client.get("/api/v1/notifications", headers=an)).json()
    assert [n["booking_id"] for n in notes if n["event_type"] == "VIEWING_SUPERSEDED"] == [mine["id"]]
    latest = (await client.get("/api/v1/bookings/activity", headers=an)).json()[0]
    assert (latest["kind"], latest["by"], latest["booking_id"]) == ("SUPERSEDED", "BOOKINGBOT", mine["id"])

    # Too late to receive An at that time, and nobody can ask for it any more (other times are offered)
    assert (await client.post(f"/api/v1/owner/bookings/{mine['id']}/approve", headers=tuan)).status_code == 409
    r = await _request(client, an, slot)
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "SLOT_UNAVAILABLE"
    assert err["details"]["free_slots"] and slot["id"] not in [s["id"] for s in err["details"]["free_slots"]]


@pytest.mark.asyncio
async def test_owner_is_not_double_booked_across_their_homes(client):
    an = await auth(client, CUSTOMER_AN)
    binh = await auth(client, CUSTOMER_BINH)
    tuan = await auth(client, OWNER_TUAN)
    first = await first_free_slot(client, TUAN_PROPERTY)
    # Tuấn's other home has a slot at the same time
    other_home = 3
    same_time = [
        s
        for s in (await client.get(f"/api/v1/properties/{other_home}/slots")).json()
        if s["start_at"] == first["start_at"]
    ]
    assert same_time, "the demo data gives both homes the same slots"

    mine = (await _request(client, an, first)).json()
    theirs = (await _request(client, binh, same_time[0])).json()
    r = await client.post(f"/api/v1/owner/bookings/{mine['id']}/approve", headers=tuan)
    assert r.json()["status"] == "CONFIRMED", r.text

    # Bình's request on the other home at that time is closed; that time is no longer offered there
    assert (await client.get(f"/api/v1/bookings/{theirs['id']}", headers=binh)).json()["status"] == "REJECTED"
    offered = (await client.get(f"/api/v1/properties/{other_home}/slots")).json()
    assert first["start_at"] not in [s["start_at"] for s in offered]


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

    # A reason is required: both sides read it
    r = await client.post(f"/api/v1/operator/bookings/{booking['id']}/cancel", json={"reason": "  "}, headers=op)
    assert r.status_code == 422
    r = await client.post(
        f"/api/v1/operator/bookings/{booking['id']}/cancel",
        json={"reason": "Chủ căn báo căn đang sửa chữa"},
        headers=op,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "CANCELLED"
    # The owner is told it was the investor, not the buyer
    tuan = await auth(client, OWNER_TUAN)
    note = next(
        n
        for n in (await client.get("/api/v1/notifications", headers=tuan)).json()
        if n["event_type"] == "VIEWING_CANCELLED"
    )
    assert note["body"].startswith("Chủ đầu tư đã hủy") and "đang sửa chữa" in note["body"]


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


@pytest.mark.asyncio
async def test_activity_history_keeps_every_important_event(client):
    an = await auth(client, CUSTOMER_AN)
    binh = await auth(client, CUSTOMER_BINH)
    tuan = await auth(client, OWNER_TUAN)
    slot = await first_free_slot(client, TUAN_PROPERTY)
    booking = (await _request(client, an, slot)).json()
    bid = booking["id"]

    await client.post(f"/api/v1/owner/bookings/{bid}/approve", headers=tuan)
    other = await first_free_slot(client, TUAN_PROPERTY)
    r = await client.post(f"/api/v1/bookings/{bid}/reschedule", json={"start_at": other["start_at"]}, headers=an)
    assert r.json()["status"] == "RESCHEDULE_REQUESTED", r.text
    await client.post(f"/api/v1/owner/bookings/{bid}/reject", json={"reason": "Hôm đó tôi bận"}, headers=tuan)
    await client.post(f"/api/v1/bookings/{bid}/cancel", headers=an)

    r = await client.get("/api/v1/bookings/activity", headers=an)
    assert r.status_code == 200, r.text
    events = [e for e in r.json() if e["booking_id"] == bid]
    # Newest first, who did what
    assert [(e["kind"], e["by"]) for e in events] == [
        ("CANCELLED", "BUYER"),
        ("RESCHEDULE_DECLINED", "OWNER"),
        ("RESCHEDULE_REQUESTED", "BUYER"),
        ("CONFIRMED", "OWNER"),
        ("REQUESTED", "BUYER"),
    ]
    assert events[1]["reason"] == "Hôm đó tôi bận"
    assert events[2]["start_at"][:16] == other["start_at"][:16]  # the new time asked for
    assert all(e["booking_status"] == "CANCELLED" and e["deal_code"] == booking["deal_code"] for e in events)

    # Another buyer sees none of it; sellers have their own pages
    assert all(e["booking_id"] != bid for e in (await client.get("/api/v1/bookings/activity", headers=binh)).json())
    assert (await client.get("/api/v1/bookings/activity", headers=tuan)).status_code == 403


@pytest.mark.asyncio
async def test_contact_details_in_the_note_are_hidden_from_the_owner(client):
    an = await auth(client, CUSTOMER_AN)
    tuan = await auth(client, OWNER_TUAN)
    slot = await first_free_slot(client, TUAN_PROPERTY)
    r = await client.post(
        "/api/v1/bookings",
        json={"property_id": TUAN_PROPERTY, "slot_id": slot["id"], "note": "Gọi em 0902222333 hoặc an@gmail.com"},
        headers=an,
    )
    assert r.status_code == 201, r.text
    listed = next(
        b for b in (await client.get("/api/v1/owner/bookings", headers=tuan)).json() if b["id"] == r.json()["id"]
    )
    assert "0902222333" not in listed["customer_note"] and "@" not in listed["customer_note"]
