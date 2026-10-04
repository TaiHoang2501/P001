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
    # Neutral answer: does not reveal that this is an operator account
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert "operator" not in r.json()["error"]["message"].lower()


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


@pytest.mark.asyncio
async def test_code_hidden_in_production_unless_demo_enables_it(client, monkeypatch):
    from src.config import get_settings

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    get_settings.cache_clear()
    try:
        r = await client.post("/api/v1/auth/otp/request", json={"target": NEW_PHONE})
        assert r.json()["debug_code"] is None

        monkeypatch.setenv("OTP_EXPOSE_CODE", "true")
        get_settings.cache_clear()
        r = await client.post("/api/v1/auth/otp/request", json={"target": NEW_PHONE})
        assert r.json()["debug_code"] is not None
    finally:
        get_settings.cache_clear()


OPERATOR_PHONE, SELLER_PHONE, BUYER_PHONE = "0901234567", "0918765432", "0901111222"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("phone", "role"), [(OPERATOR_PHONE, "CUSTOMER"), (SELLER_PHONE, "CUSTOMER"), (BUYER_PHONE, "OWNER")]
)
async def test_phone_of_another_kind_of_account_is_refused_before_sending_a_code(client, db, phone, role):
    r = await client.post("/api/v1/auth/otp/request", json={"target": phone, "role": role})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "PHONE_IN_USE"
    # No code was sent
    assert db.query(OtpCode).filter(OtpCode.target == phone).count() == 0


@pytest.mark.asyncio
async def test_login_just_sends_a_code_to_a_known_phone(client):
    # Signing in (no purpose = login), even with the matching role: a code, no "already exists"
    for phone, role in ((BUYER_PHONE, "CUSTOMER"), (SELLER_PHONE, "OWNER"), (BUYER_PHONE, None)):
        r = await client.post("/api/v1/auth/otp/request", json={"target": phone, "role": role})
        assert r.status_code == 202, r.text
        assert r.json()["debug_code"]

    code = (await client.post("/api/v1/auth/otp/request", json={"target": BUYER_PHONE})).json()["debug_code"]
    r = await _verify(client, BUYER_PHONE, code)
    assert r.status_code == 200
    assert r.json()["user"]["email"] == CUSTOMER_AN


@pytest.mark.asyncio
@pytest.mark.parametrize("phone", [BUYER_PHONE, SELLER_PHONE, OPERATOR_PHONE])
async def test_sign_up_with_a_phone_already_registered_is_refused(client, db, phone):
    r = await client.post("/api/v1/auth/otp/request", json={"target": phone, "role": "CUSTOMER", "purpose": "signup"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "PHONE_IN_USE"
    assert db.query(OtpCode).filter(OtpCode.target == phone).count() == 0

    # A new number goes through
    r = await client.post(
        "/api/v1/auth/otp/request", json={"target": NEW_PHONE, "role": "CUSTOMER", "purpose": "signup"}
    )
    assert r.status_code == 202


@pytest.mark.asyncio
async def test_verify_with_another_role_is_refused(client):
    code = await _request(client, SELLER_PHONE)
    r = await _verify(client, SELLER_PHONE, code, role="CUSTOMER")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "PHONE_IN_USE"
