"""Firebase Phone Auth (OTP_PROVIDER=firebase): Firebase sends and checks the SMS code, we verify its ID token."""

import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from src.config import get_settings
from src.db.models import OtpCode
from src.services import firebase_auth
from tests.helpers import BUYER_PHONES, CUSTOMER_AN, UNCLAIMED_RED_BOOK, UNCLAIMED_RED_BOOK_PHONE

PROJECT = "bookingbot-test"
NEW_PHONE = "0977123456"
BUYER = BUYER_PHONES[CUSTOMER_AN]
_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def firebase(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "otp_provider", "firebase")
    monkeypatch.setattr(settings, "firebase_project_id", PROJECT)
    monkeypatch.setattr(settings, "firebase_web_api_key", "test-web-key")
    # Google's public keys -> our test key
    fake = SimpleNamespace(get_signing_key_from_jwt=lambda _token: SimpleNamespace(key=_KEY.public_key()))
    monkeypatch.setattr(firebase_auth, "_jwks_client", lambda: fake)


def _token(phone: str = BUYER, *, project: str = PROJECT, auth_age: int = 10, provider: str = "phone") -> str:
    now = int(time.time())
    claims = {
        "iss": f"https://securetoken.google.com/{project}",
        "aud": project,
        "sub": "firebase-uid-1",
        "iat": now - auth_age,
        "exp": now - auth_age + 3600,
        "auth_time": now - auth_age,
        "phone_number": "+84" + phone[1:],
        "firebase": {"sign_in_provider": provider},
    }
    return jwt.encode(claims, _KEY, algorithm="RS256", headers={"kid": "k1"})


async def _verify(client, target: str, token: str, **signup):
    return await client.post("/api/v1/auth/otp/verify", json={"target": target, "firebase_id_token": token, **signup})


@pytest.mark.asyncio
async def test_request_checks_then_hands_sending_to_firebase(client, db):
    before = db.query(OtpCode).count()
    r = await client.post("/api/v1/auth/otp/request", json={"target": BUYER, "role": "CUSTOMER"})
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["provider"] == "firebase"
    assert body["firebase"] == {
        "api_key": "test-web-key",
        "auth_domain": f"{PROJECT}.firebaseapp.com",
        "project_id": PROJECT,
    }
    assert body["debug_code"] is None
    assert body["account_exists"] is True
    # No local code is made (Firebase makes and sends it)
    assert db.query(OtpCode).count() == before


@pytest.mark.asyncio
async def test_request_still_refuses_a_phone_of_another_kind_before_any_sms(client):
    r = await client.post("/api/v1/auth/otp/request", json={"target": BUYER, "role": "OWNER"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "PHONE_IN_USE"


@pytest.mark.asyncio
async def test_existing_buyer_logs_in_with_firebase_token(client):
    r = await _verify(client, BUYER, _token())
    assert r.status_code == 200, r.text
    assert r.json()["user"]["role"] == "CUSTOMER"


@pytest.mark.asyncio
async def test_new_phone_signs_up_with_the_same_token(client):
    token = _token(NEW_PHONE)
    r = await _verify(client, NEW_PHONE, token)
    assert r.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"
    r = await _verify(client, NEW_PHONE, token, full_name="Người Mua Mới")
    assert r.status_code == 200, r.text


@pytest.mark.parametrize(
    "token",
    [
        _token(NEW_PHONE),  # proves another phone
        _token(project="someone-else"),  # another Firebase project
        _token(auth_age=3600),  # SMS code entered long ago
        _token(provider="password"),  # not a phone sign-in
        "x" * 40,  # not a JWT
    ],
)
@pytest.mark.asyncio
async def test_bad_tokens_are_refused(client, token):
    r = await _verify(client, BUYER, token)
    assert r.status_code == 401, r.text
    assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_forged_signature_is_refused(client):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    claims = jwt.decode(_token(), options={"verify_signature": False})
    r = await _verify(client, BUYER, jwt.encode(claims, other, algorithm="RS256"))
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_local_codes_are_not_accepted_in_firebase_mode(client):
    r = await client.post("/api/v1/auth/otp/verify", json={"target": BUYER, "code": "123456"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_seller_verifies_red_book_with_firebase(client):
    r = await _verify(
        client, UNCLAIMED_RED_BOOK_PHONE, _token(UNCLAIMED_RED_BOOK_PHONE), full_name="Chủ Mới", role="OWNER"
    )
    assert r.status_code == 200, r.text
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    claim = {k: v for k, v in UNCLAIMED_RED_BOOK.items() if k != "id"}
    r = await client.post("/api/v1/owner/ownership/claim", json=claim, headers=headers)
    assert r.status_code == 200, r.text
    challenge = r.json()
    assert challenge["provider"] == "firebase" and challenge["debug_code"] is None

    url = f"/api/v1/owner/ownership/{challenge['verification_id']}/confirm"
    # A sign-in to another phone does not prove the red book's phone, and counts as a wrong try
    r = await client.post(url, json={"firebase_id_token": _token(NEW_PHONE)}, headers=headers)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "OTP_INVALID"

    r = await client.post(url, json={"firebase_id_token": _token(UNCLAIMED_RED_BOOK_PHONE)}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "VERIFIED"
