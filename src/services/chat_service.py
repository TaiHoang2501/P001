"""Runs one chat turn for a buyer (signed in, or a guest who has no account yet) and extracts what the UI renders.

Guests can explore and pick a viewing time, but every buyer-scoped tool answers UNAUTHENTICATED for them;
the turn then reports `needs_account` (and the viewing request the agent tried to send) so the client can
sign the guest up, send that request, and claim the guest conversation for the new account.

The reply text comes from the model, but recommendations, viewing times and booking updates come
only from successful tool results (ok: true), never from what the model says it did (AC-01).

Streaming (`chat_stream`, `guest_chat_stream`): the reply is sent piece by piece while the model writes it,
with a `tools` event each time the agent calls tools; the last event (`done`) carries the same ChatResponse
as the non-streaming endpoints, so cards and bookings still come only from tool results.
"""

import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from src.agents import graph as agent_graph
from src.core.actor import Actor
from src.core.errors import AgentUnavailableError
from src.db.session import get_sessionmaker
from src.models.booking import BookingOut, ViewingTimesOut
from src.models.property import Recommendation
from src.models.schemas import ChatRequest, ChatResponse, PendingViewingRequest
from src.services import buyer_memory, conversation_service

logger = logging.getLogger(__name__)

# Upper bound on agent <-> tool round trips in one turn
_RECURSION_LIMIT = 16
_BOOKING_TOOLS = {"create_viewing_request", "cancel_viewing", "reschedule_viewing"}


def _ok_data(message: ToolMessage) -> Any:
    envelope = message.artifact
    if isinstance(envelope, dict) and envelope.get("ok"):
        return envelope["data"]
    return None


def _guest_thread(conversation_id: str) -> str:
    return f"guest:{conversation_id}"


def _needs_account(message: ToolMessage) -> bool:
    envelope = message.artifact
    return isinstance(envelope, dict) and envelope.get("error", {}).get("code") == "UNAUTHENTICATED"


def _pending_viewing(messages: list[BaseMessage]) -> PendingViewingRequest | None:
    """The last viewing request the agent tried to send without an account, from its own tool call arguments."""
    calls = {c["id"]: c["args"] for m in messages if isinstance(m, AIMessage) for c in m.tool_calls}
    pending = None
    for m in messages:
        if isinstance(m, ToolMessage) and m.name == "create_viewing_request" and _needs_account(m):
            args = calls.get(m.tool_call_id)
            if args is not None:
                try:
                    pending = PendingViewingRequest.model_validate(args)
                except ValueError:
                    logger.warning("unusable create_viewing_request args for guest: %s", args)
    return pending


def _extract(messages: list[BaseMessage]) -> tuple[list[Recommendation], ViewingTimesOut | None, list[BookingOut]]:
    recommendations: list[Recommendation] = []
    viewing_times: ViewingTimesOut | None = None
    bookings: list[BookingOut] = []
    for m in messages:
        if not isinstance(m, ToolMessage) or (data := _ok_data(m)) is None:
            continue
        if m.name == "search_properties":
            recommendations = [Recommendation.model_validate(r) for r in data["results"]]
            if data.get("top_viewing_times"):
                viewing_times = ViewingTimesOut.model_validate(data["top_viewing_times"])
        elif m.name == "check_property_availability":
            viewing_times = ViewingTimesOut.model_validate(data)
        elif m.name in _BOOKING_TOOLS:
            bookings.append(BookingOut.model_validate(data))
    return recommendations, viewing_times, bookings


def _buyer_config(actor: Actor, request: ChatRequest) -> RunnableConfig:
    return {
        # Thread is scoped to the authenticated user, so one buyer can never load another's conversation
        "configurable": {
            "thread_id": f"{actor.id}:{request.conversation_id}",
            "user_id": actor.id,
            "buyer_name": actor.user.full_name,
            "buyer_memory": _memory(actor.id),
        },
        "recursion_limit": _RECURSION_LIMIT,
    }


def _guest_config(request: ChatRequest) -> RunnableConfig:
    """No user_id, so tools only read public data (AC-03: no PII)."""
    return {
        # The client-generated id is random and only known to that browser tab
        "configurable": {
            "thread_id": _guest_thread(request.conversation_id),
            "user_id": None,
            "buyer_name": "Quý khách",
        },
        "recursion_limit": _RECURSION_LIMIT,
    }


async def chat(actor: Actor, request: ChatRequest) -> ChatResponse:
    config = _buyer_config(actor, request)
    new_messages, latency_ms = await _run_turn(config, request.message)
    _record(actor, request.conversation_id, config["configurable"]["thread_id"], new_messages, latency_ms)
    return _response(request.conversation_id, new_messages)


def _memory(user_id: int) -> str | None:
    # A memory read failure must not stop the conversation
    try:
        with get_sessionmaker()() as db:
            return buyer_memory.summary(db, user_id)
    except Exception:
        logger.exception("could not load buyer memory")
        return None


async def guest_chat(request: ChatRequest) -> ChatResponse:
    """A turn for a buyer without an account."""
    new_messages, _ = await _run_turn(_guest_config(request), request.message)
    return _guest_response(request.conversation_id, new_messages)


def _guest_response(conversation_id: str, new_messages: list[BaseMessage]) -> ChatResponse:
    response = _response(conversation_id, new_messages)
    response.needs_account = any(isinstance(m, ToolMessage) and _needs_account(m) for m in new_messages)
    response.pending_viewing = _pending_viewing(new_messages)
    return response


# ---------- Streaming ----------

ChatEvent = tuple[str, dict[str, Any]]


def ensure_agent() -> None:
    """Fail with a normal error response (not a broken stream) when the assistant is not configured."""
    agent_graph.get_agent()


async def chat_stream(actor: Actor, request: ChatRequest) -> AsyncIterator[ChatEvent]:
    config = _buyer_config(actor, request)
    thread_id = config["configurable"]["thread_id"]
    async for name, data in _stream_turn(config, request.message):
        if name != "_final":
            yield name, data
            continue
        _record(actor, request.conversation_id, thread_id, data["messages"], data["latency_ms"])
        yield "done", _response(request.conversation_id, data["messages"]).model_dump(mode="json")


async def guest_chat_stream(request: ChatRequest) -> AsyncIterator[ChatEvent]:
    async for name, data in _stream_turn(_guest_config(request), request.message):
        if name != "_final":
            yield name, data
            continue
        yield "done", _guest_response(request.conversation_id, data["messages"]).model_dump(mode="json")


async def _stream_turn(config: RunnableConfig, message: str) -> AsyncIterator[ChatEvent]:
    """Events of one turn: `token` (a piece of the reply being written), `tools` (the agent is calling tools;
    text streamed before it was only a preface), `error`; then an internal `_final` with the new messages."""
    agent = agent_graph.get_agent()
    started = time.perf_counter()
    try:
        before = len((await agent.aget_state(config)).values.get("messages", []))
        async for mode, payload in agent.astream(
            {"messages": [HumanMessage(message)]}, config, stream_mode=["messages", "updates"]
        ):
            if mode == "messages":
                chunk, meta = payload
                if isinstance(chunk, AIMessageChunk) and meta.get("langgraph_node") == "agent" and chunk.text:
                    yield "token", {"text": chunk.text}
            elif mode == "updates":
                for node, update in payload.items():
                    if node != "agent" or not update:
                        continue
                    calls = [
                        c["name"] for m in update.get("messages", []) if isinstance(m, AIMessage) for c in m.tool_calls
                    ]
                    if calls:
                        yield "tools", {"names": calls}
        messages = (await agent.aget_state(config)).values["messages"][before:]
    except Exception:
        # The response has already started: report the failure as an event, the client shows it in the chat
        logger.exception("agent turn failed (stream)")
        yield (
            "error",
            {"code": "AGENT_UNAVAILABLE", "message": "AI assistant is temporarily unavailable, please try again"},
        )
        return
    yield "_final", {"messages": messages, "latency_ms": int((time.perf_counter() - started) * 1000)}


async def claim_guest(actor: Actor, conversation_id: str) -> bool:
    """After a guest signs up, move the guest conversation into the new account's thread so the agent keeps context."""
    agent = agent_graph.get_agent()
    guest = (await agent.aget_state({"configurable": {"thread_id": _guest_thread(conversation_id)}})).values
    messages = guest.get("messages", [])
    target: RunnableConfig = {"configurable": {"thread_id": f"{actor.id}:{conversation_id}"}}
    if not messages or (await agent.aget_state(target)).values.get("messages"):
        return False
    await agent.aupdate_state(target, {"messages": messages}, as_node="agent")
    await agent.checkpointer.adelete_thread(_guest_thread(conversation_id))
    return True


async def _run_turn(config: RunnableConfig, message: str) -> tuple[list[BaseMessage], int]:
    agent = agent_graph.get_agent()  # raises AgentUnavailableError when no API key is configured
    started = time.perf_counter()
    try:
        before = len((await agent.aget_state(config)).values.get("messages", []))
        result = await agent.ainvoke({"messages": [HumanMessage(message)]}, config)
    except Exception as e:
        logger.exception("agent turn failed")
        raise AgentUnavailableError("AI assistant is temporarily unavailable, please try again") from e
    return result["messages"][before:], int((time.perf_counter() - started) * 1000)


def _response(conversation_id: str, new_messages: list[BaseMessage]) -> ChatResponse:
    last = new_messages[-1]
    reply = last.text if isinstance(last, AIMessage) else ""
    recommendations, viewing_times, bookings = _extract(new_messages)
    return ChatResponse(
        reply=reply,
        conversation_id=conversation_id,
        recommendations=recommendations,
        viewing_times=viewing_times,
        bookings=bookings,
    )


def _record(actor: Actor, client_id: str, thread_id: str, messages: list[BaseMessage], latency_ms: int) -> None:
    # Tool actions are already committed by the services; a logging failure must not hide the reply
    try:
        with get_sessionmaker()() as db:
            conversation_service.record_turn(
                db, actor, client_id=client_id, thread_id=thread_id, messages=messages, latency_ms=latency_ms
            )
    except Exception:
        logger.exception("failed to record chat turn")
