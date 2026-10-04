import pytest
from sqlalchemy import text

from src.core.security import hash_password
from src.db.seed import SEED_PASSWORD
from tests.helpers import CUSTOMER_AN, OWNER_TUAN, SELLER_PHONES, auth


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
async def test_sellers_cannot_sign_up_with_password(client):
    r = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Chủ Căn", "phone": "0909000222", "password": "secret-pass", "role": "OWNER"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_sellers_cannot_log_in_with_password(client, db):
    # Even if a seller account somehow had a password, password login stays closed to sellers
    db.execute(
        text("UPDATE users SET password_hash = :h WHERE email = :e"),
        {"h": hash_password(SEED_PASSWORD), "e": OWNER_TUAN},
    )
    db.commit()
    for identifier in (OWNER_TUAN, SELLER_PHONES[OWNER_TUAN]):
        r = await client.post("/api/v1/auth/login", json={"identifier": identifier, "password": SEED_PASSWORD})
        assert r.status_code == 401
        # Same answer as a wrong password: the response does not reveal that this is a seller account
        assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_sellers_sign_in_with_phone_not_email(client):
    code = (await client.post("/api/v1/auth/otp/request", json={"target": OWNER_TUAN})).json()["debug_code"]
    r = await client.post("/api/v1/auth/otp/verify", json={"target": OWNER_TUAN, "code": code})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"

    headers = await auth(client, OWNER_TUAN)  # phone + OTP
    assert (await client.get("/api/v1/auth/me", headers=headers)).json()["role"] == "OWNER"


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
