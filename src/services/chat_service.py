"""Runs one chat turn for a buyer (signed in, or a guest who has no account yet) and extracts what the UI renders.

Guests can explore and pick a viewing time, but every buyer-scoped tool answers UNAUTHENTICATED for them;
the turn then reports `needs_account` (and the viewing request the agent tried to send) so the client can
sign the guest up, send that request, and claim the guest conversation for the new account.

The reply text comes from the model, but recommendations, viewing times and booking updates come
only from successful tool results (ok: true), never from what the model says it did (AC-01).

Streaming (`chat_stream`, `guest_chat_stream`): the reply is sent piece by piece while the model writes it,
with a `tools` event each time the agent calls tools; the last event (`done`) carries the same ChatResponse
as the non-streaming endpoints, so cards and bookings still come only from tool results.

Guardrails (src/agents/guardrails.py) wrap every turn: the buyer's message is screened before the model sees it
(personal data masked; a prompt-injection attempt gets a fixed reply without calling the model), and the final
reply is screened before it is returned and kept (a reply breaking a rule is replaced, also in the conversation
state, so the model does not build on it). What a guardrail changed is written to audit_logs.
"""

import logging
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from src.agents import graph as agent_graph
from src.agents import guardrails
from src.core.actor import Actor
from src.core.errors import AgentUnavailableError
from src.db.session import get_sessionmaker
from src.models.booking import BookingOut, ViewingTimesOut
from src.models.property import Recommendation
from src.models.schemas import ChatRequest, ChatResponse, PendingViewingRequest
from src.services import ai_trace, audit, buyer_memory, conversation_service, llm_observability
from src.services.ai_trace import TurnTracer

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


def _detailed(messages: list[BaseMessage]) -> list[int]:
    """Homes opened with get_property_detail this turn (successfully), in order, once each."""
    ids: list[int] = []
    for m in messages:
        if isinstance(m, ToolMessage) and m.name == "get_property_detail" and (data := _ok_data(m)) is not None:
            if data.get("id") is not None and data["id"] not in ids:
                ids.append(data["id"])
    return ids


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
            "conversation_id": request.conversation_id,
            "user_id": actor.id,
            "buyer_name": actor.user.full_name,
            "buyer_memory": _memory(actor.id),
        },
        "recursion_limit": _RECURSION_LIMIT,
        "run_name": llm_observability.AGENT_RUN_NAME,
    }


def _guest_config(request: ChatRequest) -> RunnableConfig:
    """No user_id, so tools only read public data (AC-03: no PII)."""
    return {
        # The client-generated id is random and only known to that browser tab
        "configurable": {
            "thread_id": _guest_thread(request.conversation_id),
            "conversation_id": request.conversation_id,
            "user_id": None,
            "buyer_name": "Quý khách",
        },
        "recursion_limit": _RECURSION_LIMIT,
        "run_name": llm_observability.AGENT_RUN_NAME,
    }


async def chat(actor: Actor, request: ChatRequest) -> ChatResponse:
    config = _buyer_config(actor, request)
    thread_id = config["configurable"]["thread_id"]
    tracer = TurnTracer()
    screened = await guardrails.review_input(request.message)
    if screened.blocked:
        new_messages = _blocked_turn(screened)
        _record(tracer, actor, request, thread_id, new_messages, streamed=False, screened=screened)
        return _response(request.conversation_id, new_messages, tracer.trace_id)
    try:
        new_messages, violations = await _run_turn(config, screened.text, tracer)
    except AgentUnavailableError as e:
        _record(tracer, actor, request, thread_id, [], streamed=False, error=e.__cause__ or e, screened=screened)
        raise
    _record(tracer, actor, request, thread_id, new_messages, streamed=False, screened=screened, violations=violations)
    return _response(request.conversation_id, new_messages, tracer.trace_id)


def _blocked_turn(screened: guardrails.InputVerdict) -> list[BaseMessage]:
    """The turn of a message the input guardrail stopped: a fixed reply, the model is not called. Not added to the
    agent's memory, so the attempt cannot steer later turns."""
    return [HumanMessage(screened.text), AIMessage(guardrails.INJECTION_REPLY)]


def _memory(user_id: int) -> str | None:
    # A memory read failure must not stop the conversation
    try:
        with get_sessionmaker()() as db:
            return buyer_memory.summary(db, user_id)
    except Exception:
        logger.exception("could not load buyer memory")
        return None


async def guest_chat(request: ChatRequest) -> ChatResponse:
    """A turn for a buyer without an account (stored and traced too; claimed when the guest signs up)."""
    thread_id = _guest_thread(request.conversation_id)
    tracer = TurnTracer()
    screened = await guardrails.review_input(request.message)
    if screened.blocked:
        new_messages = _blocked_turn(screened)
        _record(tracer, None, request, thread_id, new_messages, streamed=False, screened=screened)
        return _guest_response(request.conversation_id, new_messages, tracer.trace_id)
    try:
        new_messages, violations = await _run_turn(_guest_config(request), screened.text, tracer)
    except AgentUnavailableError as e:
        _record(tracer, None, request, thread_id, [], streamed=False, error=e.__cause__ or e, screened=screened)
        raise
    _record(tracer, None, request, thread_id, new_messages, streamed=False, screened=screened, violations=violations)
    return _guest_response(request.conversation_id, new_messages, tracer.trace_id)


def _guest_response(conversation_id: str, new_messages: list[BaseMessage], trace_id: str) -> ChatResponse:
    response = _response(conversation_id, new_messages, trace_id)
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
    tracer = TurnTracer()
    screened = await guardrails.review_input(request.message)
    async for name, data in _stream_turn(config, screened, tracer):
        if name == "_failed":
            _record(tracer, actor, request, thread_id, [], streamed=True, error=data["error"], screened=screened)
        elif name == "_final":
            _record(
                tracer,
                actor,
                request,
                thread_id,
                data["messages"],
                streamed=True,
                screened=screened,
                violations=data["violations"],
            )
            yield "done", _response(request.conversation_id, data["messages"], tracer.trace_id).model_dump(mode="json")
        else:
            yield name, data


async def guest_chat_stream(request: ChatRequest) -> AsyncIterator[ChatEvent]:
    thread_id = _guest_thread(request.conversation_id)
    tracer = TurnTracer()
    screened = await guardrails.review_input(request.message)
    async for name, data in _stream_turn(_guest_config(request), screened, tracer):
        if name == "_failed":
            _record(tracer, None, request, thread_id, [], streamed=True, error=data["error"], screened=screened)
        elif name == "_final":
            _record(
                tracer,
                None,
                request,
                thread_id,
                data["messages"],
                streamed=True,
                screened=screened,
                violations=data["violations"],
            )
            response = _guest_response(request.conversation_id, data["messages"], tracer.trace_id)
            yield "done", response.model_dump(mode="json")
        else:
            yield name, data


async def _stream_turn(
    config: RunnableConfig, screened: guardrails.InputVerdict, tracer: TurnTracer
) -> AsyncIterator[ChatEvent]:
    """Events of one turn: `token` (a piece of the reply being written), `tools` (the agent is calling tools;
    text streamed before it was only a preface), `error`; then an internal `_final` with the new messages and
    what the output guardrail found (or `_failed` with the error, before `error`). The `done` event carries the
    screened reply, which the client shows in place of the streamed text."""
    if screened.blocked:
        yield "token", {"text": guardrails.INJECTION_REPLY}
        yield "_final", {"messages": _blocked_turn(screened), "violations": []}
        return
    message = screened.text
    agent = agent_graph.get_agent()
    with llm_observability.chat_turn(tracer.trace_id, config, message, streamed=True) as observed:
        async for event in _stream_events(
            agent, {**config, "callbacks": [tracer, *observed.callbacks]}, message, tracer.trace_id
        ):
            name, data = event
            if name == "_final":
                observed.finish(_reply(data["messages"]))
            elif name == "_failed":
                observed.fail(data["error"])
            yield event


async def _stream_events(agent: Any, config: RunnableConfig, message: str, trace_id: str) -> AsyncIterator[ChatEvent]:
    # Reply text reaches the buyer only sentence by sentence, after the guardrail checked it
    gate = guardrails.StreamGate()
    try:
        # What the gate checks against: the conversation so far, plus this turn's tool results as they arrive
        seen: list[BaseMessage] = list((await agent.aget_state(config)).values.get("messages", []))
        before = len(seen)
        seen.append(HumanMessage(message))
        async for mode, payload in agent.astream(
            {"messages": [HumanMessage(message)]}, config, stream_mode=["messages", "updates"]
        ):
            if mode == "messages":
                chunk, meta = payload
                if isinstance(chunk, AIMessageChunk) and meta.get("langgraph_node") == "agent" and chunk.text:
                    if text := gate.feed(chunk.text, seen):
                        yield "token", {"text": text}
            elif mode == "updates":
                for node, update in payload.items():
                    if not update:
                        continue
                    seen.extend(update.get("messages", []))
                    if node != "agent":
                        continue
                    calls = [
                        c["name"] for m in update.get("messages", []) if isinstance(m, AIMessage) for c in m.tool_calls
                    ]
                    if calls:
                        gate.reset()
                        yield "tools", {"names": calls}
        history = (await agent.aget_state(config)).values["messages"]
        messages, violations = await _guard_output(agent, config, history, history[before:])
        if last := gate.finish(_reply(messages)):
            name, text = last
            yield name, {"text": text}
    except Exception as e:
        # The response has already started: report the failure as an event, the client shows it in the chat
        logger.exception("agent turn failed (stream, trace=%s)", trace_id)
        yield "_failed", {"error": e}
        yield (
            "error",
            {
                "code": "AGENT_UNAVAILABLE",
                "message": "AI assistant is temporarily unavailable, please try again",
                "trace_id": trace_id,
            },
        )
        return
    yield "_final", {"messages": messages, "violations": violations}


async def claim_guest(actor: Actor, conversation_id: str) -> bool:
    """After a guest signs up, move the guest conversation into the new account's thread so the agent keeps context
    (and the stored conversation, with its traces, becomes the new account's)."""
    agent = agent_graph.get_agent()
    guest_thread = _guest_thread(conversation_id)
    guest = (await agent.aget_state({"configurable": {"thread_id": guest_thread}})).values
    messages = guest.get("messages", [])
    thread_id = f"{actor.id}:{conversation_id}"
    target: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    if not messages or (await agent.aget_state(target)).values.get("messages"):
        return False
    await agent.aupdate_state(target, {"messages": messages}, as_node="agent")
    await agent.checkpointer.adelete_thread(guest_thread)
    try:
        with get_sessionmaker()() as db:
            conversation_service.claim_guest(db, actor, guest_thread, thread_id)
    except Exception:
        logger.exception("could not attach the guest conversation to user %s", actor.id)
    return True


async def _run_turn(config: RunnableConfig, message: str, tracer: TurnTracer) -> tuple[list[BaseMessage], list[str]]:
    """The turn's new messages (reply screened by the output guardrail) and what the guardrail found."""
    agent = agent_graph.get_agent()  # raises AgentUnavailableError when no API key is configured
    with llm_observability.chat_turn(tracer.trace_id, config, message, streamed=False) as observed:
        config = {**config, "callbacks": [tracer, *observed.callbacks]}
        try:
            before = len((await agent.aget_state(config)).values.get("messages", []))
            result = await agent.ainvoke({"messages": [HumanMessage(message)]}, config)
        except Exception as e:
            logger.exception("agent turn failed (trace=%s)", tracer.trace_id)
            observed.fail(e)
            raise AgentUnavailableError(
                "AI assistant is temporarily unavailable, please try again", details={"trace_id": tracer.trace_id}
            ) from e
        history = result["messages"]
        new_messages, violations = await _guard_output(agent, config, history, history[before:])
        observed.finish(_reply(new_messages))
    return new_messages, violations


async def _guard_output(
    agent: Any, config: RunnableConfig, history: list[BaseMessage], new_messages: list[BaseMessage]
) -> tuple[list[BaseMessage], list[str]]:
    """Screen the turn's final reply; a changed reply also replaces the original in the conversation state."""
    last = new_messages[-1] if new_messages else None
    if not isinstance(last, AIMessage) or last.tool_calls:
        return new_messages, []
    verdict = await guardrails.review_output(last.text, history)
    if not verdict.changed:
        return new_messages, verdict.notes
    logger.warning("output guardrail changed the reply: %s", verdict.violations)
    safe = guardrails.guarded_reply(last, verdict)
    try:
        await agent.aupdate_state({"configurable": config["configurable"]}, {"messages": [safe]}, as_node="agent")
    except Exception:
        logger.exception("could not store the guarded reply")
    return [*new_messages[:-1], safe], [*verdict.violations, *verdict.notes]


def _reply(new_messages: list[BaseMessage]) -> str:
    last = new_messages[-1] if new_messages else None
    return last.text if isinstance(last, AIMessage) else ""


def _response(conversation_id: str, new_messages: list[BaseMessage], trace_id: str | None = None) -> ChatResponse:
    reply = _reply(new_messages)
    recommendations, viewing_times, bookings = _extract(new_messages)
    return ChatResponse(
        reply=reply,
        conversation_id=conversation_id,
        recommendations=recommendations,
        viewing_times=viewing_times,
        bookings=bookings,
        trace_id=trace_id,
        property_ids=_detailed(new_messages),
    )


def _record(
    tracer: TurnTracer,
    actor: Actor | None,
    request: ChatRequest,
    thread_id: str,
    messages: list[BaseMessage],
    *,
    streamed: bool,
    error: BaseException | None = None,
    screened: guardrails.InputVerdict | None = None,
    violations: list[str] | None = None,
) -> None:
    """Store the turn: its trace (always, failed turns too), its messages (when it produced any) and what the
    guardrails changed. Tool actions are already committed by the services; a logging failure must not hide
    the reply."""
    try:
        with get_sessionmaker()() as db:
            conv = conversation_service.get_or_create(db, actor, request.conversation_id, thread_id)
            turn = ai_trace.save(
                db,
                tracer,
                # As the model received it: personal data the buyer typed is not kept in traces
                message=screened.text if screened is not None else request.message,
                buyer_id=actor.id if actor is not None else None,
                conversation=conv,
                streamed=streamed,
                error=error,
            )
            if messages:
                conversation_service.record_turn(
                    db,
                    actor,
                    client_id=request.conversation_id,
                    thread_id=thread_id,
                    messages=messages,
                    latency_ms=turn.latency_ms,
                    turn_id=turn.id,
                    conv=conv,
                )
            if guarded := [*(screened.flags if screened else []), *(violations or [])]:
                audit.record(
                    db,
                    actor,
                    "AI_GUARDRAIL",
                    "ai_conversation",
                    conv.id,
                    extra={
                        "flags": guarded,
                        "blocked": bool(screened and screened.blocked),
                        "trace_id": tracer.trace_id,
                    },
                )
            db.commit()
    except Exception:
        logger.exception("failed to record chat turn (trace=%s)", tracer.trace_id)
