"""Numbers for the developer dashboard (/dev, GET /admin/metrics): how the AI assistant is doing (turns, failures,
latency, tokens, tools, guardrail hits) and the business flow around it (viewings, deals, listings, open cases).

Read only. Same figures as `python scripts/ai_traces.py stats`, computed in SQL so a long window stays cheap.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select, true
from sqlalchemy.orm import Session

from src.db.models import (
    AiTurn,
    AuditLog,
    Booking,
    Deal,
    Escalation,
    EscalationStatus,
    Property,
    User,
)
from src.services import assistant_control

TIMEZONE = "Asia/Ho_Chi_Minh"
RECENT_ERRORS = 10


def _counts(db: Session, column: Any, *where: Any) -> dict[str, int]:
    rows = db.execute(select(column, func.count()).where(*where).group_by(column)).all()
    return {str(getattr(key, "value", key)): n for key, n in rows}


def _ai(db: Session, since: datetime, days: int) -> dict[str, Any]:
    in_window = AiTurn.created_at >= since
    ok = AiTurn.status == "OK"
    row = db.execute(
        select(
            func.count(),
            func.count().filter(AiTurn.guest.is_(True)),
            func.count().filter(AiTurn.status == "ERROR"),
            func.count(func.distinct(AiTurn.conversation_id)),
            func.coalesce(func.sum(AiTurn.prompt_tokens), 0),
            func.coalesce(func.sum(AiTurn.completion_tokens), 0),
            func.coalesce(func.sum(AiTurn.llm_calls), 0),
            func.coalesce(func.sum(AiTurn.tool_calls), 0),
            func.percentile_cont(0.5).within_group(AiTurn.latency_ms).filter(ok),
            func.percentile_cont(0.95).within_group(AiTurn.latency_ms).filter(ok),
        ).where(in_window)
    ).one()
    turns, guests, errors, conversations, tokens_in, tokens_out, llm_calls, tool_calls, p50, p95 = row

    # Turns per day (Vietnam time), every day of the window present so the chart has no gaps
    day = func.date(func.timezone(TIMEZONE, AiTurn.created_at))
    per_day = {
        d.isoformat(): (n, e)
        for d, n, e in db.execute(
            select(day, func.count(), func.count().filter(AiTurn.status == "ERROR")).where(in_window).group_by(day)
        ).all()
    }
    today = datetime.now(ZoneInfo(TIMEZONE)).date()
    daily = []
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        n, e = per_day.get(d, (0, 0))
        daily.append({"date": d, "turns": n, "errors": e})

    # Each tool step inside the turns' JSONB steps
    step = func.jsonb_array_elements(AiTurn.steps).table_valued("value").alias("step")
    name = step.c.value.op("->>")("name")
    failed = case((step.c.value.op("->>")("ok") == "false", 1), else_=0)
    tools = [
        {"name": n or "?", "calls": c, "failed": int(f or 0)}
        for n, c, f in db.execute(
            select(name, func.count(), func.sum(failed))
            .select_from(AiTurn)
            .join(step, true())
            .where(in_window, step.c.value.op("->>")("kind") == "tool")
            .group_by(name)
            .order_by(func.count().desc())
        ).all()
    ]

    error_types = [
        {"type": t or "?", "count": n}
        for t, n in db.execute(
            select(AiTurn.error_type, func.count())
            .where(in_window, AiTurn.status == "ERROR")
            .group_by(AiTurn.error_type)
            .order_by(func.count().desc())
        ).all()
    ]
    recent_errors = [
        {
            "trace_id": t.trace_id,
            "created_at": t.created_at,
            "error_type": t.error_type,
            "error_message": (t.error_message or "")[:300] or None,
            "guest": t.guest,
            "latency_ms": t.latency_ms,
        }
        for t in db.scalars(
            select(AiTurn).where(in_window, AiTurn.status == "ERROR").order_by(AiTurn.id.desc()).limit(RECENT_ERRORS)
        )
    ]
    return {
        "turns": turns,
        "guest_turns": guests,
        "errors": errors,
        "error_rate": errors / turns if turns else 0.0,
        "conversations": conversations,
        "latency_p50_ms": round(p50) if p50 is not None else None,
        "latency_p95_ms": round(p95) if p95 is not None else None,
        "prompt_tokens": int(tokens_in),
        "completion_tokens": int(tokens_out),
        "llm_calls": int(llm_calls),
        "tool_calls": int(tool_calls),
        "daily": daily,
        "tools": tools,
        "error_types": error_types,
        "recent_errors": recent_errors,
    }


def _guardrails(db: Session, since: datetime) -> dict[str, Any]:
    where = (AuditLog.action == "AI_GUARDRAIL", AuditLog.created_at >= since)
    total, blocked = db.execute(
        select(func.count(), func.count().filter(AuditLog.extra["blocked"].astext == "true")).where(*where)
    ).one()
    flag = func.jsonb_array_elements_text(AuditLog.extra["flags"]).table_valued("value").alias("flag")
    flags = [
        {"flag": f, "count": n}
        for f, n in db.execute(
            select(flag.c.value, func.count())
            .select_from(AuditLog)
            .join(flag, true())
            .where(*where)
            .group_by(flag.c.value)
            .order_by(func.count().desc())
        ).all()
    ]
    return {"turns_flagged": total, "blocked_inputs": blocked, "flags": flags}


def summary(db: Session, days: int) -> dict[str, Any]:
    since = datetime.now(UTC) - timedelta(days=days)
    return {
        "days": days,
        "generated_at": datetime.now(UTC),
        "assistant": assistant_control.status(db),
        "ai": _ai(db, since, days),
        "guardrails": _guardrails(db, since),
        "business": {
            # In the window
            "bookings_by_status": _counts(db, Booking.status, Booking.created_at >= since),
            "deals_by_status": _counts(db, Deal.status, Deal.created_at >= since),
            # Right now
            "properties_by_status": _counts(db, Property.status),
            "open_escalations_by_type": _counts(
                db, Escalation.type, Escalation.status.in_([EscalationStatus.OPEN, EscalationStatus.IN_PROGRESS])
            ),
            "users_by_role": _counts(db, User.role),
        },
    }
