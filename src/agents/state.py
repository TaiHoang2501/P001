from langgraph.graph import MessagesState


class AgentState(MessagesState):
    """Conversation state: the message list (human, AI, tool calls and tool results)."""
