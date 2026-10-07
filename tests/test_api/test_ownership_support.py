"""The investor steps in when a seller cannot verify a red book on their own (spec §4.5, §6.4 human fallback)."""

import pytest

from tests.helpers import CUSTOMER_AN, OPERATOR, OWNER_TUAN, TUAN_RED_BOOK, auth

JPEG = b"\xff\xd8\xff\xe0" + b"\0" * 64
LOCKED_BOOK = {"red_book_holder_name": "Trần Văn Đức", "red_book_code": "SD-2015-0110022"}  # seeded FAILED
LISTING = {
    "building_id": 1,
    "unit_code": "SP-0101",
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


async def _new_seller(client, phone: str, name: str = "Người Bán Mới") -> dict:
    code = (await client.post("/api/v1/auth/otp/request", json={"target": phone})).json()["debug_code"]
    r = await client.post(
        "/api/v1/auth/otp/verify", json={"target": phone, "code": code, "full_name": name, "role": "OWNER"}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _document(client, headers) -> str:
    r = await client.post(
        "/api/v1/owner/media",
        files={"file": ("cccd.jpg", JPEG, "image/jpeg")},
        data={"private": "true"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["key"]


async def _ask(client, headers, reason: str, book: dict, documents=()) -> dict:
    r = await client.post(
        "/api/v1/owner/ownership/support",
        json={**book, "reason": reason, "note": "Mong Chủ đầu tư hỗ trợ", "documents": list(documents)},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.asyncio
async def test_locked_red_book_unlocked_with_new_phone_then_seller_verifies_by_otp(client):
    duc = await _new_seller(client, "0966000101", "Trần Văn Đức")
    case = await _ask(client, duc, "LOCKED", LOCKED_BOOK, [await _document(client, duc)])
    assert case["type"] == "OWNERSHIP_SUPPORT" and case["status"] == "OPEN"
    # The same red book cannot be asked about twice while the case is open
    r = await client.post("/api/v1/owner/ownership/support", json={**LOCKED_BOOK, "reason": "NO_OTP"}, headers=duc)
    assert r.status_code == 409

    op = await auth(client, OPERATOR)
    assert case["id"] in [e["id"] for e in (await client.get("/api/v1/operator/escalations", headers=op)).json()]
    state = (await client.get(f"/api/v1/operator/escalations/{case['id']}/ownership", headers=op)).json()
    assert state["red_book"]["status"] == "FAILED" and state["seller"]["full_name"] == "Trần Văn Đức"

    r = await client.post(
        f"/api/v1/operator/escalations/{case['id']}/ownership/unlock", json={"owner_phone": "0966000101"}, headers=op
    )
    assert r.status_code == 200, r.text
    assert (r.json()["red_book"]["status"], r.json()["red_book"]["owner_phone"]) == ("UNVERIFIED", "0966000101")
    mine = (await client.get("/api/v1/owner/ownership/support", headers=duc)).json()
    assert mine[0]["status"] == "RESOLVED" and "mở khóa" in mine[0]["resolution"]

    # Back to the normal path: the OTP now goes to the new phone
    challenge = (await client.post("/api/v1/owner/ownership/claim", json=LOCKED_BOOK, headers=duc)).json()
    assert challenge["masked_phone"].endswith("101")
    r = await client.post(
        f"/api/v1/owner/ownership/{challenge['verification_id']}/confirm",
        json={"code": challenge["debug_code"]},
        headers=duc,
    )
    assert r.json()["status"] == "VERIFIED"


@pytest.mark.asyncio
async def test_home_without_red_book_verified_by_hand(client):
    seller = await _new_seller(client, "0966000102")
    case = await _ask(
        client, seller, "NO_RED_BOOK", {"red_book_holder_name": "Người Bán Mới", "red_book_code": "HDMB-2026-0042"}
    )
    op = await auth(client, OPERATOR)
    assert (await client.get(f"/api/v1/operator/escalations/{case['id']}/ownership", headers=op)).json()[
        "red_book"
    ] is None

    r = await client.post(
        f"/api/v1/operator/escalations/{case['id']}/ownership/verify",
        json={"note": "Đã đối chiếu hợp đồng mua bán bản gốc"},
        headers=op,
    )
    assert r.status_code == 200, r.text
    assert r.json()["red_book"]["status"] == "VERIFIED"
    assert (await client.get("/api/v1/owner/verification", headers=seller)).json()["verification_status"] == "VERIFIED"
    books = (await client.get("/api/v1/owner/ownership", headers=seller)).json()
    assert [b["red_book_code"] for b in books] == ["HDMB-2026-0042"]
    # No unit details on record: the seller enters them when listing
    r = await client.post(
        "/api/v1/owner/properties", json={**LISTING, "verification_id": books[0]["id"]}, headers=seller
    )
    assert r.status_code == 201, r.text
    assert r.json()["unit_code"] == "SP-0101"


@pytest.mark.asyncio
async def test_red_book_claimed_by_someone_else_is_revoked_then_given_to_its_owner(client):
    tuan = await auth(client, OWNER_TUAN)
    tuans = next(
        b for b in (await client.get("/api/v1/owner/ownership", headers=tuan)).json() if b["id"] == TUAN_RED_BOOK
    )
    listing = (
        await client.post("/api/v1/owner/properties", json={**LISTING, "verification_id": TUAN_RED_BOOK}, headers=tuan)
    ).json()
    book = {"red_book_holder_name": tuans["red_book_holder_name"], "red_book_code": tuans["red_book_code"]}

    real_owner = await _new_seller(client, "0966000103")
    case = await _ask(client, real_owner, "CLAIMED_BY_OTHER", book)
    op = await auth(client, OPERATOR)
    # Cannot hand it over while someone else holds it
    r = await client.post(
        f"/api/v1/operator/escalations/{case['id']}/ownership/verify", json={"note": "Chủ thật"}, headers=op
    )
    assert r.status_code == 409

    r = await client.post(
        f"/api/v1/operator/escalations/{case['id']}/ownership/revoke",
        json={"note": "Không phải chủ sở hữu"},
        headers=op,
    )
    assert r.status_code == 200, r.text
    assert r.json()["red_book"]["status"] == "UNVERIFIED" and r.json()["red_book"]["property_id"] is None
    # The wrong holder's listing is off the market and they are told
    gone = next(
        p for p in (await client.get("/api/v1/owner/properties", headers=tuan)).json() if p["id"] == listing["id"]
    )
    assert gone["status"] == "WITHDRAWN" and gone["verified_red_book"] is False
    notes = (await client.get("/api/v1/notifications", headers=tuan)).json()
    assert any(n["event_type"] == "OWNERSHIP_REVOKED" for n in notes)

    r = await client.post(
        f"/api/v1/operator/escalations/{case['id']}/ownership/verify", json={"note": "Đã xem sổ gốc"}, headers=op
    )
    assert r.status_code == 200, r.text
    assert [b["red_book_code"] for b in (await client.get("/api/v1/owner/ownership", headers=real_owner)).json()] == [
        book["red_book_code"]
    ]


@pytest.mark.asyncio
async def test_private_documents_are_only_for_the_uploader_and_the_investor(client):
    seller = await _new_seller(client, "0966000104")
    key = await _document(client, seller)
    media_id = key.removeprefix("/api/v1/media/")

    assert (await client.get(key)).status_code == 404  # never served publicly
    assert (await client.get(f"{key}/private", headers=seller)).status_code == 200
    assert (await client.get(f"{key}/private", headers=await auth(client, OPERATOR))).status_code == 200
    other = await auth(client, CUSTOMER_AN)
    assert (await client.get(f"/api/v1/media/{media_id}/private", headers=other)).status_code == 404


@pytest.mark.asyncio
async def test_only_the_investor_handles_cases(client):
    seller = await _new_seller(client, "0966000105")
    case = await _ask(client, seller, "NO_OTP", LOCKED_BOOK)
    for path in ("ownership/unlock", "ownership/verify"):
        r = await client.post(
            f"/api/v1/operator/escalations/{case['id']}/{path}", json={"note": "tự xác thực"}, headers=seller
        )
        assert r.status_code == 403
