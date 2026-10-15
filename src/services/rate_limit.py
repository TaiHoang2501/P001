"""Chat rate limits: every message costs a model call, so one buyer (or one guest IP) gets a bounded number.

Sliding windows kept in process memory: each API instance counts on its own, which is enough to stop a
script or a stuck client from spamming the assistant. Signed-in buyers are counted per account,
guests per client IP (uvicorn runs with --proxy-headers, so that is the address forwarded by the proxy).
"""

import math
import threading
import time
from collections import defaultdict, deque

from src.config import get_settings
from src.core.errors import RateLimitedError

_lock = threading.Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)
_WINDOWS = (("minute", 60.0), ("hour", 3600.0))


def _limits(guest: bool) -> dict[str, int]:
    s = get_settings()
    if guest:
        return {"minute": s.guest_chat_messages_per_minute, "hour": s.guest_chat_messages_per_hour}
    return {"minute": s.chat_messages_per_minute, "hour": s.chat_messages_per_hour}


def check_chat(key: str, *, guest: bool) -> None:
    """Count one chat message for `key`, or raise RateLimitedError (429) with retry_after_seconds."""
    limits = _limits(guest)
    now = time.monotonic()
    with _lock:
        hits = _hits[key]
        while hits and hits[0] <= now - 3600.0:
            hits.popleft()
        for name, seconds in _WINDOWS:
            recent = [t for t in hits if t > now - seconds]
            if len(recent) >= limits[name]:
                # Free again once the oldest message counted in this window leaves it
                wait = math.ceil(recent[-limits[name]] + seconds - now)
                raise RateLimitedError(
                    "Too many chat messages; try again later",
                    details={"retry_after_seconds": max(1, wait), "scope": "chat"},
                )
        hits.append(now)


def reset() -> None:
    """Forget every count (tests)."""
    with _lock:
        _hits.clear()
