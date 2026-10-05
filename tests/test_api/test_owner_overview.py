"""The seller's dashboard numbers: only their own listings, requests waiting for them, AI exposure."""

import pytest

from tests.helpers import CUSTOMER_AN, OWNER_LAN, OWNER_TUAN, auth, first_free_slot


@pytest.mark.asyncio
async def test_overview_counts_requests_for_own_listings_only(client):
    tuan = await auth(client, OWNER_TUAN)
    before = (await client.get("/api/v1/owner/overview", headers=tuan)).json()
    assert before["response_hours"] >= 1
    stats = {s["property_id"]: s for s in before["properties"]}
    own = (await client.get("/api/v1/owner/properties", headers=tuan)).json()
    assert set(stats) == {p["id"] for p in own}

    home = next(p["id"] for p in own if p["status"] == "AVAILABLE")
    slot = await first_free_slot(client, home)
    an = await auth(client, CUSTOMER_AN)
    r = await client.post("/api/v1/bookings", json={"property_id": home, "start_at": slot["start_at"]}, headers=an)
    assert r.status_code == 201, r.text

    after = {
        s["property_id"]: s for s in (await client.get("/api/v1/owner/overview", headers=tuan)).json()["properties"]
    }
    assert after[home]["viewing_requests"] == stats[home]["viewing_requests"] + 1
    assert after[home]["pending_requests"] == stats[home]["pending_requests"] + 1

    # Another seller does not see this home
    lan = await auth(client, OWNER_LAN)
    others = (await client.get("/api/v1/owner/overview", headers=lan)).json()["properties"]
    assert home not in {s["property_id"] for s in others}


@pytest.mark.asyncio
async def test_overview_is_for_sellers(client):
    assert (await client.get("/api/v1/owner/overview")).status_code == 401
    an = await auth(client, CUSTOMER_AN)
    assert (await client.get("/api/v1/owner/overview", headers=an)).status_code == 403
