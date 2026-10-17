"""Buyer-facing agent: a tool-calling loop (agent <-> tools) with per-conversation memory.

The graph is built from any chat model that supports tool binding, so tests can plug in a
scripted fake model. Conversation memory is keyed by thread_id (set by the chat service).
"""

import time
from collections.abc import Sequence
from datetime import UTC, date, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, trim_messages
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from src.agents.prompts import system_prompt, turn_context
from src.agents.state import AgentState
from src.agents.tools import TOOLS
from src.config import get_settings
from src.core.errors import AgentUnavailableError
from src.services import agent_api
from src.services.llm import get_fallback_llm, get_llm

# Messages of history sent to the model each turn (full history stays in the checkpoint). Not used for Claude:
# dropping old turns changes what its earlier thinking was produced under, and the API then rejects that thinking
_HISTORY_WINDOW = 40

# When a buyer message was sent, stored on the message itself so the model sees the same text on every request
_SENT_AT = "sent_at"

# Project codes go in the prompt, so searching needs no list_projects round (one LLM call less)
_PROJECTS_TTL_SECONDS = 300
_projects_cache: tuple[float, str | None] = (0.0, None)


def _project_catalog() -> str | None:
    global _projects_cache
    fetched_at, catalog = _projects_cache
    if time.monotonic() - fetched_at < _PROJECTS_TTL_SECONDS:
        return catalog
    envelope = agent_api.list_projects()
    if not envelope.get("ok"):
        # Do not cache a failure; the prompt then tells the model to call list_projects
        return catalog
    catalog = "\n".join(f"- {p['code']}: {p['name']} ({p['city']})" for p in envelope["data"]) or None
    _projects_cache = (time.monotonic(), catalog)
    return catalog


def _stamp_new_message(messages: Sequence[BaseMessage]) -> HumanMessage | None:
    """The newest buyer message with the time it was sent; None when it already has one. Older messages stay
    as they are: changing them would change the conversation the model's earlier thinking was produced in."""
    last = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
    if last is None or _SENT_AT in last.additional_kwargs:
        return None
    sent_at = datetime.now(UTC).isoformat()
    return last.model_copy(update={"additional_kwargs": {**last.additional_kwargs, _SENT_AT: sent_at}})


def _with_turn_context(messages: Sequence[BaseMessage]) -> list[BaseMessage]:
    """Buyer messages as the model sees them: the time each was sent, plus the calendar on the first one of a day.
    Worked out only from what is stored, so earlier messages read the same on every request."""
    tz = ZoneInfo(get_settings().timezone)
    shown: list[BaseMessage] = []
    last_day: date | None = None
    for m in messages:
        sent_at = m.additional_kwargs.get(_SENT_AT) if isinstance(m, HumanMessage) else None
        if not sent_at:
            shown.append(m)
            continue
        at = datetime.fromisoformat(sent_at)
        day = at.astimezone(tz).date()
        context = turn_context(at, with_calendar=day != last_day)
        last_day = day
        if isinstance(m.content, str):
            content: str | list = f"{context}\n\n{m.content}"
        else:
            content = [{"type": "text", "text": context}, *m.content]
        shown.append(m.model_copy(update={"content": content}))
    return shown


def _plain_system(messages: list[BaseMessage]) -> list[BaseMessage]:
    """The system prompt as plain text, without Claude's cache marker, for a fallback model on another provider."""
    return [SystemMessage(m.text) if isinstance(m, SystemMessage) else m for m in messages]


def build_graph(
    llm: BaseChatModel,
    checkpointer: BaseCheckpointSaver | None = None,
    fallback_llm: BaseChatModel | None = None,
    history_window: int | None = _HISTORY_WINDOW,
    cache_system_prompt: bool = False,
) -> CompiledStateGraph:
    model = llm.bind_tools(TOOLS)
    if fallback_llm is not None:
        # The main model overloaded or failing (e.g. Gemini 503) -> the lighter model answers this step
        model = model.with_fallbacks([RunnableLambda(_plain_system) | fallback_llm.bind_tools(TOOLS)])

    async def call_model(state: AgentState, config: RunnableConfig) -> dict:
        messages = state["messages"]
        update: dict = {"messages": []}
        if (stamped := _stamp_new_message(messages)) is not None:
            # Same id: replaces the message in the checkpoint
            messages = [stamped if m.id == stamped.id else m for m in messages]
            update["messages"].append(stamped)
        # Built on the conversation's first turn, then kept: the time and calendar go with each buyer message
        prompt = state.get("system_prompt")
        if prompt is None:
            configurable = config.get("configurable", {})
            buyer_name = configurable.get("buyer_name", "Quý khách")
            # What the signed-in buyer told us in earlier conversations (buyer_memory)
            memory = configurable.get("buyer_memory")
            prompt = system_prompt(buyer_name, memory, _project_catalog())
            update["system_prompt"] = prompt
        history = _with_turn_context(messages)
        if history_window is not None:
            # start_on="human" keeps tool calls and their results together when older turns are dropped
            history = trim_messages(
                history, strategy="last", token_counter=len, max_tokens=history_window, start_on="human"
            )
        system = SystemMessage(prompt)
        if cache_system_prompt:
            # A cache breakpoint after the tools and system prompt, besides the automatic one at the end of the
            # conversation: a new conversation with the same prompt (every guest's is the same) reads them from
            # cache instead of writing ~11k tokens again (~0.5 s off its first reply)
            system = SystemMessage([{"type": "text", "text": prompt, "cache_control": {"type": "ephemeral"}}])
        response = await model.ainvoke([system, *history], config)
        update["messages"].append(response)
        return update

    graph = StateGraph(AgentState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=checkpointer)


# Conversation memory: set to a Postgres saver at start-up (src/services/agent_memory.py); in-process otherwise
_checkpointer: BaseCheckpointSaver | None = None


def use_checkpointer(checkpointer: BaseCheckpointSaver | None) -> None:
    """Swap where conversations are kept; the agent is rebuilt on its next use."""
    global _checkpointer
    _checkpointer = checkpointer
    get_agent.cache_clear()


@lru_cache
def get_agent() -> CompiledStateGraph:
    settings = get_settings()
    if not settings.llm_api_key:
        key = f"{settings.llm_provider.upper()}_API_KEY"
        raise AgentUnavailableError(f"AI assistant is not configured ({key} missing)")
    # Without Postgres the memory is in-process: lost on restart and not shared between workers
    # The main model keeps its retries: a short rate-limit blip is better retried than handed to the
    # fallback, whose free quota (Flash: 20 requests/day) is easily used up
    # Claude gets the whole history (see _HISTORY_WINDOW); its context window holds far more than a chat
    claude = settings.llm_provider == "anthropic"
    window = None if claude else _HISTORY_WINDOW
    # Only the agent caches its prompt (src/services/llm.py)
    llm, fallback = get_llm(prompt_cache=True), get_fallback_llm(prompt_cache=True)
    return build_graph(llm, _checkpointer or InMemorySaver(), fallback, window, cache_system_prompt=claude)
