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
from src.db.models import AvailabilitySlot, Property
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
async def test_search_returns_viewing_times_without_extra_tool_call(client, script, db):
    db.add(AvailabilitySlot(property_id=1, start_at=SAT + timedelta(hours=14.5), end_at=SAT + timedelta(hours=16)))
    db.commit()
    an = await auth(client, CUSTOMER_AN)
    criteria = {"keyword": db.get(Property, 1).unit_code, "buyer_windows": [{"start_at": at(14), "end_at": at(17)}]}

    script(_call("search_properties", criteria), AIMessage(content="Căn này trống 14h30, 15h, 15h30."))
    body = (await _chat(client, an, "Tìm căn này, thứ 7 tôi rảnh 14h-17h")).json()
    assert body["recommendations"][0]["property"]["id"] == 1
    proposals = [datetime.fromisoformat(p["start_at"]) for p in body["viewing_times"]["proposals"]]
    assert proposals == [SAT + timedelta(hours=h) for h in (14.5, 15, 15.5)]


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
    [
        ("openai", "ChatOpenAI", "gpt-4o-mini"),
        ("google", "ChatGoogleGenerativeAI", "gemini-flash-latest"),
        ("groq", "ChatOpenAI", "openai/gpt-oss-120b"),
        ("anthropic", "ChatAnthropic", "claude-opus-5-5"),
    ],
)
def test_llm_provider_selection(monkeypatch, provider, cls_name, model):
    from src.services.llm import get_llm

    monkeypatch.setenv("LLM_PROVIDER", provider)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("MODEL_NAME", "")
    get_settings.cache_clear()
    try:
        llm = get_llm()
        assert type(llm).__name__ == cls_name
        assert model in (getattr(llm, "model_name", None) or getattr(llm, "model", ""))
    finally:
        get_settings.cache_clear()


def test_fallback_on_another_provider(monkeypatch):
    from src.services.llm import get_fallback_llm

    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_FALLBACK_PROVIDER", "openrouter")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("MODEL_NAME", "")
    monkeypatch.setenv("MODEL_FALLBACK_NAME", "google/gemini-3.8-flash")
    get_settings.cache_clear()
    try:
        llm = get_fallback_llm()
        assert type(llm).__name__ == "ChatOpenAI"
        assert llm.model_name == "google/gemini-3.8-flash"
        assert "openrouter.ai" in str(llm.openai_api_base)
    finally:
        get_settings.cache_clear()


def test_only_the_agent_caches_its_claude_prompt(monkeypatch):
    """The agent resends a growing conversation, so its Claude requests ask for prompt caching; a one-off prompt
    (follow-up writer) must not, or it pays the cache write for nothing."""
    from langchain_core.messages import HumanMessage, SystemMessage

    from src.services.llm import get_llm

    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    get_settings.cache_clear()
    try:
        messages = [SystemMessage("sys"), HumanMessage("hi")]
        cached = get_llm(prompt_cache=True)._get_request_payload(messages)
        assert cached["cache_control"] == {"type": "ephemeral"}
        assert "cache_control" not in get_llm()._get_request_payload(messages)
    finally:
        get_settings.cache_clear()


def test_tool_results_show_the_model_vietnam_time():
    from src.agents.tools import _result

    envelope = {
        "ok": True,
        "data": {
            "deal_code": "VH-2026-00001",
            "day": "2026-10-12",
            "windows": [{"start_at": "2026-10-12T09:00:00Z", "end_at": "2026-10-12T09:30:00+00:00"}],
        },
    }
    content, artifact = _result(envelope)
    seen = json.loads(content)["data"]
    # 09:00 UTC is 16:00 in Vietnam: the model must not have to convert it
    assert seen["windows"] == [{"start_at": "2026-10-12T16:00:00+07:00", "end_at": "2026-10-12T16:30:00+07:00"}]
    assert seen["deal_code"] == "VH-2026-00001" and seen["day"] == "2026-10-12"
    # The chat service renders cards and bookings from the untouched envelope
    assert artifact["data"]["windows"][0]["start_at"] == "2026-10-12T09:00:00Z"


@pytest.mark.asyncio
async def test_a_later_turn_resends_the_conversation_unchanged(monkeypatch):
    """Claude rejects earlier thinking when the system prompt or an earlier message changed since it was produced:
    the next turn must send the same system prompt and the same earlier messages, only with new ones appended."""
    seen: list[list] = []

    class Recording(ScriptedModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            seen.append(messages)
            return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    sent = iter(
        [
            datetime(2026, 10, 13, 2, 0, tzinfo=VN),
            datetime(2026, 10, 13, 2, 7, tzinfo=VN),
            datetime(2026, 10, 14, 8, 0, tzinfo=VN),
        ]
    )

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ARG003
            return next(sent)

    monkeypatch.setattr(agent_graph, "datetime", Clock)
    # The project list (and the clock) moving on between turns must not reach the system prompt
    catalogs = iter(["- VHOP1: Ocean Park", "- VHOP2: Ocean Park 2", "- VHSC: Smart City"])
    monkeypatch.setattr(agent_graph, "_project_catalog", lambda: next(catalogs))
    model = Recording(messages=iter([AIMessage(content=f"Trả lời {i}") for i in range(3)]))
    agent = agent_graph.build_graph(model, InMemorySaver(), history_window=None)
    config = {"configurable": {"thread_id": "same-prefix", "buyer_name": "an"}}

    for text in ("Chào em", "Tìm căn 2PN", "Hôm nay thì sao"):
        await agent.ainvoke({"messages": [("human", text)]}, config)

    first, second, third = seen
    assert first[0].content == second[0].content == third[0].content
    assert "13/10/2026" not in first[0].content
    assert [m.content for m in second[: len(first)]] == [m.content for m in first]
    assert [m.content for m in third[: len(second)]] == [m.content for m in second]
    # Each buyer message carries when it was sent; the calendar only on the first one of a day
    assert first[1].content.startswith("[Thời điểm khách gửi tin này: Thứ Ba 13/10/2026 02:00]\n[Lịch tham chiếu")
    assert second[3].content == "[Thời điểm khách gửi tin này: Thứ Ba 13/10/2026 02:07]\n\nTìm căn 2PN"
    assert third[5].content.startswith("[Thời điểm khách gửi tin này: Thứ Tư 14/10/2026 08:00]\n[Lịch tham chiếu")
    # What is stored (and shown in the chat history) is what the buyer typed
    stored = (await agent.aget_state(config)).values["messages"]
    assert [m.content for m in stored if m.type == "human"] == ["Chào em", "Tìm căn 2PN", "Hôm nay thì sao"]


@pytest.mark.asyncio
async def test_claude_caches_the_system_prompt_across_conversations(monkeypatch):
    """With Claude the system prompt carries its own cache breakpoint, so a new conversation with the same prompt
    reads it from cache; a fallback on another provider gets it as plain text."""
    seen: list[list] = []

    class Recording(ScriptedModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            seen.append(messages)
            return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    class Failing(ScriptedModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
            raise RuntimeError("overloaded")

    monkeypatch.setattr(agent_graph, "_project_catalog", lambda: None)
    reply = iter([AIMessage(content="Chào anh"), AIMessage(content="Chào chị")])
    agent = agent_graph.build_graph(Recording(messages=reply), InMemorySaver(), cache_system_prompt=True)
    await agent.ainvoke({"messages": [("human", "Chào em")]}, {"configurable": {"thread_id": "cached"}})
    (block,) = seen[0][0].content
    assert block["cache_control"] == {"type": "ephemeral"}
    assert block["text"].startswith("Bạn là BookingBot")

    fallback = Recording(messages=iter([AIMessage(content="Chào anh")]))
    agent = agent_graph.build_graph(
        Failing(messages=iter([])), InMemorySaver(), fallback_llm=fallback, cache_system_prompt=True
    )
    await agent.ainvoke({"messages": [("human", "Chào em")]}, {"configurable": {"thread_id": "fallback"}})
    assert seen[-1][0].content == block["text"]
