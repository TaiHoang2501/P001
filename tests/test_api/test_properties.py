import pytest

from tests.helpers import CUSTOMER_AN, OPERATOR, OWNER_LAN, OWNER_TUAN, TUAN_RED_BOOK, auth

NEW_LISTING = {
    "building_id": 1,
    "unit_code": "S2.01-TEST",
    "property_type": "APARTMENT",
    "bedrooms": 2,
    "bathrooms": 2,
    "area_m2": "68.5",
    "floor": 12,
    "price_vnd": 3_200_000_000,
    "direction": "SE",
    "view": "LAKE",
    "furnishing": "FULL",
    "legal_status": "PINK_BOOK",
    "description": "Căn góc view hồ",
    "verification_id": TUAN_RED_BOOK,
}


@pytest.mark.asyncio
async def test_search_only_returns_available_listings_of_active_owners(client):
    r = await client.post("/api/v1/properties/search", json={"limit": 20})
    assert r.status_code == 200
    body = r.json()
    # 32 random + 5 extra two-bedroom demo listings; 4 more seed listings are pending/draft/unverified owner
    assert body["total_candidates"] == 37
    for rec in body["results"]:
        assert rec["property"]["status"] == "AVAILABLE"
        assert rec["property"]["owner_id"] in (4, 5)


@pytest.mark.asyncio
async def test_search_hard_filters_and_explanations(client):
    r = await client.post(
        "/api/v1/properties/search",
        json={
            "project_codes": ["VHSC"],
            "budget_max": 4_500_000_000,
            "bedrooms_min": 2,
            "preferred_views": ["LAKE", "PARK"],
            "priorities": {"view": "high"},
        },
    )
    assert r.status_code == 200
    results = r.json()["results"]
    assert results, "seed data should contain matches"
    scores = [rec["match_score"] for rec in results]
    assert scores == sorted(scores, reverse=True)
    for rec in results:
        prop = rec["property"]
        assert prop["project_code"] == "VHSC"
        assert prop["price_vnd"] <= 4_500_000_000
        assert prop["bedrooms"] >= 2
        criteria = {m["criterion"] for m in rec["matched"] + rec["unmatched"]}
        assert {"price", "view"} <= criteria


@pytest.mark.asyncio
async def test_search_no_match_returns_empty_not_invented(client):
    r = await client.post("/api/v1/properties/search", json={"budget_max": 1_000_000})
    assert r.status_code == 200
    assert r.json() == {"total_candidates": 0, "results": []}


@pytest.mark.asyncio
async def test_pending_listing_hidden_from_public(client):
    pending_id = 33  # first extra seed listing (PENDING_REVIEW)
    assert (await client.get(f"/api/v1/properties/{pending_id}")).status_code == 404
    headers = await auth(client, OPERATOR)
    assert (await client.get(f"/api/v1/properties/{pending_id}", headers=headers)).status_code == 200


@pytest.mark.asyncio
async def test_listing_goes_straight_to_review_then_approved(client):
    owner = await auth(client, OWNER_TUAN)
    op = await auth(client, OPERATOR)

    r = await client.post("/api/v1/owner/properties", json=NEW_LISTING, headers=owner)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    # "Đăng tin bán": no draft, the investor reviews it right away
    assert r.json()["status"] == "PENDING_REVIEW"

    queue = await client.get("/api/v1/operator/properties", headers=op)
    assert pid in [p["id"] for p in queue.json()]

    r = await client.post(f"/api/v1/operator/properties/{pid}/approve", headers=op)
    assert r.json()["status"] == "AVAILABLE"
    assert (await client.get(f"/api/v1/properties/{pid}")).status_code == 200

    # Approving twice is an invalid transition
    r = await client.post(f"/api/v1/operator/properties/{pid}/approve", headers=op)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "STATE_CONFLICT"

    # Approved listings can no longer be edited freely
    r = await client.patch(f"/api/v1/owner/properties/{pid}", json={"price_vnd": 3_000_000_000}, headers=owner)
    assert r.status_code == 409
    # A price that is not a home price is refused outright (1 đồng, 5.000 tỷ)
    for price in (1, 5_000_000_000_000):
        r = await client.patch(f"/api/v1/owner/properties/{pid}", json={"price_vnd": price}, headers=owner)
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_rejected_listing_can_be_fixed_and_resubmitted(client):
    owner = await auth(client, OWNER_LAN)
    op = await auth(client, OPERATOR)
    pid = 33  # PENDING_REVIEW listing owned by Lan

    r = await client.post(
        f"/api/v1/operator/properties/{pid}/reject", json={"reason": "Thiếu ảnh phòng khách"}, headers=op
    )
    assert r.json()["status"] == "REJECTED"
    assert r.json()["rejection_reason"] == "Thiếu ảnh phòng khách"

    r = await client.patch(f"/api/v1/owner/properties/{pid}", json={"description": "Đã bổ sung ảnh"}, headers=owner)
    assert r.status_code == 200
    r = await client.post(f"/api/v1/owner/properties/{pid}/submit", headers=owner)
    assert r.json()["status"] == "PENDING_REVIEW"
    assert r.json()["rejection_reason"] is None


@pytest.mark.asyncio
async def test_owner_cannot_touch_other_owners_listing(client):
    lan = await auth(client, OWNER_LAN)
    tuan_property = 1
    r = await client.post(f"/api/v1/owner/properties/{tuan_property}/sold", headers=lan)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_customer_cannot_create_listing(client):
    headers = await auth(client, CUSTOMER_AN)
    r = await client.post("/api/v1/owner/properties", json=NEW_LISTING, headers=headers)
    assert r.status_code == 403
