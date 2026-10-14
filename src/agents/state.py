from typing import NotRequired

from langgraph.graph import MessagesState


class AgentState(MessagesState):
    """Conversation state: the message list (human, AI, tool calls and tool results), and the system prompt
    built on the conversation's first turn. It is kept unchanged afterwards: Claude rejects its earlier thinking
    when the system prompt it was produced under has changed."""

    system_prompt: NotRequired[str]
