"""One-time login codes (spec §4.17: Buyer phone + OTP, Seller phone/email + OTP).

Only a keyed hash of each code is stored. A code expires after `otp_ttl_seconds`, is burned
after `otp_max_attempts` wrong guesses, and each target may request at most `otp_max_requests`
codes per `otp_rate_window_minutes`.
"""

import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.core.errors import InvalidCredentialsError, RateLimitedError
from src.db.models import OtpCode, OtpPurpose

logger = logging.getLogger(__name__)

CODE_LENGTH = 6


def normalize_target(target: str) -> str:
    return target.strip().lower()


def _hash(target: str, code: str) -> str:
    key = get_settings().jwt_secret.encode()
    return hmac.new(key, f"{target}:{code}".encode(), hashlib.sha256).hexdigest()


def _deliver(target: str, code: str) -> None:
    # SMS/Zalo provider is TBD (spec §10 Q18); until then the code only goes to the server log
    logger.info("OTP for %s: %s", target, code)


def request_code(db: Session, target: str, purpose: OtpPurpose = OtpPurpose.LOGIN) -> tuple[str, int]:
    """Create and send a new code. Returns (code, ttl_seconds); callers must not expose the code in production."""
    settings = get_settings()
    target = normalize_target(target)
    now = datetime.now(UTC)

    window_start = now - timedelta(minutes=settings.otp_rate_window_minutes)
    recent = db.scalar(select(func.count()).where(OtpCode.target == target, OtpCode.created_at >= window_start))
    if recent >= settings.otp_max_requests:
        raise RateLimitedError(
            "Too many codes requested; try again later",
            details={"retry_after_minutes": settings.otp_rate_window_minutes},
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
    # Same error for every failure so the response does not leak why
    invalid = InvalidCredentialsError("Code is invalid or expired")
    if otp is None or otp.expires_at <= datetime.now(UTC) or otp.attempts >= settings.otp_max_attempts:
        raise invalid
    if not hmac.compare_digest(otp.code_hash, _hash(target, code.strip())):
        otp.attempts += 1
        db.commit()
        raise invalid
    return otp


def consume(otp: OtpCode) -> None:
    otp.consumed_at = datetime.now(UTC)
