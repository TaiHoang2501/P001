"""OTP login for Buyer/Seller (spec §4.17)."""

from datetime import UTC, datetime, timedelta

import pytest

from src.db.models import BuyerProfile, OtpCode, SellerProfile, SellerVerificationStatus, User
from tests.helpers import CUSTOMER_AN, OPERATOR

NEW_PHONE = "0977123456"


async def _request(client, target: str) -> str:
    r = await client.post("/api/v1/auth/otp/request", json={"target": target})
    assert r.status_code == 202, r.text
    assert r.json()["expires_in"] > 0
    return r.json()["debug_code"]


async def _verify(client, target: str, code: str, **signup):
    return await client.post("/api/v1/auth/otp/verify", json={"target": target, "code": code, **signup})


@pytest.mark.asyncio
async def test_existing_buyer_logs_in_with_otp(client):
    code = await _request(client, CUSTOMER_AN)
    r = await _verify(client, CUSTOMER_AN, code)
    assert r.status_code == 200, r.text
    assert r.json()["user"]["role"] == "CUSTOMER"

    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.status_code == 200


@pytest.mark.asyncio
async def test_first_use_of_phone_asks_for_signup_then_creates_buyer(client, db):
    code = await _request(client, NEW_PHONE)

    r = await _verify(client, NEW_PHONE, code)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"

    # Same code still works once sign-up details are added
    r = await _verify(client, NEW_PHONE, code, full_name="Người Mua Mới")
    assert r.status_code == 200, r.text
    user_id = r.json()["user"]["id"]
    assert db.get(User, user_id).password_hash is None
    assert db.get(BuyerProfile, user_id) is not None


@pytest.mark.asyncio
async def test_seller_signup_creates_unverified_seller_profile(client, db):
    code = await _request(client, NEW_PHONE)
    r = await _verify(client, NEW_PHONE, code, full_name="Chủ Căn Mới", role="OWNER")
    assert r.status_code == 200, r.text

    profile = db.get(SellerProfile, r.json()["user"]["id"])
    assert profile.verification_status == SellerVerificationStatus.UNVERIFIED


@pytest.mark.asyncio
async def test_code_is_single_use(client):
    code = await _request(client, CUSTOMER_AN)
    assert (await _verify(client, CUSTOMER_AN, code)).status_code == 200
    r = await _verify(client, CUSTOMER_AN, code)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_code_burns_after_too_many_wrong_guesses(client):
    code = await _request(client, CUSTOMER_AN)
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"
    for _ in range(5):
        assert (await _verify(client, CUSTOMER_AN, wrong)).status_code == 401
    assert (await _verify(client, CUSTOMER_AN, code)).status_code == 401


@pytest.mark.asyncio
async def test_expired_code_rejected(client, db):
    code = await _request(client, CUSTOMER_AN)
    otp = db.query(OtpCode).filter_by(target=CUSTOMER_AN).one()
    otp.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()

    assert (await _verify(client, CUSTOMER_AN, code)).status_code == 401


@pytest.mark.asyncio
async def test_requests_are_rate_limited(client):
    for _ in range(5):
        await _request(client, NEW_PHONE)
    r = await client.post("/api/v1/auth/otp/request", json={"target": NEW_PHONE})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_operator_cannot_use_otp(client):
    code = await _request(client, OPERATOR)
    r = await _verify(client, OPERATOR, code)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_invalid_target_rejected(client):
    r = await client.post("/api/v1/auth/otp/request", json={"target": "not-a-phone"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_otp_only_account_cannot_password_login(client):
    code = await _request(client, NEW_PHONE)
    await _verify(client, NEW_PHONE, code, full_name="Người Mua Mới")

    r = await client.post("/api/v1/auth/login", json={"identifier": NEW_PHONE, "password": "anything"})
    assert r.status_code == 401
