"""Developer traces of chat turns (table ai_turns): every turn, guests and failed turns included.

A `TurnTracer` rides along with one agent run (LangChain callbacks) and notes each model call and each tool call
with its timing; `save` stores the turn with its outcome. The trace id is also written to the server log and
returned with the reply, so a problem a user reports leads straight to its trace (see scripts/ai_traces.py).
These are developer tools: nothing here is shown to buyers, sellers or operators.
"""

import logging
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import ToolMessage
from langchain_core.outputs import LLMResult
from sqlalchemy import delete
from sqlalchemy.orm import Session

from src.config import get_settings
from src.db.models import AiConversation, AiTurn

logger = logging.getLogger(__name__)

# Long tool results / errors are cut in the trace (the full tool result is in ai_messages)
_TEXT_LIMIT = 500


class TurnTracer(BaseCallbackHandler):
    """Collects the steps of one turn. Runs inline (no thread pool) so the steps keep their order."""

    run_inline = True

    def __init__(self) -> None:
        self.trace_id = uuid.uuid4().hex
        self.started = time.perf_counter()
        self.steps: list[dict[str, Any]] = []
        self._open: dict[UUID, dict[str, Any]] = {}

    def elapsed_ms(self) -> int:
        return int((time.perf_counter() - self.started) * 1000)

    def _begin(self, run_id: UUID, kind: str, name: str | None) -> None:
        step: dict[str, Any] = {"kind": kind, "name": name, "at_ms": self.elapsed_ms(), "ms": None, "ok": None}
        self.steps.append(step)
        self._open[run_id] = step

    def _end(self, run_id: UUID, **fields: Any) -> dict[str, Any] | None:
        step = self._open.pop(run_id, None)
        if step is not None:
            step["ms"] = self.elapsed_ms() - step["at_ms"]
            step.update(fields)
        return step

    # ---- model calls ----

    def on_chat_model_start(self, serialized: dict[str, Any], messages: Any, *, run_id: UUID, **kwargs: Any) -> None:
        params = kwargs.get("invocation_params") or {}
        self._begin(run_id, "llm", params.get("model") or params.get("model_name") or (serialized or {}).get("name"))

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        message = None
        if response.generations and response.generations[0]:
            message = getattr(response.generations[0][0], "message", None)
        usage = getattr(message, "usage_metadata", None) or {}
        meta = getattr(message, "response_metadata", None) or {}
        step = self._end(
            run_id,
            ok=True,
            prompt_tokens=usage.get("input_tokens"),
            completion_tokens=usage.get("output_tokens"),
            # Part of prompt_tokens Claude read from its prompt cache (llm.get_llm(prompt_cache=True))
            cache_read_tokens=(usage.get("input_token_details") or {}).get("cache_read"),
            tool_calls=[c["name"] for c in (getattr(message, "tool_calls", None) or [])],
        )
        if step is not None and meta.get("model_name"):
            step["name"] = meta["model_name"]

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._end(run_id, ok=False, error=_describe(error))

    # ---- tool calls ----

    def on_tool_start(self, serialized: dict[str, Any], input_str: str, *, run_id: UUID, **kwargs: Any) -> None:
        self._begin(run_id, "tool", (serialized or {}).get("name") or kwargs.get("name"))

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        envelope = output.artifact if isinstance(output, ToolMessage) else None
        if isinstance(envelope, dict):
            error = envelope.get("error") or {}
            self._end(run_id, ok=bool(envelope.get("ok")), error=error.get("code") if error else None)
        else:
            self._end(run_id, ok=True)

    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._end(run_id, ok=False, error=_describe(error))


def _describe(error: BaseException) -> str:
    return f"{type(error).__name__}: {error}"[:_TEXT_LIMIT]


def save(
    db: Session,
    tracer: TurnTracer,
    *,
    message: str,
    buyer_id: int | None,
    conversation: AiConversation | None,
    streamed: bool,
    error: BaseException | None = None,
) -> AiTurn:
    """Store the turn (no commit). A failed turn keeps the steps that ran before the failure."""
    llm = [s for s in tracer.steps if s["kind"] == "llm"]
    tools = [s for s in tracer.steps if s["kind"] == "tool"]

    def total(key: str) -> int | None:
        values = [s[key] for s in llm if s.get(key) is not None]
        return sum(values) if values else None

    turn = AiTurn(
        trace_id=tracer.trace_id,
        conversation_id=conversation.id if conversation is not None else None,
        buyer_id=buyer_id,
        guest=buyer_id is None,
        streamed=streamed,
        message=message,
        status="ERROR" if error is not None else "OK",
        error_type=type(error).__name__ if error is not None else None,
        error_message=str(error)[:_TEXT_LIMIT] if error is not None else None,
        model=next((s["name"] for s in reversed(llm) if s.get("ok") and s.get("name")), None),
        llm_calls=len(llm),
        tool_calls=len(tools),
        prompt_tokens=total("prompt_tokens"),
        completion_tokens=total("completion_tokens"),
        cache_read_tokens=total("cache_read_tokens"),
        latency_ms=tracer.elapsed_ms(),
        steps=tracer.steps,
    )
    db.add(turn)
    db.flush()
    return turn


def purge_old(db: Session, now: datetime | None = None) -> int:
    """Periodic job: drop traces (and guest conversations nobody claimed) older than AI_TRACE_RETENTION_DAYS."""
    cutoff = (now or datetime.now(UTC)) - timedelta(days=get_settings().ai_trace_retention_days)
    turns = db.execute(delete(AiTurn).where(AiTurn.created_at < cutoff)).rowcount
    db.execute(delete(AiConversation).where(AiConversation.buyer_id.is_(None), AiConversation.last_message_at < cutoff))
    db.commit()
    return turns
