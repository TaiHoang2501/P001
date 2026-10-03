"""What the agent remembers about a signed-in buyer across conversations (buyer_profiles).

- The last search criteria (budget, project, bedrooms, preferences) → `preferences`, `budget_*`.
- The free windows the buyer gave for viewings → `viewing_preference.windows` (past ones are dropped).

Written from the agent's own tool calls, read back into the system prompt of every later turn, so the buyer
does not repeat their needs or free time. Only the buyer's own data is stored (no PII beyond the account).
"""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from src.config import get_settings
from src.db.models import BuyerProfile
from src.db.session import get_sessionmaker
from src.models.property import SearchCriteria

logger = logging.getLogger(__name__)

# Criteria worth remembering (limit/priorities/keyword are about one search, not the buyer)
_REMEMBERED = (
    "project_codes",
    "property_types",
    "budget_min",
    "budget_max",
    "bedrooms_min",
    "area_min",
    "preferred_bedrooms",
    "preferred_area_m2",
    "preferred_directions",
    "preferred_views",
    "preferred_furnishing",
    "preferred_floor_min",
    "preferred_floor_max",
)
_MAX_WINDOWS = 10


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return getattr(value, "value", value)


def _profile(db: Session, user_id: int) -> BuyerProfile:
    profile = db.get(BuyerProfile, user_id, with_for_update=True)
    if profile is None:
        profile = BuyerProfile(user_id=user_id)
        db.add(profile)
    return profile


def remember_criteria(user_id: int, criteria: dict[str, Any]) -> None:
    """After a search: keep the criteria the buyer stated (a failure never breaks the chat)."""
    try:
        parsed = SearchCriteria.model_validate(criteria)
        kept = {k: _jsonable(v) for k in _REMEMBERED if (v := getattr(parsed, k)) not in (None, [])}
        if not kept:
            return
        with get_sessionmaker()() as db:
            profile = _profile(db, user_id)
            profile.preferences = kept
            profile.budget_min_vnd = parsed.budget_min
            profile.budget_max_vnd = parsed.budget_max
            db.commit()
    except Exception:
        logger.exception("could not remember buyer criteria")


def remember_windows(user_id: int, windows: list[dict[str, Any]]) -> None:
    """After an availability check: keep the buyer's free windows (newest first, future only)."""
    try:
        now = datetime.now(UTC)
        fresh = []
        for w in windows:
            start, end = datetime.fromisoformat(str(w["start_at"])), datetime.fromisoformat(str(w["end_at"]))
            if end > now and start.tzinfo is not None:
                fresh.append({"start_at": start.isoformat(), "end_at": end.isoformat()})
        if not fresh:
            return
        with get_sessionmaker()() as db:
            profile = _profile(db, user_id)
            known = [w for w in (profile.viewing_preference or {}).get("windows", []) if w not in fresh]
            profile.viewing_preference = {
                **(profile.viewing_preference or {}),
                "windows": _future(fresh + known)[:_MAX_WINDOWS],
            }
            db.commit()
    except Exception:
        logger.exception("could not remember buyer free windows")


def _future(windows: list[dict[str, str]]) -> list[dict[str, str]]:
    now = datetime.now(UTC)
    return [w for w in windows if datetime.fromisoformat(w["end_at"]) > now]


def known_windows(db: Session, user_id: int) -> list[dict[str, str]]:
    profile = db.get(BuyerProfile, user_id)
    return _future((profile.viewing_preference or {}).get("windows", [])) if profile else []


def known_criteria(db: Session, user_id: int) -> dict[str, Any]:
    profile = db.get(BuyerProfile, user_id)
    return dict(profile.preferences or {}) if profile else {}


def summary(db: Session, user_id: int) -> str | None:
    """Plain-language memory for the system prompt, or None when nothing is known yet."""
    criteria, windows = known_criteria(db, user_id), known_windows(db, user_id)
    if not criteria and not windows:
        return None
    lines = []
    if criteria:
        lines.append(f"- Tiêu chí tìm căn gần nhất (dạng tham số search_properties): {criteria}")
    if windows:
        tz = ZoneInfo(get_settings().timezone)
        spans = [
            f"{datetime.fromisoformat(w['start_at']).astimezone(tz):%H:%M %d/%m}"
            f"–{datetime.fromisoformat(w['end_at']).astimezone(tz):%H:%M %d/%m}"
            f" ({w['start_at']} → {w['end_at']})"
            for w in windows
        ]
        lines.append("- Khung giờ rảnh khách đã nói: " + "; ".join(spans))
    return "\n".join(lines)
