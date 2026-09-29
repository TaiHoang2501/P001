"""Persists AI chat turns: conversations, messages (incl. tool calls/results) and recommendations.

What is stored is what the tools actually returned, so audits of AC-01 (no invented property)
and analytics like Precision@5 (spec §2.2) work from facts, not from the model's wording.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.actor import Actor
from src.core.errors import NotFoundError
from src.db.models import AiConversation, AiMessage, Deal, MessageRole, Recommendation
from src.models.schemas import ChatMessageOut, ConversationOut


def get_or_create(db: Session, actor: Actor, client_id: str, thread_id: str) -> AiConversation:
    conv = db.scalar(
        select(AiConversation).where(AiConversation.buyer_id == actor.id, AiConversation.client_id == client_id)
    )
    if conv is None:
        conv = AiConversation(buyer_id=actor.id, client_id=client_id, thread_id=thread_id)
        db.add(conv)
        db.flush()
    return conv


def record_turn(
    db: Session,
    actor: Actor,
    *,
    client_id: str,
    thread_id: str,
    messages: list[BaseMessage],
    latency_ms: int,
) -> AiConversation:
    """Store one turn (the new messages) and derive recommendations / deal attribution from tool results."""
    conv = get_or_create(db, actor, client_id, thread_id)
    tool_args: dict[str, dict[str, Any]] = {}
    last_assistant: AiMessage | None = None

    for m in messages:
        if isinstance(m, HumanMessage):
            db.add(AiMessage(conversation_id=conv.id, role=MessageRole.USER, content=m.text))
        elif isinstance(m, AIMessage):
            calls = [{"id": c["id"], "name": c["name"], "args": c["args"]} for c in m.tool_calls]
            tool_args.update({c["id"]: c["args"] for c in calls})
            usage = m.usage_metadata or {}
            last_assistant = AiMessage(
                conversation_id=conv.id,
                role=MessageRole.ASSISTANT,
                content=m.text,
                tool_calls=calls or None,
                model=(m.response_metadata or {}).get("model_name"),
                prompt_tokens=usage.get("input_tokens"),
                completion_tokens=usage.get("output_tokens"),
            )
            db.add(last_assistant)
        elif isinstance(m, ToolMessage):
            envelope = m.artifact if isinstance(m.artifact, dict) else None
            if envelope is None:
                # Rejected before our tool ran (e.g. arguments failed the schema): keep the error text
                envelope = {"ok": False, "error": {"code": "TOOL_ERROR", "message": m.text, "details": {}}}
            args = tool_args.get(m.tool_call_id, {})
            row = AiMessage(
                conversation_id=conv.id,
                role=MessageRole.TOOL,
                content="",
                tool_name=m.name,
                tool_args=args,
                tool_result=envelope,
                tool_ok=bool(envelope and envelope.get("ok")),
            )
            db.add(row)
            db.flush()
            if row.tool_ok:
                _on_tool_success(db, actor, conv, row, envelope["data"])

    if last_assistant is not None:
        last_assistant.latency_ms = latency_ms
    conv.last_message_at = datetime.now(UTC)
    db.commit()
    return conv


def _on_tool_success(db: Session, actor: Actor, conv: AiConversation, row: AiMessage, data: Any) -> None:
    if row.tool_name == "search_properties":
        conv.extracted_criteria = row.tool_args or {}
        for rank, rec in enumerate(data.get("results", []), start=1):
            db.add(
                Recommendation(
                    conversation_id=conv.id,
                    ai_message_id=row.id,
                    buyer_id=actor.id,
                    property_id=rec["property"]["id"],
                    rank=rank,
                    match_score=Decimal(str(rec["match_score"])).quantize(Decimal("0.0001")),
                    score_breakdown={"matched": rec["matched"], "unmatched": rec["unmatched"]},
                    criteria_snapshot=row.tool_args or {},
                )
            )
        db.flush()
    elif row.tool_name == "create_viewing_request":
        _attribute_deal(db, conv, deal_id=data["deal_id"], property_id=data["property_id"])


def _attribute_deal(db: Session, conv: AiConversation, *, deal_id: int, property_id: int) -> None:
    """Remember which recommendation led to the deal (first one wins)."""
    deal = db.get(Deal, deal_id)
    if deal is None or deal.source_recommendation_id is not None:
        return
    deal.source_recommendation_id = db.scalar(
        select(Recommendation.id)
        .where(Recommendation.conversation_id == conv.id, Recommendation.property_id == property_id)
        .order_by(Recommendation.id.desc())
        .limit(1)
    )


# ---------- Reads (chat history for the web UI) ----------


def list_for(db: Session, actor: Actor) -> list[ConversationOut]:
    rows = db.scalars(
        select(AiConversation)
        .where(AiConversation.buyer_id == actor.id)
        .order_by(AiConversation.last_message_at.desc())
    )
    return [
        ConversationOut(
            conversation_id=c.client_id,
            status=c.status,
            extracted_criteria=c.extracted_criteria,
            created_at=c.created_at,
            last_message_at=c.last_message_at,
        )
        for c in rows
    ]


def messages_for(db: Session, actor: Actor, client_id: str) -> list[ChatMessageOut]:
    """Buyer-visible history: their messages and the assistant's text replies (no tool internals)."""
    conv = db.scalar(
        select(AiConversation).where(AiConversation.buyer_id == actor.id, AiConversation.client_id == client_id)
    )
    if conv is None:
        raise NotFoundError(f"Conversation {client_id} not found")
    rows = db.scalars(
        select(AiMessage)
        .where(
            AiMessage.conversation_id == conv.id,
            AiMessage.role.in_([MessageRole.USER, MessageRole.ASSISTANT]),
            AiMessage.content != "",
        )
        .order_by(AiMessage.id)
    )
    return [ChatMessageOut(role=m.role, content=m.content, created_at=m.created_at) for m in rows]
