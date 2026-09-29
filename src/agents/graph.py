"""Buyer-facing agent: a tool-calling loop (agent <-> tools) with per-conversation memory.

The graph is built from any chat model that supports tool binding, so tests can plug in a
scripted fake model. Conversation memory is keyed by thread_id (set by the chat service).
"""

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
from src.services.llm import get_llm

# Messages of history sent to the model each turn (full history stays in the checkpoint)
_HISTORY_WINDOW = 40


def build_graph(llm: BaseChatModel, checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    model = llm.bind_tools(TOOLS)

    async def call_model(state: AgentState, config: RunnableConfig) -> dict:
        buyer_name = config.get("configurable", {}).get("buyer_name", "Quý khách")
        # start_on="human" keeps tool calls and their results together when older turns are dropped
        history = trim_messages(
            state["messages"], strategy="last", token_counter=len, max_tokens=_HISTORY_WINDOW, start_on="human"
        )
        response = await model.ainvoke([SystemMessage(system_prompt(buyer_name)), *history], config)
        return {"messages": [response]}

    graph = StateGraph(AgentState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=checkpointer)


@lru_cache
def get_agent() -> CompiledStateGraph:
    if not get_settings().openai_api_key:
        raise AgentUnavailableError("AI assistant is not configured (OPENAI_API_KEY missing)")
    # In-process memory: conversations are lost on restart and not shared between workers
    return build_graph(get_llm(), InMemorySaver())
