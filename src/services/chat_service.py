"""Runs one chat turn for a buyer (signed in, or a guest who has no account yet) and extracts what the UI renders.

Guests can explore and pick a viewing time, but every buyer-scoped tool answers UNAUTHENTICATED for them;
the turn then reports `needs_account` (and the viewing request the agent tried to send) so the client can
sign the guest up, send that request, and claim the guest conversation for the new account.

The reply text comes from the model, but recommendations, viewing times and booking updates come
only from successful tool results (ok: true), never from what the model says it did (AC-01).
"""

import logging
import time
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from src.agents import graph as agent_graph
from src.core.actor import Actor
from src.core.errors import AgentUnavailableError
from src.db.session import get_sessionmaker
from src.models.booking import BookingOut, ViewingTimesOut
from src.models.property import Recommendation
from src.models.schemas import ChatRequest, ChatResponse, PendingViewingRequest
from src.services import conversation_service

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
        elif m.name == "check_property_availability":
            viewing_times = ViewingTimesOut.model_validate(data)
        elif m.name in _BOOKING_TOOLS:
            bookings.append(BookingOut.model_validate(data))
    return recommendations, viewing_times, bookings


async def chat(actor: Actor, request: ChatRequest) -> ChatResponse:
    config: RunnableConfig = {
        # Thread is scoped to the authenticated user, so one buyer can never load another's conversation
        "configurable": {
            "thread_id": f"{actor.id}:{request.conversation_id}",
            "user_id": actor.id,
            "buyer_name": actor.user.full_name,
        },
        "recursion_limit": _RECURSION_LIMIT,
    }
    new_messages, latency_ms = await _run_turn(config, request.message)
    _record(actor, request.conversation_id, config["configurable"]["thread_id"], new_messages, latency_ms)
    return _response(request.conversation_id, new_messages)


async def guest_chat(request: ChatRequest) -> ChatResponse:
    """A turn for a buyer without an account: no user_id, so tools only read public data (AC-03: no PII)."""
    config: RunnableConfig = {
        # The client-generated id is random and only known to that browser tab
        "configurable": {
            "thread_id": _guest_thread(request.conversation_id),
            "user_id": None,
            "buyer_name": "Quý khách",
        },
        "recursion_limit": _RECURSION_LIMIT,
    }
    new_messages, _ = await _run_turn(config, request.message)
    response = _response(request.conversation_id, new_messages)
    response.needs_account = any(isinstance(m, ToolMessage) and _needs_account(m) for m in new_messages)
    response.pending_viewing = _pending_viewing(new_messages)
    return response


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
