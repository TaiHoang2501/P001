"""Viewing pass (QR at the building's gate): only for confirmed viewings, checked live, never a login."""

from datetime import UTC, datetime, timedelta

import pytest

from src.db.models import Booking
from tests.helpers import CUSTOMER_AN, CUSTOMER_BINH, OWNER_TUAN, auth, first_free_slot

PROPERTY = 1  # Tuấn's listing


async def _confirmed(client) -> tuple[dict, dict, dict]:
    an = await auth(client, CUSTOMER_AN)
    slot = await first_free_slot(client, PROPERTY)
    booking = (
        await client.post("/api/v1/bookings", json={"property_id": PROPERTY, "slot_id": slot["id"]}, headers=an)
    ).json()
    tuan = await auth(client, OWNER_TUAN)
    return an, tuan, booking


@pytest.mark.asyncio
async def test_pass_only_after_the_seller_confirms(client):
    an, tuan, booking = await _confirmed(client)
    r = await client.get(f"/api/v1/bookings/{booking['id']}/pass", headers=an)
    assert r.status_code == 409  # still waiting for the seller

    await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=tuan)
    r = await client.get(f"/api/v1/bookings/{booking['id']}/pass", headers=an)
    assert r.status_code == 200, r.text

    # Another buyer cannot get this pass
    binh = await auth(client, CUSTOMER_BINH)
    assert (await client.get(f"/api/v1/bookings/{booking['id']}/pass", headers=binh)).status_code == 404


@pytest.mark.asyncio
async def test_scan_shows_the_home_and_names_but_no_phone(client, db):
    an, tuan, booking = await _confirmed(client)
    await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=tuan)
    token = (await client.get(f"/api/v1/bookings/{booking['id']}/pass", headers=an)).json()["token"]

    # The slot is in the future: not yet
    seen = (await client.get(f"/api/v1/passes/{token}")).json()
    assert seen["result"] == "too_early"
    assert seen["unit_code"] and seen["buyer_name"] == "Nguyễn Văn An" and seen["seller_name"]
    assert "phone" not in str(seen).lower()

    # Around the viewing time: valid
    row = db.get(Booking, booking["id"])
    length = row.end_at - row.start_at
    row.start_at = datetime.now(UTC) - timedelta(minutes=5)
    row.end_at = row.start_at + length
    db.commit()
    assert (await client.get(f"/api/v1/passes/{token}")).json()["result"] == "valid"

    # Long after: over
    row.start_at = datetime.now(UTC) - timedelta(hours=3)
    row.end_at = row.start_at + length
    db.commit()
    assert (await client.get(f"/api/v1/passes/{token}")).json()["result"] == "expired"


@pytest.mark.asyncio
async def test_cancelled_viewing_makes_the_old_qr_invalid(client):
    an, tuan, booking = await _confirmed(client)
    await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=tuan)
    token = (await client.get(f"/api/v1/bookings/{booking['id']}/pass", headers=an)).json()["token"]
    r = await client.post(f"/api/v1/bookings/{booking['id']}/cancel", headers=an)
    assert r.status_code == 200, r.text
    assert (await client.get(f"/api/v1/passes/{token}")).json()["result"] == "cancelled"


@pytest.mark.asyncio
async def test_pass_and_login_tokens_do_not_mix(client):
    an, tuan, booking = await _confirmed(client)
    await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=tuan)
    token = (await client.get(f"/api/v1/bookings/{booking['id']}/pass", headers=an)).json()["token"]

    # A pass is not a login...
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})).status_code == 401
    # ...and a login is not a pass
    login = an["Authorization"].removeprefix("Bearer ")
    assert (await client.get(f"/api/v1/passes/{login}")).json()["result"] == "invalid"
    assert (await client.get("/api/v1/passes/not-a-token")).json()["result"] == "invalid"
