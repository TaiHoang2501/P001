"""AI assistant chat: the buyer's only way to discover properties (spec §4.4)."""

from fastapi import APIRouter

from src.core.deps import CustomerActor, DbSession
from src.models.schemas import ChatMessageOut, ChatRequest, ChatResponse, ConversationOut
from src.services import chat_service, conversation_service

router = APIRouter(tags=["agent"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, actor: CustomerActor) -> ChatResponse:
    return await chat_service.chat(actor, request)


@router.get("/status")
async def agent_status() -> dict[str, str]:
    return {"status": "ready", "agent": "BookingBot LangGraph Agent v2"}


@router.get("/chat/conversations", response_model=list[ConversationOut])
def my_conversations(actor: CustomerActor, db: DbSession) -> list[ConversationOut]:
    return conversation_service.list_for(db, actor)


@router.get("/chat/conversations/{conversation_id}/messages", response_model=list[ChatMessageOut])
def conversation_messages(conversation_id: str, actor: CustomerActor, db: DbSession) -> list[ChatMessageOut]:
    return conversation_service.messages_for(db, actor, conversation_id)
