"""Red book ownership verification before listing (holder name + code + OTP to the phone on record)."""

import pytest

from tests.helpers import (
    CUSTOMER_AN,
    OPERATOR,
    OWNER_LAN,
    OWNER_TUAN,
    TUAN_RED_BOOK,
    UNCLAIMED_RED_BOOK,
    UNCLAIMED_RED_BOOK_PHONE,
    auth,
)

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


async def _new_seller(client, phone: str = UNCLAIMED_RED_BOOK_PHONE) -> dict:
    """A new seller account; by default the owner of UNCLAIMED_RED_BOOK, signed in with the phone on it."""
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

    # The verified red book verifies the seller too: no separate review by the operator
    profile = (await client.get("/api/v1/owner/verification", headers=seller)).json()
    assert profile["verification_status"] == "VERIFIED"
    operator = await auth(client, OPERATOR)
    queue = (await client.get("/api/v1/operator/sellers", headers=operator)).json()
    assert profile["user_id"] not in [s["user_id"] for s in queue]
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
    # Its owner (signed in with the phone on it) is told it is locked
    seller = await _new_seller(client, "0933444555")
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
    assert r.status_code == 422
    assert r.json()["error"]["details"] == {"reason": "NOT_OWNER_PHONE"}

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


@pytest.mark.asyncio
async def test_someone_else_cannot_verify_a_red_book_even_knowing_its_details(client):
    """Tuấn knows Hương's name and red book code: no code is sent, he is pointed to a support request."""
    tuan = await auth(client, OWNER_TUAN)
    r = await client.post("/api/v1/owner/ownership/claim", json=CLAIM, headers=tuan)
    assert r.status_code == 422, r.text
    error = r.json()["error"]
    # Not a digit of the owner's phone is given away
    assert error["details"] == {"reason": "NOT_OWNER_PHONE"}
    assert "debug_code" not in r.json()
    # The owner herself, signed in with the phone on the red book, still can
    owner = await _new_seller(client)
    assert (await _claim(client, owner))["status"] == "OTP_SENT"


@pytest.mark.asyncio
async def test_guessing_red_books_is_limited(client):
    seller = await _new_seller(client, "0966000078")
    for _ in range(5):
        r = await client.post(
            "/api/v1/owner/ownership/claim", json={**CLAIM, "red_book_code": "SD-0000-0000000"}, headers=seller
        )
        assert r.status_code == 422
    r = await client.post("/api/v1/owner/ownership/claim", json=CLAIM, headers=seller)
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_a_home_has_one_verified_red_book(client, db):
    """A second red book for a home that already has a verified one goes to the investor, not to the seller."""
    from src.db.models import PropertyOwnershipVerification

    book = db.get(PropertyOwnershipVerification, UNCLAIMED_RED_BOOK["id"])
    tuans = db.get(PropertyOwnershipVerification, TUAN_RED_BOOK)
    book.building_id, book.unit_code = tuans.building_id, tuans.unit_code
    db.commit()
    r = await client.post("/api/v1/owner/ownership/claim", json=CLAIM, headers=await _new_seller(client))
    assert r.status_code == 409, r.text
    assert r.json()["error"]["details"]["reason"] == "UNIT_CLAIMED"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "red_book",
    [
        {"red_book_holder_name": "Phạm Minh Tuấn", "red_book_code": "SD-2019-0456123"},  # verified by Tuấn
        {"red_book_holder_name": "Trần Văn Đức", "red_book_code": "SD-2015-0110022"},  # locked
        CLAIM,  # not verified yet
    ],
)
async def test_someone_else_learns_nothing_about_a_red_book(client, red_book):
    """Two owners with the same name: whatever state the other's red book is in, the answer is the same."""
    stranger = await _new_seller(client, "0966000079")
    r = await client.post("/api/v1/owner/ownership/claim", json=red_book, headers=stranger)
    assert (r.status_code, r.json()["error"]["details"]) == (422, {"reason": "NOT_OWNER_PHONE"})


@pytest.mark.asyncio
async def test_only_the_owner_phone_can_finish_a_red_book(client, db):
    """Lan (another phone) cannot take the red book the owner is verifying, even with the code, nor lock it by
    guessing: the confirm step checks the signed-in phone like the claim does."""
    owner = await _new_seller(client)
    challenge = await _claim(client, owner)
    vid = challenge["verification_id"]
    lan = await auth(client, OWNER_LAN)
    for code in (challenge["debug_code"], "000000", "111111", "222222", "333333", "444444"):
        r = await client.post(f"/api/v1/owner/ownership/{vid}/confirm", json={"code": code}, headers=lan)
        assert r.status_code == 422 and r.json()["error"]["details"]["reason"] == "NOT_OWNER_PHONE", r.text
    # Untouched: the real owner still finishes it
    r = await client.post(
        f"/api/v1/owner/ownership/{vid}/confirm", json={"code": challenge["debug_code"]}, headers=owner
    )
    assert r.status_code == 200 and r.json()["status"] == "VERIFIED", r.text
