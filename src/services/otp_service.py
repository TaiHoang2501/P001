"""One-time login codes (spec §4.17: Buyer phone + OTP, Seller phone/email + OTP).

Two providers (OTP_PROVIDER): "firebase" = Firebase Phone Auth generates, sends by SMS and checks the code in the
browser, and we verify the resulting ID token (`firebase_auth`); "local" = the codes below, which only reach the
server log (and the API response outside production), for development, tests and the demo.

Only a keyed hash of each code is stored. A code expires after `otp_ttl_seconds`, is burned
after `otp_max_attempts` wrong guesses, and each target may have at most `otp_max_requests` unused
codes per `otp_rate_window_minutes`. Codes that signed someone in do not count: a buyer who signs out
and back in a few times is not locked out, while repeated requests nobody completes still are.
"""

import hashlib
import hmac
import logging
import math
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.core.errors import InvalidCredentialsError, RateLimitedError
from src.db.models import OtpCode, OtpPurpose
from src.models.auth import FirebaseWebConfig, normalize_phone
from src.services import firebase_auth

logger = logging.getLogger(__name__)

CODE_LENGTH = 6


def normalize_target(target: str) -> str:
    return target.strip().lower()


def _hash(target: str, code: str) -> str:
    key = get_settings().jwt_secret.encode()
    return hmac.new(key, f"{target}:{code}".encode(), hashlib.sha256).hexdigest()


def uses_firebase() -> bool:
    return get_settings().otp_provider == "firebase"


def firebase_config() -> FirebaseWebConfig | None:
    """What the browser needs to have Firebase send and check the SMS code; None with local codes."""
    settings = get_settings()
    if not uses_firebase():
        return None
    return FirebaseWebConfig(
        api_key=settings.firebase_web_api_key,
        auth_domain=settings.firebase_auth_domain or f"{settings.firebase_project_id}.firebaseapp.com",
        project_id=settings.firebase_project_id,
    )


def _deliver(target: str, code: str) -> None:
    # Local codes are never sent by SMS (that is Firebase's job with OTP_PROVIDER=firebase): server log only
    logger.info("OTP for %s: %s", target, code)


def request_code(db: Session, target: str, purpose: OtpPurpose = OtpPurpose.LOGIN) -> tuple[str, int]:
    """Create and send a new code. Returns (code, ttl_seconds); callers must not expose the code in production."""
    settings = get_settings()
    target = normalize_target(target)
    now = datetime.now(UTC)

    window = timedelta(minutes=settings.otp_rate_window_minutes)
    unused = (OtpCode.target == target, OtpCode.created_at >= now - window, OtpCode.consumed_at.is_(None))
    recent, oldest = db.execute(select(func.count(), func.min(OtpCode.created_at)).where(*unused)).one()
    if recent >= settings.otp_max_requests:
        # Free again once the oldest unused code leaves the window
        wait = max(1, math.ceil((oldest + window - now).total_seconds() / 60))
        raise RateLimitedError(
            "Too many codes requested; try again later",
            details={"retry_after_minutes": wait},
        )

    code = f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"
    db.add(
        OtpCode(
            target=target,
            purpose=purpose,
            code_hash=_hash(target, code),
            expires_at=now + timedelta(seconds=settings.otp_ttl_seconds),
        )
    )
    db.commit()
    _deliver(target, code)
    return code, settings.otp_ttl_seconds


def check_code(db: Session, target: str, code: str, purpose: OtpPurpose = OtpPurpose.LOGIN) -> OtpCode:
    """Validate `code` against the newest live code for `target` (row-locked, not yet consumed).

    A wrong guess is counted and committed before raising. Call `consume` once the login succeeds.
    """
    settings = get_settings()
    target = normalize_target(target)
    otp = db.scalar(
        select(OtpCode)
        .where(OtpCode.target == target, OtpCode.purpose == purpose, OtpCode.consumed_at.is_(None))
        .order_by(OtpCode.created_at.desc(), OtpCode.id.desc())
        .limit(1)
        .with_for_update()
    )
    # Same message for every failure so the response does not leak why; the details only tell the person who
    # asked for the code what to do next (try again / ask for a new code)
    if otp is None or otp.expires_at <= datetime.now(UTC) or otp.attempts >= settings.otp_max_attempts:
        raise InvalidCredentialsError("Code is invalid or expired", details={"new_code_needed": True})
    if not hmac.compare_digest(otp.code_hash, _hash(target, code.strip())):
        otp.attempts += 1
        db.commit()
        left = settings.otp_max_attempts - otp.attempts
        raise InvalidCredentialsError(
            "Code is invalid or expired", details={"attempts_left": left, "new_code_needed": left <= 0}
        )
    return otp


def check_proof(
    db: Session,
    target: str,
    *,
    code: str | None,
    firebase_id_token: str | None,
    purpose: OtpPurpose = OtpPurpose.LOGIN,
) -> OtpCode | None:
    """Check that the caller controls `target` with the active provider's proof: a Firebase ID token for that
    phone, or one of our local codes. Returns the local code row to `consume` (None for Firebase)."""
    if uses_firebase():
        if firebase_id_token is None:
            raise InvalidCredentialsError("Code is invalid or expired", details={"new_code_needed": True})
        if firebase_auth.verify_phone_token(firebase_id_token) != normalize_phone(normalize_target(target)):
            # A valid sign-in, but for another phone
            raise InvalidCredentialsError("Code is invalid or expired", details={"new_code_needed": True})
        return None
    if code is None:
        raise InvalidCredentialsError("Code is invalid or expired", details={"new_code_needed": True})
    return check_code(db, target, code, purpose)


def consume(otp: OtpCode | None) -> None:
    if otp is not None:
        otp.consumed_at = datetime.now(UTC)
