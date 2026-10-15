"""Chat rate limits: every message costs a model call, so one buyer (or one guest IP) gets a bounded number.

Counted in the database (rate_limit_hits), so the limits hold across every API instance (Render, Cloud Run).
Signed-in buyers are counted per account, guests per client IP, and all guests together have a daily cap: a
script with many IPs still cannot run up the model bill, while signed-in buyers are not affected by it.

The guest IP is read from X-Forwarded-For counting from the right (`client_ip`): the platform's proxy appends
the address it saw, so entries a client typed into the header themselves are never used.
"""

from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.core.errors import RateLimitedError
from src.db.models import RateLimitHit

# Every guest message is also counted under this key, for the daily cap on all guests together
GUESTS_KEY = "guests"
_KEEP = timedelta(hours=25)


def client_ip(request: Request) -> str:
    """The guest's address. CLIENT_IP_HEADER names a header the platform sets itself (and strips from clients);
    otherwise the TRUSTED_PROXY_HOPS-th X-Forwarded-For entry from the right, the one our proxies appended."""
    settings = get_settings()
    if settings.client_ip_header and (value := request.headers.get(settings.client_ip_header, "").strip()):
        return value
    hops = settings.trusted_proxy_hops
    forwarded = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    if hops > 0 and forwarded:
        return forwarded[-hops] if len(forwarded) >= hops else forwarded[0]
    return request.client.host if request.client else "unknown"


def _retry_after(db: Session, key: str, now: datetime, window: timedelta, count: int, limit: int) -> int:
    """Seconds until enough of the counted messages leave the window for one more to fit."""
    oldest = db.scalar(
        select(RateLimitHit.created_at)
        .where(RateLimitHit.key == key, RateLimitHit.created_at >= now - window)
        .order_by(RateLimitHit.created_at)
        .offset(count - limit)
        .limit(1)
    )
    if oldest is None:
        return 1
    return max(1, int((oldest + window - now).total_seconds()) + 1)


def _check(db: Session, key: str, now: datetime, limits: list[tuple[timedelta, int]], scope: str) -> None:
    longest = max(window for window, _ in limits)
    counts = db.execute(
        select(*(func.count().filter(RateLimitHit.created_at >= now - window) for window, _ in limits)).where(
            RateLimitHit.key == key, RateLimitHit.created_at >= now - longest
        )
    ).one()
    for (window, limit), count in zip(limits, counts, strict=True):
        if count >= limit:
            raise RateLimitedError(
                "Too many chat messages; try again later",
                details={"retry_after_seconds": _retry_after(db, key, now, window, count, limit), "scope": scope},
            )


def check_chat(db: Session, key: str, *, guest: bool) -> None:
    """Count one chat message for `key` ("user:7", "ip:1.2.3.4"), or raise RateLimitedError (429)."""
    s = get_settings()
    now = datetime.now(UTC)
    # Messages of the same key (two tabs at once) are counted one after the other, so both cannot take the last one
    db.execute(select(func.pg_advisory_xact_lock(func.hashtext(key))))
    if guest:
        per_key = [
            (timedelta(minutes=1), s.guest_chat_messages_per_minute),
            (timedelta(hours=1), s.guest_chat_messages_per_hour),
        ]
    else:
        per_key = [(timedelta(minutes=1), s.chat_messages_per_minute), (timedelta(hours=1), s.chat_messages_per_hour)]
    try:
        _check(db, key, now, per_key, "chat")
        if guest:
            _check(db, GUESTS_KEY, now, [(timedelta(days=1), s.guest_chat_messages_per_day_total)], "chat_guest_daily")
    except RateLimitedError:
        db.rollback()
        raise
    db.add(RateLimitHit(key=key, created_at=now))
    if guest:
        db.add(RateLimitHit(key=GUESTS_KEY, created_at=now))
    db.commit()


def purge_old(db: Session) -> int:
    """Drop counts no limit looks at any more (background job)."""
    result = db.execute(delete(RateLimitHit).where(RateLimitHit.created_at < datetime.now(UTC) - _KEEP))
    db.commit()
    return result.rowcount or 0
