"""AI assistant chat: the buyer's only way to discover properties (spec §4.4)."""

from fastapi import APIRouter

from src.core.deps import CustomerActor
from src.models.schemas import ChatRequest, ChatResponse
from src.services import chat_service

router = APIRouter(tags=["agent"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, actor: CustomerActor) -> ChatResponse:
    return await chat_service.chat(actor, request)


@router.get("/status")
async def agent_status() -> dict[str, str]:
    return {"status": "ready", "agent": "BookingBot LangGraph Agent v2"}
