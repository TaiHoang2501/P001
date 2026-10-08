"""Photos uploaded from the seller's device, "Đăng tin bán" in one step, and fixing a listing under review."""

import pytest

from tests.helpers import CUSTOMER_AN, OPERATOR, OWNER_LAN, OWNER_TUAN, TUAN_RED_BOOK, auth

# Smallest valid-looking files: only the first bytes are checked
JPEG = b"\xff\xd8\xff\xe0" + b"\0" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 64

LISTING = {
    "building_id": 1,
    "unit_code": "NEW-2201",
    "property_type": "APARTMENT",
    "bedrooms": 2,
    "bathrooms": 2,
    "area_m2": "70",
    "floor": 22,
    "price_vnd": 4_100_000_000,
    "direction": "SE",
    "view": "LAKE",
    "furnishing": "FULL",
    "legal_status": "PINK_BOOK",
    "verification_id": TUAN_RED_BOOK,
}


async def _upload(client, headers, data: bytes = JPEG, name: str = "phong-khach.jpg"):
    return await client.post(
        "/api/v1/owner/media", files={"file": (name, data, "application/octet-stream")}, headers=headers
    )


@pytest.mark.asyncio
async def test_photo_upload_is_served_back(client):
    tuan = await auth(client, OWNER_TUAN)
    r = await _upload(client, tuan, PNG, "bep.png")
    assert r.status_code == 201, r.text
    photo = r.json()
    assert photo["key"].startswith("/api/v1/media/") and photo["content_type"] == "image/png"

    r = await client.get(photo["url"])
    assert r.status_code == 200
    assert r.content == PNG and r.headers["content-type"] == "image/png"


@pytest.mark.asyncio
async def test_only_photos_within_the_size_limit_are_accepted(client, monkeypatch):
    tuan = await auth(client, OWNER_TUAN)
    r = await _upload(client, tuan, b"%PDF-1.7 not a photo", "giay-to.pdf")
    assert r.status_code == 422

    from src.config import get_settings

    monkeypatch.setattr(get_settings(), "media_max_bytes", 1024)
    r = await _upload(client, tuan, JPEG + b"\0" * 2048)
    assert r.status_code == 422
    assert r.json()["error"]["details"]["max_bytes"] == 1024


@pytest.mark.asyncio
async def test_only_sellers_upload(client):
    an = await auth(client, CUSTOMER_AN)
    assert (await _upload(client, an)).status_code == 403


@pytest.mark.asyncio
async def test_post_listing_with_photos_goes_straight_to_review(client):
    tuan = await auth(client, OWNER_TUAN)
    cover = (await _upload(client, tuan)).json()
    second = (await _upload(client, tuan, PNG, "bep.png")).json()

    r = await client.post(
        "/api/v1/owner/properties",
        json={**LISTING, "photos": [cover["key"], second["key"]]},
        headers=tuan,
    )
    assert r.status_code == 201, r.text
    listing = r.json()
    assert listing["status"] == "PENDING_REVIEW"
    assert [m["url"] for m in listing["media"]] == [cover["url"], second["url"]]

    # The investor sees it in the review queue with its photos
    op = await auth(client, OPERATOR)
    queue = (await client.get("/api/v1/operator/properties", headers=op)).json()
    assert len(next(p for p in queue if p["id"] == listing["id"])["media"]) == 2


@pytest.mark.asyncio
async def test_photos_of_another_seller_cannot_be_used(client):
    lan = await auth(client, OWNER_LAN)
    tuan = await auth(client, OWNER_TUAN)
    lans = (await _upload(client, lan)).json()

    r = await client.post("/api/v1/owner/properties", json={**LISTING, "photos": [lans["key"]]}, headers=tuan)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_listing_under_review_can_be_corrected(client):
    tuan = await auth(client, OWNER_TUAN)
    r = await client.post("/api/v1/owner/properties", json=LISTING, headers=tuan)
    pid = r.json()["id"]

    # Wrong price typed in: fix it and add a photo while it waits for the investor
    r = await client.patch(f"/api/v1/owner/properties/{pid}", json={"price_vnd": 4_050_000_000}, headers=tuan)
    assert r.status_code == 200, r.text
    assert (r.json()["price_vnd"], r.json()["status"]) == (4_050_000_000, "PENDING_REVIEW")
    photo = (await _upload(client, tuan)).json()
    r = await client.post(
        f"/api/v1/owner/properties/{pid}/media",
        json={"kind": "IMAGE", "s3_key": photo["key"], "content_type": "image/jpeg"},
        headers=tuan,
    )
    assert r.status_code == 201, r.text
    assert [m["url"] for m in r.json()["media"]] == [photo["url"]]


@pytest.mark.asyncio
async def test_home_facts_come_from_the_red_book(client):
    tuan = await auth(client, OWNER_TUAN)
    book = next(
        b for b in (await client.get("/api/v1/owner/ownership", headers=tuan)).json() if b["id"] == TUAN_RED_BOOK
    )
    unit = book["unit"]
    assert unit and unit["unit_code"]

    # Whatever the form says, the listing takes the home's facts from the investor's red book data
    wrong = {**LISTING, "area_m2": "999", "bedrooms": 5, "floor": 40, "direction": "N", "unit_code": "SAI-0000"}
    r = await client.post("/api/v1/owner/properties", json=wrong, headers=tuan)
    assert r.status_code == 201, r.text
    listing = r.json()
    for field in ("building_id", "unit_code", "bedrooms", "bathrooms", "floor", "direction"):
        assert listing[field] == unit[field], field
    assert float(listing["area_m2"]) == float(unit["area_m2"])
    assert listing["legal_status"] == "PINK_BOOK" and listing["verified_red_book"] is True
    assert listing["red_book_code"] == book["red_book_code"]

    # The seller cannot change them later; their own choices (price, view, furnishing) stay editable
    r = await client.patch(f"/api/v1/owner/properties/{listing['id']}", json={"bedrooms": 4}, headers=tuan)
    assert r.status_code == 422
    assert r.json()["error"]["details"]["fields"] == ["bedrooms"]
    same = {"bedrooms": unit["bedrooms"], "price_vnd": 3_900_000_000, "view": "PARK"}
    r = await client.patch(f"/api/v1/owner/properties/{listing['id']}", json=same, headers=tuan)
    assert r.status_code == 200, r.text
