"""Langfuse tracing of buyer chat turns (developer observability, like ai_turns; never shown to users).

One chat turn = one Langfuse trace, with the same trace id as the turn's ai_turns row, so the id returned to the
client opens the same turn in both places. The trace root is the turn (input: the buyer's message, output: the
reply); under it the LangChain callback handler records the agent graph: each model call as a generation (model,
tokens, cost) and each tool call. Traces of one conversation share a session, signed-in buyers carry their user id.

Phone numbers and email addresses are masked before anything leaves the server (AC-03). Tracing is optional:
without keys (and in tests) nothing is sent, and a Langfuse failure never stops a chat turn.
"""

import logging
import re
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from functools import lru_cache
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableConfig
from langfuse import Langfuse, propagate_attributes
from langfuse.langchain import CallbackHandler
from langfuse.span_filter import is_default_export_span
from langfuse.types import MaskOtelSpansParams, MaskOtelSpansResult, OtelSpanPatch
from opentelemetry.sdk.trace import ReadableSpan

from src.config import get_settings

logger = logging.getLogger(__name__)

TURN_NAME = "buyer-chat-turn"
# Name of the agent graph run under the turn (LangGraph's default is "LangGraph")
AGENT_RUN_NAME = "buyer-agent"

# Vietnamese phone numbers (0xx / +84 / 84, with or without separators) and email addresses
_PHONE = re.compile(r"(?<!\d)(?:\+?84|0)[35789](?:[\s.-]?\d){8}(?!\d)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def mask_text(text: str) -> str:
    return _EMAIL.sub("[email]", _PHONE.sub("[phone]", text))


# LangGraph's routing edge after each model call: a leaf span that says no more than the next node in the tree
_NOISE_SPANS = {"tools_condition"}


def _export_span(span: ReadableSpan) -> bool:
    return span.name not in _NOISE_SPANS and is_default_export_span(span)


def _mask_spans(*, params: MaskOtelSpansParams) -> MaskOtelSpansResult | None:
    """Export-stage masking: covers the turn root and everything the LangChain handler records."""
    patches = {}
    for identifier, span in params.spans.items():
        changed = {}
        for key, value in span.attributes.items():
            if isinstance(value, str) and (masked := mask_text(value)) != value:
                changed[key] = masked
        if changed:
            patches[identifier] = OtelSpanPatch(set_attributes=changed)
    return MaskOtelSpansResult(span_patches=patches) if patches else None


@lru_cache
def get_langfuse() -> Langfuse | None:
    settings = get_settings()
    if not settings.langfuse_enabled:
        return None
    try:
        return Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            base_url=settings.langfuse_base_url,
            environment=settings.app_env,
            sample_rate=settings.langfuse_sample_rate,
            mask_otel_spans=_mask_spans,
            should_export_span=_export_span,
        )
    except Exception:
        logger.exception("could not start Langfuse; chat turns are not traced there")
        return None


def shutdown() -> None:
    """Send what is still queued (at server shutdown)."""
    client = get_langfuse()
    if client is not None:
        client.shutdown()


class TurnTrace:
    """The Langfuse side of one chat turn; every method is a no-op when tracing is off."""

    def __init__(self, root: Any = None, handler: BaseCallbackHandler | None = None) -> None:
        self._root = root
        self.callbacks: list[BaseCallbackHandler] = [handler] if handler is not None else []

    def finish(self, reply: str) -> None:
        if self._root is not None:
            self._root.update(output=reply)

    def fail(self, error: BaseException) -> None:
        if self._root is not None:
            self._root.update(level="ERROR", status_message=f"{type(error).__name__}: {error}"[:500])


@contextmanager
def chat_turn(trace_id: str, config: RunnableConfig, message: str, *, streamed: bool) -> Iterator[TurnTrace]:
    """Trace one turn. `config` is the agent config built by the chat service (user, conversation)."""
    client = get_langfuse()
    if client is None:
        yield TurnTrace()
        return
    configurable = config.get("configurable", {})
    user_id = configurable.get("user_id")
    with ExitStack() as stack:
        try:
            root = stack.enter_context(
                client.start_as_current_observation(
                    trace_context={"trace_id": trace_id},
                    name=TURN_NAME,
                    as_type="agent",
                    input=message,
                    metadata={"streamed": streamed, "thread_id": configurable.get("thread_id")},
                )
            )
            stack.enter_context(
                propagate_attributes(
                    trace_name=TURN_NAME,
                    user_id=str(user_id) if user_id is not None else None,
                    # The client's conversation id: a guest conversation keeps its session after sign-up
                    session_id=configurable.get("conversation_id"),
                    tags=["buyer" if user_id is not None else "guest", "stream" if streamed else "sync"],
                )
            )
            trace = TurnTrace(root, CallbackHandler(public_key=get_settings().langfuse_public_key))
        except Exception:
            logger.exception("could not start the Langfuse trace (trace=%s)", trace_id)
            trace = TurnTrace()
        yield trace
