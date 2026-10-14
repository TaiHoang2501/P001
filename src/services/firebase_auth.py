"""Firebase Phone Auth: Firebase generates, sends (SMS) and checks the code in the browser; we verify the result.

The browser signs in to Firebase with the phone + SMS code and sends us the Firebase ID token. We check the token's
signature against Google's public keys, that it was issued for our Firebase project, that it comes from a phone
sign-in made in the last `otp_ttl_seconds`, and return the phone number it proves (as "09xxxxxxxx"). No service
account is needed: verifying an ID token only takes the project ID.
"""

import logging
import time
from functools import lru_cache
from typing import Any

import jwt

from src.config import get_settings
from src.core.errors import InvalidCredentialsError, OtpUnavailableError
from src.models.auth import is_phone, normalize_phone

logger = logging.getLogger(__name__)

# Public keys Firebase signs ID tokens with (JWK form of the securetoken@ service account certificates)
JWKS_URL = "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"
# Clock skew allowed between Google and this server
LEEWAY_SECONDS = 60


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    # Keys rotate every few hours; PyJWKClient caches them and refetches on an unknown key id
    return jwt.PyJWKClient(JWKS_URL, cache_keys=True, lifespan=3600, timeout=10)


def _invalid(reason: str) -> InvalidCredentialsError:
    # One message for every failure (as for a wrong local code); the reason only goes to the log
    logger.info("Firebase ID token rejected: %s", reason)
    return InvalidCredentialsError("Code is invalid or expired", details={"new_code_needed": True})


def _decode(id_token: str, project_id: str) -> dict[str, Any]:
    try:
        key = _jwks_client().get_signing_key_from_jwt(id_token).key
    except jwt.PyJWKClientConnectionError as e:
        raise OtpUnavailableError("Could not reach Firebase to check the sign-in code") from e
    except jwt.PyJWTError as e:
        raise _invalid(f"no signing key ({e})") from e
    try:
        return jwt.decode(
            id_token,
            key,
            algorithms=["RS256"],
            audience=project_id,
            issuer=f"https://securetoken.google.com/{project_id}",
            leeway=LEEWAY_SECONDS,
            options={"require": ["exp", "iat", "aud", "iss", "sub", "auth_time"]},
        )
    except jwt.PyJWTError as e:
        raise _invalid(str(e)) from e


def verify_phone_token(id_token: str) -> str:
    """The phone ("09xxxxxxxx") a fresh Firebase phone sign-in proved; InvalidCredentialsError otherwise."""
    settings = get_settings()
    if not settings.firebase_project_id:
        raise OtpUnavailableError("Firebase is not configured (FIREBASE_PROJECT_ID)")
    claims = _decode(id_token, settings.firebase_project_id)
    if not claims.get("sub"):
        raise _invalid("empty sub")
    if (claims.get("firebase") or {}).get("sign_in_provider") != "phone":
        raise _invalid("not a phone sign-in")
    # The SMS code was entered just now, not an hour ago: an ID token lives 1 h, a code only `otp_ttl_seconds`
    age = time.time() - float(claims["auth_time"])
    if age > settings.otp_ttl_seconds + LEEWAY_SECONDS or age < -LEEWAY_SECONDS:
        raise _invalid(f"sign-in is {int(age)} s old")
    phone = normalize_phone(str(claims.get("phone_number") or ""))
    if not is_phone(phone):
        raise _invalid("no Vietnamese mobile number in the token")
    return phone
