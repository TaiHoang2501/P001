"""Listing media, ownership document requirement and withdrawal (spec §4.5, §4.11)."""

import pytest

from tests.helpers import CUSTOMER_AN, OPERATOR, OWNER_LAN, OWNER_TUAN, auth, first_free_slot

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
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_submit_requires_ownership_document(client):
    owner = await auth(client, OWNER_TUAN)
    pid = await _new_draft(client, owner)

    r = await client.post(f"/api/v1/owner/properties/{pid}/submit", headers=owner)
    assert r.status_code == 422
    assert r.json()["error"]["details"]["missing"] == "OWNERSHIP_DOC"

    assert (await client.post(f"/api/v1/owner/properties/{pid}/media", json=DOC, headers=owner)).status_code == 201
    r = await client.post(f"/api/v1/owner/properties/{pid}/submit", headers=owner)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "PENDING_REVIEW"


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
    await client.post(f"/api/v1/owner/properties/{pid}/submit", headers=owner)
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
