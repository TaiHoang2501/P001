"""Listing media, ownership proof and withdrawal (spec §4.5, §4.11)."""

import pytest
from sqlalchemy import text

from tests.helpers import CUSTOMER_AN, OPERATOR, OWNER_LAN, OWNER_TUAN, TUAN_RED_BOOK, auth, first_free_slot

DOC = {"kind": "OWNERSHIP_DOC", "s3_key": "private/new/so-hong.pdf", "content_type": "application/pdf"}
PHOTO = {"kind": "IMAGE", "s3_key": "public/new/living-room.jpg", "content_type": "image/jpeg", "sort_order": 1}


async def _new_draft(client, headers) -> int:
    r = await client.post(
        "/api/v1/owner/properties",
        json={
            "building_id": 1,
            "unit_code": "NEW-1001",
            "property_type": "APARTMENT",
            "bedrooms": 2,
            "bathrooms": 2,
            "area_m2": "72.5",
            "floor": 10,
            "price_vnd": 4_200_000_000,
            "direction": "SE",
            "view": "LAKE",
            "furnishing": "BASIC",
            "legal_status": "PINK_BOOK",
            "verification_id": TUAN_RED_BOOK,
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_new_listing_goes_straight_to_review(client):
    owner = await auth(client, OWNER_TUAN)
    pid = await _new_draft(client, owner)
    r = await client.get("/api/v1/owner/properties", headers=owner)
    assert next(p for p in r.json() if p["id"] == pid)["status"] == "PENDING_REVIEW"


@pytest.mark.asyncio
async def test_listing_without_verified_red_book_cannot_be_sent_again(client, db):
    owner = await auth(client, OWNER_TUAN)
    pid = await _new_draft(client, owner)
    op = await auth(client, OPERATOR)
    await client.post(f"/api/v1/operator/properties/{pid}/reject", json={"reason": "Ảnh mờ"}, headers=op)
    db.execute(text("UPDATE properties SET verification_id = NULL WHERE id = :id"), {"id": pid})
    db.commit()

    # Ownership is proven by the red book only; an uploaded document no longer counts
    assert (await client.post(f"/api/v1/owner/properties/{pid}/media", json=DOC, headers=owner)).status_code == 201
    r = await client.post(f"/api/v1/owner/properties/{pid}/submit", headers=owner)
    assert r.status_code == 422
    assert r.json()["error"]["details"]["missing"] == "OWNERSHIP_VERIFICATION"


@pytest.mark.asyncio
async def test_ownership_document_is_never_public(client):
    owner = await auth(client, OWNER_TUAN)
    pid = await _new_draft(client, owner)
    r = await client.post(f"/api/v1/owner/properties/{pid}/media", json={**DOC, "is_public": True}, headers=owner)
    assert [m["is_public"] for m in r.json()["media"]] == [False]


@pytest.mark.asyncio
async def test_buyer_sees_photos_but_not_documents(client):
    owner = await auth(client, OWNER_TUAN)
    pid = await _new_draft(client, owner)
    await client.post(f"/api/v1/owner/properties/{pid}/media", json=DOC, headers=owner)
    await client.post(f"/api/v1/owner/properties/{pid}/media", json=PHOTO, headers=owner)
    operator = await auth(client, OPERATOR)
    r = await client.post(f"/api/v1/operator/properties/{pid}/approve", headers=operator)
    assert {m["kind"] for m in r.json()["media"]} == {"OWNERSHIP_DOC", "IMAGE"}

    buyer = await auth(client, CUSTOMER_AN)
    r = await client.get(f"/api/v1/properties/{pid}", headers=buyer)
    assert r.status_code == 200
    assert [m["kind"] for m in r.json()["media"]] == ["IMAGE"]
    assert r.json()["image_urls"] == [PHOTO["s3_key"]]


@pytest.mark.asyncio
async def test_media_locked_while_listing_is_live(client):
    owner = await auth(client, OWNER_TUAN)
    r = await client.post("/api/v1/owner/properties/1/media", json=PHOTO, headers=owner)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_owner_cannot_delete_other_owners_media(client, db):
    lan = await auth(client, OWNER_LAN)
    tuan = await auth(client, OWNER_TUAN)
    pid = await _new_draft(client, tuan)
    media_id = (await client.post(f"/api/v1/owner/properties/{pid}/media", json=DOC, headers=tuan)).json()["media"][0][
        "id"
    ]
    assert (await client.delete(f"/api/v1/owner/properties/{pid}/media/{media_id}", headers=lan)).status_code == 404
    r = await client.delete(f"/api/v1/owner/properties/{pid}/media/{media_id}", headers=tuan)
    assert r.status_code == 200
    assert r.json()["media"] == []


@pytest.mark.asyncio
async def test_withdraw_and_resubmit(client):
    owner = await auth(client, OWNER_TUAN)
    r = await client.post("/api/v1/owner/properties/1/withdraw", headers=owner)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "WITHDRAWN"
    assert (await client.get("/api/v1/properties/1")).status_code == 404

    # Off the marketplace, so it can be edited and sent back for review
    assert (
        await client.patch("/api/v1/owner/properties/1", json={"price_vnd": 5_000_000_000}, headers=owner)
    ).status_code == 200
    r = await client.post("/api/v1/owner/properties/1/submit", headers=owner)
    assert r.json()["status"] == "PENDING_REVIEW"


@pytest.mark.asyncio
async def test_cannot_withdraw_with_active_booking(client):
    buyer = await auth(client, CUSTOMER_AN)
    slot = await first_free_slot(client, 1)
    r = await client.post("/api/v1/bookings", json={"property_id": 1, "slot_id": slot["id"]}, headers=buyer)
    assert r.status_code == 201, r.text

    owner = await auth(client, OWNER_TUAN)
    r = await client.post("/api/v1/owner/properties/1/withdraw", headers=owner)
    assert r.status_code == 409


# ---------- Uploads to object storage ----------


@pytest.fixture
def storage(monkeypatch):
    """In-memory stand-in for the S3-compatible bucket."""
    from src.services import storage_service

    objects: dict[tuple[bool, str], bytes] = {}
    monkeypatch.setattr(storage_service, "is_enabled", lambda: True)
    monkeypatch.setattr(
        storage_service, "upload", lambda key, body, _ct, *, private: objects.__setitem__((private, key), body.read())
    )
    monkeypatch.setattr(storage_service, "delete", lambda key, *, private: objects.pop((private, key), None))
    monkeypatch.setattr(storage_service, "signed_url", lambda key: f"https://signed.example/{key}?token=x")
    return objects


async def _upload(client, headers, pid: int, kind: str, content_type: str, body: bytes = b"data"):
    return await client.post(
        f"/api/v1/owner/properties/{pid}/media/upload",
        data={"kind": kind},
        files={"file": ("file", body, content_type)},
        headers=headers,
    )


@pytest.mark.asyncio
async def test_upload_photo_goes_to_public_bucket(client, storage):
    owner = await auth(client, OWNER_TUAN)
    pid = await _new_draft(client, owner)

    r = await _upload(client, owner, pid, "IMAGE", "image/webp", b"photo")
    assert r.status_code == 201, r.text
    [media] = r.json()["media"]
    assert media["is_public"] is True
    assert media["url"].startswith(f"properties/{pid}/") and media["url"].endswith(".webp")
    assert storage == {(False, media["url"]): b"photo"}


@pytest.mark.asyncio
async def test_uploaded_document_is_private_and_signed(client, storage):
    owner = await auth(client, OWNER_TUAN)
    pid = await _new_draft(client, owner)

    r = await _upload(client, owner, pid, "OWNERSHIP_DOC", "application/pdf")
    assert r.status_code == 201, r.text
    [media] = r.json()["media"]
    assert media["is_public"] is False
    assert media["url"].startswith(f"https://signed.example/properties/{pid}/")
    [(private, _key)] = storage
    assert private is True


@pytest.mark.asyncio
async def test_upload_rejects_wrong_type_and_empty_file(client, storage):
    owner = await auth(client, OWNER_TUAN)
    pid = await _new_draft(client, owner)

    assert (await _upload(client, owner, pid, "IMAGE", "text/html")).status_code == 422
    assert (await _upload(client, owner, pid, "IMAGE", "image/png", b"")).status_code == 422
    assert storage == {}


@pytest.mark.asyncio
async def test_upload_blocked_for_live_listing_and_other_owners(client, storage):
    tuan = await auth(client, OWNER_TUAN)
    lan = await auth(client, OWNER_LAN)
    assert (await _upload(client, tuan, 1, "IMAGE", "image/jpeg")).status_code == 409
    pid = await _new_draft(client, tuan)
    assert (await _upload(client, lan, pid, "IMAGE", "image/jpeg")).status_code == 404
    assert storage == {}


@pytest.mark.asyncio
async def test_upload_without_storage_configured(client):
    owner = await auth(client, OWNER_TUAN)
    pid = await _new_draft(client, owner)
    r = await _upload(client, owner, pid, "IMAGE", "image/jpeg")
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "STORAGE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_deleting_media_removes_the_file(client, storage):
    owner = await auth(client, OWNER_TUAN)
    pid = await _new_draft(client, owner)
    media_id = (await _upload(client, owner, pid, "IMAGE", "image/jpeg")).json()["media"][0]["id"]

    r = await client.delete(f"/api/v1/owner/properties/{pid}/media/{media_id}", headers=owner)
    assert r.status_code == 200
    assert storage == {}


@pytest.mark.asyncio
async def test_cannot_register_another_listings_private_file(client, storage):
    """A signed URL would expose someone else's ownership document."""
    owner = await auth(client, OWNER_TUAN)
    pid = await _new_draft(client, owner)
    stolen = {**DOC, "s3_key": "properties/1/someone-elses-so-hong.pdf"}
    r = await client.post(f"/api/v1/owner/properties/{pid}/media", json=stolen, headers=owner)
    assert r.status_code == 422
