"""Red book ownership verification before listing (holder name + code + OTP to the phone on record)."""

import pytest

from tests.helpers import CUSTOMER_AN, OPERATOR, OWNER_LAN, OWNER_TUAN, TUAN_RED_BOOK, UNCLAIMED_RED_BOOK, auth

CLAIM = {k: v for k, v in UNCLAIMED_RED_BOOK.items() if k != "id"}
LISTING = {
    "building_id": 1,
    "unit_code": "RB-0707",
    "property_type": "APARTMENT",
    "bedrooms": 2,
    "bathrooms": 2,
    "area_m2": "70",
    "floor": 7,
    "price_vnd": 3_500_000_000,
    "direction": "SE",
    "view": "LAKE",
    "furnishing": "FULL",
    "legal_status": "PINK_BOOK",
}


async def _new_seller(client, phone: str = "0966000077") -> dict:
    code = (await client.post("/api/v1/auth/otp/request", json={"target": phone})).json()["debug_code"]
    r = await client.post(
        "/api/v1/auth/otp/verify", json={"target": phone, "code": code, "full_name": "Người Bán Mới", "role": "OWNER"}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _claim(client, headers, claim=CLAIM) -> dict:
    r = await client.post("/api/v1/owner/ownership/claim", json=claim, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_new_seller_verifies_red_book_then_lists(client):
    seller = await _new_seller(client)

    # Spacing and letter case may differ, accents may not
    challenge = await _claim(
        client, seller, {"red_book_holder_name": "  nguyễn  THỊ hương ", "red_book_code": "sd-2017-0332211"}
    )
    assert challenge["verification_id"] == UNCLAIMED_RED_BOOK["id"]
    assert challenge["status"] == "OTP_SENT"
    assert challenge["masked_phone"] == "090****777"
    assert challenge["debug_code"]

    vid = challenge["verification_id"]
    r = await client.post(
        f"/api/v1/owner/ownership/{vid}/confirm", json={"code": challenge["debug_code"]}, headers=seller
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "VERIFIED"
    assert r.json()["property_id"] is None

    # The red book is evidence; the operator still reviews the seller, and sees the red book in the queue
    profile = (await client.get("/api/v1/owner/verification", headers=seller)).json()
    assert profile["verification_status"] == "PENDING"
    operator = await auth(client, OPERATOR)
    queue = (await client.get("/api/v1/operator/sellers", headers=operator)).json()
    item = next(s for s in queue if s["user_id"] == profile["user_id"])
    assert item["red_book_codes"] == [CLAIM["red_book_code"]]
    assert [b["red_book_code"] for b in (await client.get("/api/v1/owner/ownership", headers=seller)).json()] == [
        CLAIM["red_book_code"]
    ]

    r = await client.post("/api/v1/owner/properties", json={**LISTING, "verification_id": vid}, headers=seller)
    assert r.status_code == 201, r.text
    books = (await client.get("/api/v1/owner/ownership", headers=seller)).json()
    assert books[0]["property_id"] == r.json()["id"]

    # One red book backs one listing
    r = await client.post(
        "/api/v1/owner/properties", json={**LISTING, "unit_code": "RB-0708", "verification_id": vid}, headers=seller
    )
    assert r.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "claim",
    [
        {**CLAIM, "red_book_holder_name": "Nguyen Thi Huong"},  # accents stripped
        {**CLAIM, "red_book_holder_name": "Trần Văn Đức"},  # someone else's name
        {**CLAIM, "red_book_code": "SD-0000-0000000"},  # unknown code
    ],
)
async def test_mismatch_gets_one_answer_and_sends_no_code(client, claim):
    seller = await _new_seller(client)
    r = await client.post("/api/v1/owner/ownership/claim", json=claim, headers=seller)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "OWNERSHIP_NOT_MATCHED"
    assert "debug_code" not in r.json()


@pytest.mark.asyncio
async def test_wrong_codes_lock_the_red_book(client):
    seller = await _new_seller(client)
    challenge = await _claim(client, seller)
    vid = challenge["verification_id"]
    wrong = "000000" if challenge["debug_code"] != "000000" else "111111"

    r = await client.post(f"/api/v1/owner/ownership/{vid}/confirm", json={"code": wrong}, headers=seller)
    # 422, not 401: a wrong ownership code must not sign the seller out
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "OTP_INVALID"
    assert r.json()["error"]["details"]["attempts_left"] == 4

    for _ in range(4):
        r = await client.post(f"/api/v1/owner/ownership/{vid}/confirm", json={"code": wrong}, headers=seller)
    assert r.json()["error"]["details"]["status"] == "FAILED"

    # Locked: even the right code or a new claim no longer works
    r = await client.post("/api/v1/owner/ownership/claim", json=CLAIM, headers=seller)
    assert r.status_code == 409
    assert r.json()["error"]["details"]["reason"] == "LOCKED"


@pytest.mark.asyncio
async def test_seeded_failed_red_book_is_locked(client):
    seller = await _new_seller(client)
    r = await client.post(
        "/api/v1/owner/ownership/claim",
        json={"red_book_holder_name": "Trần Văn Đức", "red_book_code": "SD-2015-0110022"},
        headers=seller,
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_red_book_verified_by_another_seller_cannot_be_claimed(client):
    seller = await _new_seller(client)
    r = await client.post(
        "/api/v1/owner/ownership/claim",
        json={"red_book_holder_name": "Phạm Minh Tuấn", "red_book_code": "SD-2019-0456123"},
        headers=seller,
    )
    assert r.status_code == 409

    # Its own owner just gets it back as already verified, without a new code
    tuan = await auth(client, OWNER_TUAN)
    r = await client.post(
        "/api/v1/owner/ownership/claim",
        json={"red_book_holder_name": "Phạm Minh Tuấn", "red_book_code": "SD-2019-0456123"},
        headers=tuan,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "VERIFIED"
    assert r.json()["debug_code"] is None


@pytest.mark.asyncio
async def test_listing_needs_own_verified_red_book(client):
    seller = await _new_seller(client)
    # No red book at all
    r = await client.post("/api/v1/owner/properties", json={**LISTING, "verification_id": 7}, headers=seller)
    assert r.status_code == 422
    assert r.json()["error"]["details"]["missing"] == "OWNERSHIP_VERIFICATION"

    # Someone else's verified red book
    lan = await auth(client, OWNER_LAN)
    r = await client.post("/api/v1/owner/properties", json={**LISTING, "verification_id": TUAN_RED_BOOK}, headers=lan)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_buyers_cannot_use_ownership_endpoints(client):
    buyer = await auth(client, CUSTOMER_AN)
    assert (await client.post("/api/v1/owner/ownership/claim", json=CLAIM, headers=buyer)).status_code == 403
