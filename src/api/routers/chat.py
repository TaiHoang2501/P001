"""AI assistant chat: the buyer's only way to discover properties (spec §4.4)."""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from src.core.deps import CustomerActor, DbSession
from src.models.schemas import ChatMessageOut, ChatRequest, ChatResponse, ConversationOut, GuestClaimResponse
from src.services import chat_service, conversation_service

router = APIRouter(tags=["agent"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, actor: CustomerActor) -> ChatResponse:
    return await chat_service.chat(actor, request)


@router.post("/chat/guest", response_model=ChatResponse)
async def guest_chat(request: ChatRequest) -> ChatResponse:
    """New buyers chat before having an account; booking asks them to sign up (see `needs_account`)."""
    return await chat_service.guest_chat(request)


def _sse(events: AsyncIterator[chat_service.ChatEvent]) -> StreamingResponse:
    async def body() -> AsyncIterator[str]:
        async for name, data in events:
            yield f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    # No proxy buffering (Render/nginx), so each piece reaches the browser as soon as it is written
    return StreamingResponse(
        body(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


_STREAM_DOC = (
    "Server-Sent Events: `token` {text} while the reply is written, `tools` {names} when the agent calls tools, "
    "`error` {code, message}, and finally `done` with the same body as the non-streaming endpoint."
)


@router.post("/chat/stream", response_class=StreamingResponse, description=_STREAM_DOC)
async def chat_stream(request: ChatRequest, actor: CustomerActor) -> StreamingResponse:
    chat_service.ensure_agent()
    return _sse(chat_service.chat_stream(actor, request))


@router.post("/chat/guest/stream", response_class=StreamingResponse, description=_STREAM_DOC)
async def guest_chat_stream(request: ChatRequest) -> StreamingResponse:
    chat_service.ensure_agent()
    return _sse(chat_service.guest_chat_stream(request))


@router.post("/chat/guest/{conversation_id}/claim", response_model=GuestClaimResponse)
async def claim_guest_chat(conversation_id: str, actor: CustomerActor) -> GuestClaimResponse:
    """Right after a guest signs up: continue the same conversation under the new account."""
    return GuestClaimResponse(claimed=await chat_service.claim_guest(actor, conversation_id))


@router.get("/status")
async def agent_status() -> dict[str, str]:
    return {"status": "ready", "agent": "BookingBot LangGraph Agent v2"}


@router.get("/chat/conversations", response_model=list[ConversationOut])
def my_conversations(actor: CustomerActor, db: DbSession) -> list[ConversationOut]:
    return conversation_service.list_for(db, actor)


@router.get("/chat/conversations/{conversation_id}/messages", response_model=list[ChatMessageOut])
def conversation_messages(conversation_id: str, actor: CustomerActor, db: DbSession) -> list[ChatMessageOut]:
    return conversation_service.messages_for(db, actor, conversation_id)
