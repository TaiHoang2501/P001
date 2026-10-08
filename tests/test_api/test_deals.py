"""Deal ID on every viewing request (spec §4.9, AC-02, AC-09) and level-1 privacy (AC-03)."""

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.db.models import BuyerAvailability, BuyerProfile
from tests.helpers import CUSTOMER_AN, CUSTOMER_BINH, OPERATOR, OWNER_LAN, OWNER_TUAN, auth, first_free_slot

VN = ZoneInfo("Asia/Ho_Chi_Minh")
TUAN_PROPERTY = 1
SAT = datetime(2030, 1, 5, tzinfo=VN)


def at(hour: float) -> str:
    return (SAT + timedelta(hours=hour)).isoformat()


async def _book_slot(client, headers, property_id: int = TUAN_PROPERTY):
    slot = await first_free_slot(client, property_id)
    return await client.post(
        "/api/v1/bookings", json={"property_id": property_id, "slot_id": slot["id"]}, headers=headers
    )


@pytest.mark.asyncio
async def test_ac09_viewing_request_creates_deal(client):
    an = await auth(client, CUSTOMER_AN)
    r = await _book_slot(client, an)
    assert r.status_code == 201, r.text
    booking = r.json()
    assert re.fullmatch(r"VH-\d{4}-\d{5}", booking["deal_code"])

    deal = (await client.get(f"/api/v1/deals/{booking['deal_id']}", headers=an)).json()
    assert deal["code"] == booking["deal_code"]
    assert deal["status"] == "VIEWING_REQUESTED"
    assert deal["seller_id"] == 4
    assert deal["disclosure_level"] == 1


@pytest.mark.asyncio
async def test_ac02_seller_receives_request_linked_to_deal(client):
    an = await auth(client, CUSTOMER_AN)
    booking = (await _book_slot(client, an)).json()

    tuan = await auth(client, OWNER_TUAN)
    deals = (await client.get("/api/v1/deals", headers=tuan)).json()
    assert [d["id"] for d in deals] == [booking["deal_id"]]
    requests = (await client.get("/api/v1/owner/bookings", headers=tuan)).json()
    assert requests[0]["deal_code"] == booking["deal_code"]


@pytest.mark.asyncio
async def test_ac03_seller_sees_name_and_budget_but_no_phone(client, db):
    profile = db.get(BuyerProfile, 1)
    profile.budget_min_vnd, profile.budget_max_vnd = 4_000_000_000, 5_000_000_000
    db.commit()
    an = await auth(client, CUSTOMER_AN)
    await _book_slot(client, an)

    tuan = await auth(client, OWNER_TUAN)
    seen = (await client.get("/api/v1/owner/bookings", headers=tuan)).json()[0]
    assert seen["buyer_budget_min_vnd"] == 4_000_000_000
    assert seen["buyer_budget_max_vnd"] == 5_000_000_000
    assert seen["customer_name"] == "Nguyễn Văn An"
    assert seen["customer_phone"] is None

    # The buyer sees their own details; the operator sees everything
    assert (await client.get("/api/v1/bookings", headers=an)).json()[0]["customer_phone"] == "0901111222"
    op = await auth(client, OPERATOR)
    assert (await client.get("/api/v1/operator/bookings", headers=op)).json()[0]["customer_name"] == "Nguyễn Văn An"


@pytest.mark.asyncio
async def test_seller_never_sees_the_phone_before_level_3(client):
    an = await auth(client, CUSTOMER_AN)
    booking = (await _book_slot(client, an)).json()
    tuan = await auth(client, OWNER_TUAN)

    # Requested, then confirmed: the name all along, the phone never
    seen = (await client.get("/api/v1/owner/bookings", headers=tuan)).json()[0]
    assert seen["customer_name"] == "Nguyễn Văn An"
    assert seen["customer_phone"] is None
    r = await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=tuan)
    assert r.json()["customer_name"] == "Nguyễn Văn An"
    assert r.json()["customer_phone"] is None


@pytest.mark.asyncio
async def test_rebooking_after_cancel_reuses_the_same_deal(client):
    an = await auth(client, CUSTOMER_AN)
    first = (await _book_slot(client, an)).json()
    r = await client.post(f"/api/v1/bookings/{first['id']}/cancel", headers=an)
    assert r.status_code == 200
    assert (await client.get(f"/api/v1/deals/{first['deal_id']}", headers=an)).json()["status"] == "MATCHED"

    second = (await _book_slot(client, an)).json()
    assert second["deal_id"] == first["deal_id"]


@pytest.mark.asyncio
async def test_one_active_viewing_per_deal(client):
    an = await auth(client, CUSTOMER_AN)
    assert (await _book_slot(client, an)).status_code == 201
    r = await _book_slot(client, an)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "STATE_CONFLICT"


@pytest.mark.asyncio
async def test_different_buyers_get_different_deals(client):
    an = await auth(client, CUSTOMER_AN)
    binh = await auth(client, CUSTOMER_BINH)
    a = (await _book_slot(client, an)).json()
    b = (await _book_slot(client, binh)).json()
    assert a["deal_id"] != b["deal_id"]


@pytest.mark.asyncio
async def test_book_proposed_time_and_store_buyer_windows(client, db):
    tuan = await auth(client, OWNER_TUAN)
    await client.post(
        f"/api/v1/owner/properties/{TUAN_PROPERTY}/slots", json={"start_at": at(14.5), "end_at": at(16)}, headers=tuan
    )
    an = await auth(client, CUSTOMER_AN)
    r = await client.post(
        "/api/v1/bookings",
        json={
            "property_id": TUAN_PROPERTY,
            "start_at": at(15),
            "buyer_windows": [{"start_at": at(14), "end_at": at(17)}],
        },
        headers=an,
    )
    assert r.status_code == 201, r.text
    assert datetime.fromisoformat(r.json()["start_at"]) == SAT + timedelta(hours=15)
    assert datetime.fromisoformat(r.json()["end_at"]) == SAT + timedelta(hours=15.5)

    windows = db.query(BuyerAvailability).filter_by(deal_id=r.json()["deal_id"]).all()
    assert [(w.start_at, w.end_at) for w in windows] == [(SAT + timedelta(hours=14), SAT + timedelta(hours=17))]


@pytest.mark.asyncio
async def test_start_time_outside_seller_availability_is_refused(client):
    an = await auth(client, CUSTOMER_AN)
    r = await client.post("/api/v1/bookings", json={"property_id": TUAN_PROPERTY, "start_at": at(3)}, headers=an)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "BUSINESS_RULE_VIOLATION"


@pytest.mark.asyncio
async def test_request_needs_exactly_one_time_source(client):
    an = await auth(client, CUSTOMER_AN)
    r = await client.post("/api/v1/bookings", json={"property_id": TUAN_PROPERTY}, headers=an)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_deal_hidden_from_other_buyers_and_sellers(client):
    an = await auth(client, CUSTOMER_AN)
    deal_id = (await _book_slot(client, an)).json()["deal_id"]

    for who in (CUSTOMER_BINH, OWNER_LAN):
        headers = await auth(client, who)
        assert (await client.get(f"/api/v1/deals/{deal_id}", headers=headers)).status_code == 404
    op = await auth(client, OPERATOR)
    assert (await client.get(f"/api/v1/deals/{deal_id}", headers=op)).status_code == 200
