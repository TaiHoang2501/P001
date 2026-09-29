"""Runs one chat turn for an authenticated buyer and extracts what the UI should render.

The reply text comes from the model, but recommendations, viewing times and booking updates come
only from successful tool results (ok: true), never from what the model says it did (AC-01).
"""

import logging
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from src.agents import graph as agent_graph
from src.core.actor import Actor
from src.core.errors import AgentUnavailableError
from src.models.booking import BookingOut, ViewingTimesOut
from src.models.property import Recommendation
from src.models.schemas import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

# Upper bound on agent <-> tool round trips in one turn
_RECURSION_LIMIT = 16
_BOOKING_TOOLS = {"create_viewing_request", "cancel_viewing", "reschedule_viewing"}


def _ok_data(message: ToolMessage) -> Any:
    envelope = message.artifact
    if isinstance(envelope, dict) and envelope.get("ok"):
        return envelope["data"]
    return None


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
    agent = agent_graph.get_agent()  # raises AgentUnavailableError when no API key is configured
    config: RunnableConfig = {
        # Thread is scoped to the authenticated user, so one buyer can never load another's conversation
        "configurable": {
            "thread_id": f"{actor.id}:{request.conversation_id}",
            "user_id": actor.id,
            "buyer_name": actor.user.full_name,
        },
        "recursion_limit": _RECURSION_LIMIT,
    }
    try:
        before = len((await agent.aget_state(config)).values.get("messages", []))
        result = await agent.ainvoke({"messages": [HumanMessage(request.message)]}, config)
    except Exception as e:
        logger.exception("agent turn failed")
        raise AgentUnavailableError("AI assistant is temporarily unavailable, please try again") from e

    new_messages = result["messages"][before:]
    last = new_messages[-1]
    reply = last.text if isinstance(last, AIMessage) else ""
    recommendations, viewing_times, bookings = _extract(new_messages)
    return ChatResponse(
        reply=reply,
        conversation_id=request.conversation_id,
        recommendations=recommendations,
        viewing_times=viewing_times,
        bookings=bookings,
    )
