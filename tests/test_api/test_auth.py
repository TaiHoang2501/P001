import pytest

from tests.helpers import CUSTOMER_AN, OWNER_TUAN, auth


@pytest.mark.asyncio
async def test_register_then_login_by_phone(client):
    r = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Khách Mới", "phone": "0909999888", "password": "secret-pass", "role": "CUSTOMER"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["user"]["role"] == "CUSTOMER"

    r = await client.post("/api/v1/auth/login", json={"identifier": "0909999888", "password": "secret-pass"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_register_duplicate_phone_rejected(client):
    r = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Trùng", "phone": "0901111222", "password": "secret-pass"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_cannot_self_register_as_operator(client):
    r = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Hacker", "phone": "0909000111", "password": "secret-pass", "role": "INVESTOR_OPERATOR"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_wrong_password(client):
    r = await client.post("/api/v1/auth/login", json={"identifier": CUSTOMER_AN, "password": "nope"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_me_requires_token(client):
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    headers = await auth(client, OWNER_TUAN)
    r = await client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["role"] == "OWNER"


@pytest.mark.asyncio
async def test_customer_cannot_use_owner_or_operator_endpoints(client):
    headers = await auth(client, CUSTOMER_AN)
    assert (await client.get("/api/v1/owner/properties", headers=headers)).status_code == 403
    assert (await client.get("/api/v1/operator/properties", headers=headers)).status_code == 403
