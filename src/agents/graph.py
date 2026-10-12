"""Buyer-facing agent: a tool-calling loop (agent <-> tools) with per-conversation memory.

The graph is built from any chat model that supports tool binding, so tests can plug in a
scripted fake model. Conversation memory is keyed by thread_id (set by the chat service).
"""

import time
from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, trim_messages
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from src.agents.prompts import system_prompt
from src.agents.state import AgentState
from src.agents.tools import TOOLS
from src.config import get_settings
from src.core.errors import AgentUnavailableError
from src.services import agent_api
from src.services.llm import get_fallback_llm, get_llm

# Messages of history sent to the model each turn (full history stays in the checkpoint)
_HISTORY_WINDOW = 40

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


def build_graph(
    llm: BaseChatModel,
    checkpointer: BaseCheckpointSaver | None = None,
    fallback_llm: BaseChatModel | None = None,
) -> CompiledStateGraph:
    model = llm.bind_tools(TOOLS)
    if fallback_llm is not None:
        # The main model overloaded or failing (e.g. Gemini 503) -> the lighter model answers this step
        model = model.with_fallbacks([fallback_llm.bind_tools(TOOLS)])

    async def call_model(state: AgentState, config: RunnableConfig) -> dict:
        configurable = config.get("configurable", {})
        buyer_name = configurable.get("buyer_name", "Quý khách")
        # What the signed-in buyer told us in earlier conversations (buyer_memory)
        memory = configurable.get("buyer_memory")
        # start_on="human" keeps tool calls and their results together when older turns are dropped
        history = trim_messages(
            state["messages"], strategy="last", token_counter=len, max_tokens=_HISTORY_WINDOW, start_on="human"
        )
        prompt = system_prompt(buyer_name, memory, _project_catalog())
        response = await model.ainvoke([SystemMessage(prompt), *history], config)
        return {"messages": [response]}

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
    return build_graph(get_llm(), _checkpointer or InMemorySaver(), get_fallback_llm())
