"""Langfuse and LangSmith tracing of buyer chat turns (developer observability, like ai_turns; never shown to users).

One chat turn = one Langfuse trace, with the same trace id as the turn's ai_turns row, so the id returned to the
client opens the same turn in both places. The trace root is the turn (input: the buyer's message, output: the
reply); under it the LangChain callback handler records the agent graph: each model call as a generation (model,
tokens, cost) and each tool call. Traces of one conversation share a session, signed-in buyers carry their user id.

LangSmith gets the same turn through its LangChain tracer: the agent graph run is the trace root, tagged with the
ai_turns trace id (metadata `ai_turn_id`) and grouped into threads by `conversation_id`.

Phone numbers and email addresses are masked before anything leaves the server (AC-03); the buyer's name and memory
are left out of LangSmith metadata. Tracing is optional: without keys (and in tests) nothing is sent, and a
Langfuse or LangSmith failure never stops a chat turn. Do not set LANGSMITH_TRACING / LANGCHAIN_TRACING_V2: that
would also trace model calls outside chat turns, without masking.
"""

import logging
import re
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from functools import lru_cache
from typing import Any

import langsmith
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableConfig
from langchain_core.tracers.langchain import LangChainTracer
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


def _mask_value(value: Any) -> Any:
    """Mask strings anywhere in a run's inputs/outputs (messages arrive as objects or as serialized dicts)."""
    if isinstance(value, str):
        return mask_text(value)
    if isinstance(value, dict):
        return {k: _mask_value(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_mask_value(v) for v in value]
    if hasattr(value, "model_dump"):
        return _mask_value(value.model_dump())
    return value


def _mask_run_data(data: dict) -> dict:
    return _mask_value(data)


# Copied from the agent config by LangGraph: personal (the name) or bulky (long-term memory of the buyer)
_HIDDEN_METADATA = {"buyer_name", "buyer_memory"}


def _mask_metadata(metadata: dict) -> dict:
    return {k: _mask_value(v) for k, v in metadata.items() if k not in _HIDDEN_METADATA}


@lru_cache
def get_langsmith() -> langsmith.Client | None:
    settings = get_settings()
    if not settings.langsmith_enabled:
        return None
    try:
        return langsmith.Client(
            api_url=settings.langsmith_endpoint,
            api_key=settings.langsmith_api_key,
            hide_inputs=_mask_run_data,
            hide_outputs=_mask_run_data,
            hide_metadata=_mask_metadata,
            tracing_sampling_rate=settings.langsmith_sample_rate,
            tracing_error_callback=lambda e: logger.warning("LangSmith upload failed: %s", e),
        )
    except Exception:
        logger.exception("could not start LangSmith; chat turns are not traced there")
        return None


def _langsmith_tracer(trace_id: str, config: RunnableConfig, *, streamed: bool) -> BaseCallbackHandler | None:
    client = get_langsmith()
    if client is None:
        return None
    try:
        configurable = config.get("configurable", {})
        user_id = configurable.get("user_id")
        return LangChainTracer(
            project_name=get_settings().langsmith_project,
            client=client,
            tags=["buyer" if user_id is not None else "guest", "stream" if streamed else "sync"],
            metadata={
                "ai_turn_id": trace_id,
                "environment": get_settings().app_env,
                # LangSmith threads group runs by this key: a guest conversation keeps its thread after sign-up
                "conversation_id": configurable.get("conversation_id"),
            },
        )
    except Exception:
        logger.exception("could not start the LangSmith tracer (trace=%s)", trace_id)
        return None


def shutdown() -> None:
    """Send what is still queued (at server shutdown)."""
    client = get_langfuse()
    if client is not None:
        client.shutdown()
    smith = get_langsmith()
    if smith is not None:
        try:
            smith.flush()
        except Exception:
            logger.exception("could not flush LangSmith traces")


class TurnTrace:
    """The Langfuse side of one chat turn; every method is a no-op when tracing is off."""

    def __init__(self, root: Any = None, *handlers: BaseCallbackHandler | None) -> None:
        self._root = root
        self.callbacks: list[BaseCallbackHandler] = [h for h in handlers if h is not None]

    def finish(self, reply: str) -> None:
        if self._root is not None:
            self._root.update(output=reply)

    def fail(self, error: BaseException) -> None:
        if self._root is not None:
            self._root.update(level="ERROR", status_message=f"{type(error).__name__}: {error}"[:500])


@contextmanager
def chat_turn(trace_id: str, config: RunnableConfig, message: str, *, streamed: bool) -> Iterator[TurnTrace]:
    """Trace one turn. `config` is the agent config built by the chat service (user, conversation)."""
    smith = _langsmith_tracer(trace_id, config, streamed=streamed)
    client = get_langfuse()
    if client is None:
        yield TurnTrace(None, smith)
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
            trace = TurnTrace(root, CallbackHandler(public_key=get_settings().langfuse_public_key), smith)
        except Exception:
            logger.exception("could not start the Langfuse trace (trace=%s)", trace_id)
            trace = TurnTrace(None, smith)
        yield trace
