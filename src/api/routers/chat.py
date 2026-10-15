"""AI assistant chat: the buyer's only way to discover properties (spec §4.4)."""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.core.deps import CustomerActor, DbSession
from src.models.schemas import (
    AssistantStatusOut,
    ChatMessageOut,
    ChatRequest,
    ChatResponse,
    ConversationOut,
    GuestClaimResponse,
)
from src.services import assistant_control, chat_service, conversation_service, rate_limit

router = APIRouter(tags=["agent"])


def _admit(db: Session, key: str, guest: bool) -> None:
    # Kill switch first: while an operator has the assistant off, nothing reaches the model (and nothing is counted)
    assistant_control.ensure_enabled()
    rate_limit.check_chat(db, key, guest=guest)


async def _limit_buyer(db: Session, user_id: int) -> None:
    await run_in_threadpool(_admit, db, f"user:{user_id}", False)


async def _limit_guest(db: Session, request: Request) -> None:
    await run_in_threadpool(_admit, db, f"ip:{rate_limit.client_ip(request)}", True)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, actor: CustomerActor, db: DbSession) -> ChatResponse:
    await _limit_buyer(db, actor.id)
    return await chat_service.chat(actor, request)


@router.post("/chat/guest", response_model=ChatResponse)
async def guest_chat(request: ChatRequest, http: Request, db: DbSession) -> ChatResponse:
    """New buyers chat before having an account; booking asks them to sign up (see `needs_account`)."""
    await _limit_guest(db, http)
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
    "Server-Sent Events: `token` {text} while the reply is written (sentence by sentence, each checked by the "
    "guardrails first), `tools` {names} when the agent calls tools, `replace` {text} when the guardrails changed the "
    "reply (show it instead of the streamed text), `error` {code, message}, and finally `done` with the same body as "
    "the non-streaming endpoint."
)


@router.post("/chat/stream", response_class=StreamingResponse, description=_STREAM_DOC)
async def chat_stream(request: ChatRequest, actor: CustomerActor, db: DbSession) -> StreamingResponse:
    await _limit_buyer(db, actor.id)
    chat_service.ensure_agent()
    return _sse(chat_service.chat_stream(actor, request))


@router.post("/chat/guest/stream", response_class=StreamingResponse, description=_STREAM_DOC)
async def guest_chat_stream(request: ChatRequest, http: Request, db: DbSession) -> StreamingResponse:
    await _limit_guest(db, http)
    chat_service.ensure_agent()
    return _sse(chat_service.guest_chat_stream(request))


@router.post("/chat/guest/{conversation_id}/claim", response_model=GuestClaimResponse)
async def claim_guest_chat(conversation_id: str, actor: CustomerActor) -> GuestClaimResponse:
    """Right after a guest signs up: continue the same conversation under the new account."""
    return GuestClaimResponse(claimed=await chat_service.claim_guest(actor, conversation_id))


@router.get("/chat/assistant-status", response_model=AssistantStatusOut)
def assistant_status(db: DbSession) -> AssistantStatusOut:
    """Public: the chat shows a maintenance notice (with the support hotline) while an operator has the AI off."""
    return AssistantStatusOut.model_validate(assistant_control.status(db))


@router.get("/status")
async def agent_status() -> dict[str, str]:
    return {"status": "ready", "agent": "BookingBot LangGraph Agent v2"}


@router.get("/chat/conversations", response_model=list[ConversationOut])
def my_conversations(actor: CustomerActor, db: DbSession) -> list[ConversationOut]:
    return conversation_service.list_for(db, actor)


@router.get("/chat/conversations/{conversation_id}/messages", response_model=list[ChatMessageOut])
def conversation_messages(conversation_id: str, actor: CustomerActor, db: DbSession) -> list[ChatMessageOut]:
    return conversation_service.messages_for(db, actor, conversation_id)
