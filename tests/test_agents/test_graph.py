"""Agent graph + chat endpoint, driven by a scripted fake model (no OpenAI calls)."""

import json
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk
from langgraph.checkpoint.memory import InMemorySaver

from src.agents import graph as agent_graph
from src.agents.tools import TOOLS
from src.config import get_settings
from src.core.errors import AgentUnavailableError
from src.db.models import AvailabilitySlot
from tests.helpers import CUSTOMER_AN, CUSTOMER_BINH, OPERATOR, OWNER_TUAN, auth

AN_ID = 1
VN = ZoneInfo("Asia/Ho_Chi_Minh")
SAT = datetime(2030, 1, 5, tzinfo=VN)


def at(hour: float) -> str:
    return (SAT + timedelta(hours=hour)).isoformat()


class ScriptedModel(GenericFakeChatModel):
    """Replies with the given messages in order; tool binding is a no-op."""

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        """Streamed like a real model: text word by word, tool calls kept (the base fake drops them)."""
        message = self._generate(messages, stop=stop, run_manager=run_manager, **kwargs).generations[0].message
        if message.tool_calls:
            calls = [
                {"name": c["name"], "args": json.dumps(c["args"]), "id": c["id"], "index": i}
                for i, c in enumerate(message.tool_calls)
            ]
            yield ChatGenerationChunk(message=AIMessageChunk(content="", id=message.id, tool_call_chunks=calls))
            return
        for token in re.split(r"(\s)", message.content):
            chunk = ChatGenerationChunk(message=AIMessageChunk(content=token, id=message.id))
            if run_manager:
                run_manager.on_llm_new_token(token, chunk=chunk)
            yield chunk


def _call(name: str, args: dict, call_id: str = "call-1") -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


@pytest.fixture
def script(monkeypatch):
    """Install a fake agent; returns a function that sets the model's next replies."""
    model = ScriptedModel(messages=iter([]))
    agent = agent_graph.build_graph(model, InMemorySaver())
    monkeypatch.setattr(agent_graph, "get_agent", lambda: agent)

    def set_replies(*messages: AIMessage) -> None:
        model.messages = iter(messages)

    set_replies.agent = agent
    return set_replies


async def _chat(client, headers, message: str, conversation_id: str = "conv1"):
    return await client.post(
        "/api/v1/chat", json={"message": message, "conversation_id": conversation_id}, headers=headers
    )


def test_model_cannot_choose_the_user():
    # user_id comes from the authenticated session via run config, never from tool arguments
    for t in TOOLS:
        fields = t.tool_call_schema.model_json_schema().get("properties", {})
        assert "user_id" not in fields and "config" not in fields, t.name


def test_agent_has_no_tool_to_confirm_or_hold():
    names = {t.name for t in TOOLS}
    assert not names & {"confirm_viewing", "create_property_hold", "release_property_hold"}


@pytest.mark.asyncio
async def test_chat_requires_logged_in_buyer(client):
    body = {"message": "Xin chào", "conversation_id": "c1"}
    assert (await client.post("/api/v1/chat", json=body)).status_code == 401
    for who in (OWNER_TUAN, OPERATOR):
        headers = await auth(client, who)
        assert (await client.post("/api/v1/chat", json=body, headers=headers)).status_code == 403


@pytest.mark.asyncio
async def test_chat_without_api_key_is_unavailable(client, monkeypatch):
    for provider in ("openai", "google"):
        monkeypatch.setenv("LLM_PROVIDER", provider)
        monkeypatch.setenv("OPENAI_API_KEY", "")
        monkeypatch.setenv("GOOGLE_API_KEY", "")
        get_settings.cache_clear()
        agent_graph.get_agent.cache_clear()
        with pytest.raises(AgentUnavailableError, match="GOOGLE_API_KEY" if provider == "google" else "OPENAI"):
            agent_graph.get_agent()
    get_settings.cache_clear()
    agent_graph.get_agent.cache_clear()
    try:
        an = await auth(client, CUSTOMER_AN)
        r = await _chat(client, an, "Xin chào")
        assert r.status_code == 503
        assert r.json()["error"]["code"] == "AGENT_UNAVAILABLE"
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_agent_asks_then_recommends_from_search(client, script):
    an = await auth(client, CUSTOMER_AN)

    script(AIMessage(content="Anh/chị mua để ở hay đầu tư, ngân sách khoảng bao nhiêu?"))
    r = await _chat(client, an, "Tôi muốn tìm căn hộ ở Smart City")
    assert r.status_code == 200, r.text
    assert r.json()["recommendations"] == []

    criteria = {"project_codes": ["VHSC"], "budget_max": 4_500_000_000, "bedrooms_min": 2}
    script(_call("search_properties", criteria), AIMessage(content="Đây là 3 căn phù hợp nhất."))
    r = await _chat(client, an, "Để ở, 2 phòng ngủ, dưới 4,5 tỷ")
    body = r.json()
    assert body["reply"] == "Đây là 3 căn phù hợp nhất."
    assert body["recommendations"]
    for rec in body["recommendations"]:
        assert rec["property"]["project_code"] == "VHSC"
        assert rec["property"]["price_vnd"] <= 4_500_000_000

    state = await script.agent.aget_state({"configurable": {"thread_id": f"{AN_ID}:conv1"}})
    human = [m.content for m in state.values["messages"] if m.type == "human"]
    assert human == ["Tôi muốn tìm căn hộ ở Smart City", "Để ở, 2 phòng ngủ, dưới 4,5 tỷ"]


@pytest.mark.asyncio
async def test_conversations_are_isolated_per_buyer(client, script):
    an = await auth(client, CUSTOMER_AN)
    binh = await auth(client, CUSTOMER_BINH)
    script(AIMessage(content="Chào anh An"))
    await _chat(client, an, "Tôi là An", conversation_id="same")
    script(AIMessage(content="Chào chị Bình"))
    await _chat(client, binh, "Tôi là Bình", conversation_id="same")

    state = await script.agent.aget_state({"configurable": {"thread_id": f"{AN_ID}:same"}})
    assert [m.content for m in state.values["messages"] if m.type == "human"] == ["Tôi là An"]


@pytest.mark.asyncio
async def test_happy_path_times_then_viewing_request_as_logged_in_buyer(client, script, db):
    db.add(AvailabilitySlot(property_id=1, start_at=SAT + timedelta(hours=14.5), end_at=SAT + timedelta(hours=16)))
    db.commit()
    an = await auth(client, CUSTOMER_AN)
    windows = [{"start_at": at(14), "end_at": at(17)}]

    script(
        _call("check_property_availability", {"property_id": 1, "buyer_windows": windows}),
        AIMessage(content="Chủ căn trống 14h30, 15h hoặc 15h30. Anh chọn giờ nào?"),
    )
    body = (await _chat(client, an, "Thứ 7 tôi rảnh 14h-17h")).json()
    proposals = [datetime.fromisoformat(p["start_at"]) for p in body["viewing_times"]["proposals"]]
    assert proposals == [SAT + timedelta(hours=h) for h in (14.5, 15, 15.5)]

    script(
        _call("create_viewing_request", {"property_id": 1, "start_at": at(15), "buyer_windows": windows}),
        AIMessage(content="Đã gửi yêu cầu xem 15h tới chủ căn, chờ chủ căn xác nhận."),
    )
    body = (await _chat(client, an, "15h nhé")).json()
    [booking] = body["bookings"]
    assert booking["customer_id"] == AN_ID
    assert booking["status"] == "REQUESTED"
    assert booking["created_via"] == "AI_AGENT"
    assert booking["deal_code"].startswith("VH-")


@pytest.mark.asyncio
async def test_failed_tool_call_is_not_reported_as_booking(client, script):
    an = await auth(client, CUSTOMER_AN)
    script(
        # Seller is not free at 03:00, so the service refuses
        _call("create_viewing_request", {"property_id": 1, "start_at": at(3)}),
        AIMessage(content="Giờ này chủ căn không trống, anh chọn giờ khác nhé."),
    )
    body = (await _chat(client, an, "Đặt lịch 3h sáng")).json()
    assert body["bookings"] == []


@pytest.mark.parametrize(
    ("provider", "cls_name", "model"),
    [("openai", "ChatOpenAI", "gpt-4o-mini"), ("google", "ChatGoogleGenerativeAI", "gemini-flash-latest")],
)
def test_llm_provider_selection(monkeypatch, provider, cls_name, model):
    from src.services.llm import get_llm

    monkeypatch.setenv("LLM_PROVIDER", provider)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("MODEL_NAME", "")
    get_settings.cache_clear()
    try:
        llm = get_llm()
        assert type(llm).__name__ == cls_name
        assert model in (getattr(llm, "model_name", None) or getattr(llm, "model", ""))
    finally:
        get_settings.cache_clear()
