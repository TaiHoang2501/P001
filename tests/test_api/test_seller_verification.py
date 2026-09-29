"""Seller verification by the operator and its enforcement (spec §2.3, AC-04)."""

import pytest

from src.db.models import Property, PropertyStatus, SellerProfile, SellerVerificationStatus
from src.models.property import SearchCriteria
from src.services import property_service
from tests.helpers import CUSTOMER_AN, OPERATOR, auth, first_free_slot

OWNER_KHOA = "khoa.do@gmail.com"  # seeded with a PENDING verification
KHOA_ID = 6
TUAN_ID = 4


def _unverify(db, user_id: int) -> None:
    db.get(SellerProfile, user_id).verification_status = SellerVerificationStatus.UNVERIFIED
    db.commit()


@pytest.mark.asyncio
async def test_operator_sees_pending_seller_and_verifies(client):
    headers = await auth(client, OPERATOR)
    r = await client.get("/api/v1/operator/sellers", headers=headers)
    assert r.status_code == 200
    assert [s["user_id"] for s in r.json()] == [KHOA_ID]
    assert r.json()[0]["full_name"] == "Đỗ Văn Khoa"

    r = await client.post(f"/api/v1/operator/sellers/{KHOA_ID}/verify", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["verification_status"] == "VERIFIED"

    owner = await auth(client, OWNER_KHOA)
    assert (await client.get("/api/v1/owner/verification", headers=owner)).json()["verification_status"] == "VERIFIED"


@pytest.mark.asyncio
async def test_rejected_seller_can_resubmit(client):
    operator = await auth(client, OPERATOR)
    r = await client.post(
        f"/api/v1/operator/sellers/{KHOA_ID}/reject", json={"reason": "Ảnh CCCD bị mờ"}, headers=operator
    )
    assert r.json()["verification_status"] == "REJECTED"
    assert r.json()["rejection_reason"] == "Ảnh CCCD bị mờ"

    owner = await auth(client, OWNER_KHOA)
    r = await client.post(
        "/api/v1/owner/verification", json={"id_document_s3_key": "private/sellers/6/cccd-2.jpg"}, headers=owner
    )
    assert r.status_code == 200, r.text
    assert r.json()["verification_status"] == "PENDING"
    assert r.json()["rejection_reason"] is None


@pytest.mark.asyncio
async def test_cannot_review_seller_twice(client):
    operator = await auth(client, OPERATOR)
    r = await client.post(f"/api/v1/operator/sellers/{TUAN_ID}/verify", headers=operator)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "STATE_CONFLICT"


@pytest.mark.asyncio
async def test_owner_cannot_verify_themselves(client):
    owner = await auth(client, OWNER_KHOA)
    assert (await client.post(f"/api/v1/operator/sellers/{KHOA_ID}/verify", headers=owner)).status_code == 403


@pytest.mark.asyncio
async def test_listing_of_unverified_seller_cannot_be_approved(client, db):
    prop = db.query(Property).filter_by(owner_id=TUAN_ID).order_by(Property.id).first()
    prop.status = PropertyStatus.PENDING_REVIEW
    db.commit()
    _unverify(db, TUAN_ID)

    operator = await auth(client, OPERATOR)
    r = await client.post(f"/api/v1/operator/properties/{prop.id}/approve", headers=operator)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "SELLER_UNVERIFIED"


@pytest.mark.asyncio
async def test_unverified_seller_property_cannot_be_booked(client, db):
    prop = db.query(Property).filter_by(owner_id=TUAN_ID, status=PropertyStatus.AVAILABLE).first()
    slot = await first_free_slot(client, prop.id)
    _unverify(db, TUAN_ID)

    headers = await auth(client, CUSTOMER_AN)
    r = await client.post("/api/v1/bookings", json={"property_id": prop.id, "slot_id": slot["id"]}, headers=headers)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "SELLER_UNVERIFIED"


def test_search_hides_unverified_sellers(db):
    before = property_service.search(db, SearchCriteria(limit=20))
    tuan_listings = db.query(Property).filter_by(owner_id=TUAN_ID, status=PropertyStatus.AVAILABLE).count()
    assert tuan_listings > 0

    _unverify(db, TUAN_ID)
    after = property_service.search(db, SearchCriteria(limit=20))
    assert after.total_candidates == before.total_candidates - tuan_listings
    assert all(r.property.owner_id != TUAN_ID for r in after.results)
