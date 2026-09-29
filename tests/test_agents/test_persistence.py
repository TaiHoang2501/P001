"""Chat turns are stored with tool calls/results; recommendations are linked to the deals they lead to."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from src.agents import graph as agent_graph
from src.db.models import (
    AiConversation,
    AiMessage,
    AvailabilitySlot,
    ConversationStatus,
    Deal,
    Escalation,
    MessageRole,
    Recommendation,
)
from tests.helpers import CUSTOMER_AN, CUSTOMER_BINH, auth

AN_ID = 1
VN = ZoneInfo("Asia/Ho_Chi_Minh")
SAT = datetime(2030, 1, 5, tzinfo=VN)
CRITERIA = {"project_codes": ["VHOP1"], "bedrooms_min": 1, "limit": 3}


class ScriptedModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self


def _call(name: str, args: dict, call_id: str = "call-1") -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


@pytest.fixture
def script(monkeypatch):
    model = ScriptedModel(messages=iter([]))
    agent = agent_graph.build_graph(model, InMemorySaver())
    monkeypatch.setattr(agent_graph, "get_agent", lambda: agent)

    def set_replies(*messages: AIMessage) -> None:
        model.messages = iter(messages)

    return set_replies


async def _chat(client, headers, message: str, conversation_id: str = "conv1"):
    r = await client.post(
        "/api/v1/chat", json={"message": message, "conversation_id": conversation_id}, headers=headers
    )
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_turn_is_stored_with_tool_call_and_result(client, script, db):
    an = await auth(client, CUSTOMER_AN)
    script(_call("search_properties", CRITERIA), AIMessage(content="Có 3 căn phù hợp."))
    await _chat(client, an, "Tìm căn ở Ocean Park")

    conv = db.query(AiConversation).filter_by(buyer_id=AN_ID, client_id="conv1").one()
    assert conv.thread_id == f"{AN_ID}:conv1"
    assert conv.extracted_criteria == CRITERIA

    rows = db.query(AiMessage).filter_by(conversation_id=conv.id).order_by(AiMessage.id).all()
    assert [r.role for r in rows] == [MessageRole.USER, MessageRole.ASSISTANT, MessageRole.TOOL, MessageRole.ASSISTANT]
    tool = rows[2]
    assert tool.tool_name == "search_properties"
    assert tool.tool_args == CRITERIA
    assert tool.tool_ok is True
    assert tool.tool_result["ok"] is True
    assert rows[1].tool_calls[0]["name"] == "search_properties"
    assert rows[3].content == "Có 3 căn phù hợp."
    assert rows[3].latency_ms is not None


@pytest.mark.asyncio
async def test_search_results_become_ranked_recommendations(client, script, db):
    an = await auth(client, CUSTOMER_AN)
    script(_call("search_properties", CRITERIA), AIMessage(content="Đây là các căn."))
    body = await _chat(client, an, "Tìm căn")

    recs = db.query(Recommendation).filter_by(buyer_id=AN_ID).order_by(Recommendation.rank).all()
    assert [r.property_id for r in recs] == [r["property"]["id"] for r in body["recommendations"]]
    assert [r.rank for r in recs] == list(range(1, len(recs) + 1))
    assert recs[0].criteria_snapshot == CRITERIA
    assert "matched" in recs[0].score_breakdown


@pytest.mark.asyncio
async def test_failed_tool_is_stored_as_not_ok_and_makes_no_recommendation(client, script, db):
    an = await auth(client, CUSTOMER_AN)
    script(_call("search_properties", {"budget_min": 5, "budget_max": 1}), AIMessage(content="Ngân sách chưa hợp lệ."))
    await _chat(client, an, "Tìm căn")

    tool = db.query(AiMessage).filter_by(role=MessageRole.TOOL).one()
    assert tool.tool_ok is False
    assert tool.tool_result["error"]["code"] == "TOOL_ERROR"
    assert "budget_min" in tool.tool_result["error"]["message"]
    assert db.query(Recommendation).count() == 0


@pytest.mark.asyncio
async def test_deal_is_attributed_to_the_recommendation_that_led_to_it(client, script, db):
    an = await auth(client, CUSTOMER_AN)
    script(_call("search_properties", CRITERIA), AIMessage(content="Đây là các căn."))
    body = await _chat(client, an, "Tìm căn")
    property_id = body["recommendations"][0]["property"]["id"]
    db.add(
        AvailabilitySlot(property_id=property_id, start_at=SAT + timedelta(hours=14), end_at=SAT + timedelta(hours=16))
    )
    db.commit()

    start = (SAT + timedelta(hours=15)).isoformat()
    script(
        _call("create_viewing_request", {"property_id": property_id, "start_at": start}),
        AIMessage(content="Đã gửi yêu cầu xem."),
    )
    body = await _chat(client, an, "Xem căn đầu tiên lúc 15h")
    [booking] = body["bookings"]

    db.expire_all()
    deal = db.get(Deal, booking["deal_id"])
    rec = db.get(Recommendation, deal.source_recommendation_id)
    assert rec.property_id == property_id
    assert rec.rank == 1


@pytest.mark.asyncio
async def test_history_endpoints_show_only_own_text_messages(client, script):
    an = await auth(client, CUSTOMER_AN)
    script(_call("search_properties", CRITERIA), AIMessage(content="Có 3 căn phù hợp."))
    await _chat(client, an, "Tìm căn ở Ocean Park")

    convs = (await client.get("/api/v1/chat/conversations", headers=an)).json()
    assert [c["conversation_id"] for c in convs] == ["conv1"]
    msgs = (await client.get("/api/v1/chat/conversations/conv1/messages", headers=an)).json()
    assert [(m["role"], m["content"]) for m in msgs] == [
        ("USER", "Tìm căn ở Ocean Park"),
        ("ASSISTANT", "Có 3 căn phù hợp."),
    ]

    binh = await auth(client, CUSTOMER_BINH)
    assert (await client.get("/api/v1/chat/conversations", headers=binh)).json() == []
    assert (await client.get("/api/v1/chat/conversations/conv1/messages", headers=binh)).status_code == 404


@pytest.mark.asyncio
async def test_escalation_from_chat_marks_conversation_and_links_it(client, script, db):
    an = await auth(client, CUSTOMER_AN)
    script(
        _call("create_human_escalation", {"type": "OTHER", "summary": "Khách muốn nói chuyện với nhân viên"}),
        AIMessage(content="Nhân viên hỗ trợ sẽ liên hệ anh sớm."),
    )
    await _chat(client, an, "Cho tôi gặp nhân viên")

    conv = db.query(AiConversation).filter_by(buyer_id=AN_ID).one()
    assert conv.status == ConversationStatus.ESCALATED
    esc = db.query(Escalation).one()
    assert esc.conversation_id == conv.id
    assert esc.context == {"thread_id": f"{AN_ID}:conv1"}
