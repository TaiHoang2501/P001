"""Developer traces of chat turns (ai_turns): signed-in buyers, guests and failed turns, with their steps."""

from datetime import UTC, datetime, timedelta

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from src.agents import graph as agent_graph
from src.db.models import AiConversation, AiMessage, AiTurn
from src.services import ai_trace
from tests.helpers import CUSTOMER_AN, auth
from tests.test_agents.test_persistence import CRITERIA, ScriptedModel, _call

AN_ID = 1


@pytest.fixture
def script(monkeypatch):
    model = ScriptedModel(messages=iter([]))
    agent = agent_graph.build_graph(model, InMemorySaver())
    monkeypatch.setattr(agent_graph, "get_agent", lambda: agent)

    def set_replies(*messages: AIMessage) -> None:
        model.messages = iter(messages)

    return set_replies


@pytest.mark.asyncio
async def test_buyer_turn_is_traced_step_by_step(client, script, db):
    an = await auth(client, CUSTOMER_AN)
    script(_call("search_properties", CRITERIA), AIMessage(content="Có 3 căn phù hợp."))
    r = await client.post("/api/v1/chat", json={"message": "Tìm căn Ocean Park", "conversation_id": "c1"}, headers=an)
    assert r.status_code == 200, r.text
    trace_id = r.json()["trace_id"]

    turn = db.query(AiTurn).filter_by(trace_id=trace_id).one()
    assert (turn.status, turn.guest, turn.buyer_id, turn.message) == ("OK", False, AN_ID, "Tìm căn Ocean Park")
    assert (turn.llm_calls, turn.tool_calls) == (2, 1)
    assert [(s["kind"], s["name"]) for s in turn.steps][1] == ("tool", "search_properties")
    assert all(s["ms"] is not None and s["ok"] for s in turn.steps)
    assert turn.latency_ms >= 0
    # The stored messages point at their turn
    assert db.query(AiMessage).filter_by(turn_id=turn.id).count() == 4


@pytest.mark.asyncio
async def test_guest_turn_is_stored_and_attached_at_sign_up(client, script, db):
    script(AIMessage(content="Chào anh/chị, em có thể giúp gì?"))
    r = await client.post("/api/v1/chat/guest", json={"message": "Xin chào", "conversation_id": "g1"})
    assert r.status_code == 200, r.text

    turn = db.query(AiTurn).filter_by(trace_id=r.json()["trace_id"]).one()
    assert (turn.guest, turn.buyer_id) == (True, None)
    conv = db.get(AiConversation, turn.conversation_id)
    assert (conv.buyer_id, conv.thread_id) == (None, "guest:g1")
    assert db.query(AiMessage).filter_by(conversation_id=conv.id).count() == 2

    # The guest signs up: the conversation and its traces become the new account's
    an = await auth(client, CUSTOMER_AN)
    r = await client.post("/api/v1/chat/guest/g1/claim", headers=an)
    assert r.status_code == 200, r.text
    db.expire_all()
    assert (db.get(AiConversation, conv.id).buyer_id, db.get(AiTurn, turn.id).buyer_id) == (AN_ID, AN_ID)


@pytest.mark.asyncio
async def test_failed_turn_is_traced_with_its_error(client, script, db):
    an = await auth(client, CUSTOMER_AN)
    script()  # the model has nothing to say: the turn fails
    r = await client.post("/api/v1/chat", json={"message": "Tìm căn", "conversation_id": "c2"}, headers=an)
    assert r.status_code == 503
    trace_id = r.json()["error"]["details"]["trace_id"]

    turn = db.query(AiTurn).filter_by(trace_id=trace_id).one()
    assert turn.status == "ERROR" and turn.error_type
    assert turn.steps and turn.steps[0]["kind"] == "llm" and turn.steps[0]["ok"] is False


def test_old_traces_are_dropped(db):
    old = AiTurn(trace_id="old0", message="x", created_at=datetime.now(UTC) - timedelta(days=400))
    new = AiTurn(trace_id="new0", message="y")
    db.add_all([old, new])
    db.commit()
    assert ai_trace.purge_old(db) == 1
    assert [t.trace_id for t in db.query(AiTurn)] == ["new0"]


@pytest.mark.asyncio
async def test_operator_sees_the_chat_behind_a_case_the_assistant_raised(client, script, db):
    """In plain words: the buyer's name and phone, and the end of their chat with the assistant."""
    from src.db.models import Escalation
    from tests.helpers import OPERATOR

    an = await auth(client, CUSTOMER_AN)
    script(
        _call("create_human_escalation", {"type": "OTHER", "summary": "Khách muốn gặp nhân viên"}),
        AIMessage(content="Em đã chuyển cho bộ phận hỗ trợ, nhân viên sẽ liên hệ anh/chị."),
    )
    r = await client.post(
        "/api/v1/chat", json={"message": "Cho tôi gặp nhân viên", "conversation_id": "c9"}, headers=an
    )
    assert r.status_code == 200, r.text
    esc = db.query(Escalation).one()

    op = await auth(client, OPERATOR)
    ctx = (await client.get(f"/api/v1/operator/escalations/{esc.id}/context", headers=op)).json()
    assert (ctx["buyer_name"], ctx["buyer_phone"]) == ("Nguyễn Văn An", "0901111222")
    assert [(m["role"], m["content"]) for m in ctx["messages"]] == [
        ("USER", "Cho tôi gặp nhân viên"),
        ("ASSISTANT", "Em đã chuyển cho bộ phận hỗ trợ, nhân viên sẽ liên hệ anh/chị."),
    ]
    # Only for operators
    assert (await client.get(f"/api/v1/operator/escalations/{esc.id}/context", headers=an)).status_code == 403
