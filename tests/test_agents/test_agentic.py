"""The agent acting on its own: buyer memory across conversations, follow-ups, new-match alerts."""

from datetime import UTC, datetime, timedelta
from typing import ClassVar

import pytest
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import select, update

from src.agents import graph as agent_graph
from src.db.models import Booking, BuyerProfile, Notification
from src.services import agent_followup, agent_memory, agent_writer
from tests.helpers import CUSTOMER_AN, CUSTOMER_BINH, OPERATOR, OWNER_TUAN, auth, first_free_slot
from tests.test_agents.test_graph import ScriptedModel, _call, script  # noqa: F401  (fixture)

AN_ID, BINH_ID = 1, 2
TUAN_PROPERTY = 1  # AVAILABLE, VHOP1, owned by Tuấn, has free slots
PENDING_LAN = 33  # PENDING_REVIEW, VHOP1, 3.5 tỷ, 2 PN, owned by Lan (verified)


class RecordingModel(ScriptedModel):
    """Scripted replies + remembers the messages it was given (to read the system prompt)."""

    seen: ClassVar[list] = []

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        RecordingModel.seen.append(messages)
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


async def _chat(client, headers, message, conversation_id="agentic"):
    r = await client.post(
        "/api/v1/chat", json={"message": message, "conversation_id": conversation_id}, headers=headers
    )
    assert r.status_code == 200, r.text
    return r.json()


async def _book(client, headers, property_id=TUAN_PROPERTY) -> dict:
    slot = await first_free_slot(client, property_id)
    r = await client.post(
        "/api/v1/bookings",
        json={"property_id": property_id, "start_at": slot["start_at"], "buyer_windows": []},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def _notes(db, user_id, event_type):
    return db.scalars(
        select(Notification).where(Notification.user_id == user_id, Notification.event_type == event_type)
    ).all()


# ---------- Memory across conversations ----------


@pytest.mark.asyncio
async def test_agent_remembers_needs_and_free_time_for_signed_in_buyer(client, db, script):  # noqa: F811
    an = await auth(client, CUSTOMER_AN)
    sat = (datetime.now(UTC) + timedelta(days=3)).replace(hour=2, minute=0, second=0, microsecond=0)  # 09:00 +07
    windows = [{"start_at": sat.isoformat(), "end_at": (sat + timedelta(hours=8)).isoformat()}]
    script(
        _call("search_properties", {"project_codes": ["VHOP1"], "budget_max": 3_500_000_000, "preferred_bedrooms": 2}),
        _call("check_property_availability", {"property_id": TUAN_PROPERTY, "buyer_windows": windows}, "call-2"),
        AIMessage(content="Đây là các căn và giờ trống."),
    )
    await _chat(client, an, "Căn 2PN Ocean Park dưới 3,5 tỷ, tôi rảnh thứ 7")

    profile = db.get(BuyerProfile, AN_ID)
    db.refresh(profile)
    assert profile.preferences["budget_max"] == 3_500_000_000
    assert profile.preferences["project_codes"] == ["VHOP1"]
    assert profile.budget_max_vnd == 3_500_000_000
    assert len(profile.viewing_preference["windows"]) == 1


@pytest.mark.asyncio
async def test_remembered_needs_reach_the_prompt_of_a_new_conversation(client, db, monkeypatch):
    db.execute(
        update(BuyerProfile)
        .where(BuyerProfile.user_id == AN_ID)
        .values(preferences={"project_codes": ["VHOP1"], "budget_max": 3_500_000_000})
    )
    db.commit()
    RecordingModel.seen.clear()
    model = RecordingModel(messages=iter([AIMessage(content="Chào anh, em nhớ nhu cầu của anh.")]))
    agent = agent_graph.build_graph(model, InMemorySaver())
    monkeypatch.setattr(agent_graph, "get_agent", lambda: agent)

    await _chat(client, await auth(client, CUSTOMER_AN), "Chào em", conversation_id="brand-new")

    system = next(m for m in RecordingModel.seen[0] if isinstance(m, SystemMessage)).content
    assert "Khách đã cho biết trước đây" in system
    assert "3500000000" in system


@pytest.mark.asyncio
async def test_guest_chat_stores_no_memory(client, db, script):  # noqa: F811
    script(_call("search_properties", {"budget_max": 2_000_000_000}), AIMessage(content="Có vài căn."))
    r = await client.post("/api/v1/chat/guest", json={"message": "dưới 2 tỷ", "conversation_id": "g-mem"})
    assert r.status_code == 200
    profiles = db.scalars(select(BuyerProfile).where(BuyerProfile.preferences != {})).all()
    assert profiles == []


# ---------- Follow-ups while the buyer is away ----------


@pytest.mark.asyncio
async def test_unanswered_request_gets_alternatives_after_an_hour_once(client, db):
    booking = await _book(client, await auth(client, CUSTOMER_AN))

    # Too early: nothing yet
    assert agent_followup.run(db) == 0

    db.execute(
        update(Booking).where(Booking.id == booking["id"]).values(created_at=datetime.now(UTC) - timedelta(hours=2))
    )
    db.commit()
    assert agent_followup.run(db) == 1
    (note,) = _notes(db, AN_ID, "AGENT_FOLLOWUP")
    assert note.payload["kind"] == "waiting"
    assert booking["deal_code"] in note.body
    assert note.payload["times"] or note.payload["property_ids"]
    # The request itself is untouched: only the seller can answer it
    assert db.get(Booking, booking["id"]).status.value == "REQUESTED"

    # Sent once
    assert agent_followup.run(db) == 0


@pytest.mark.asyncio
async def test_rejected_request_gets_alternatives(client, db):
    booking = await _book(client, await auth(client, CUSTOMER_AN))
    tuan = await auth(client, OWNER_TUAN)
    r = await client.post(
        f"/api/v1/owner/bookings/{booking['id']}/reject", json={"reason": "Bận việc gia đình"}, headers=tuan
    )
    assert r.status_code == 200, r.text

    assert agent_followup.run(db) == 1
    (note,) = _notes(db, AN_ID, "AGENT_FOLLOWUP")
    assert note.payload["kind"] == "rejected"
    assert "từ chối" in note.body
    # Never suggests the home the buyer already asked for as a "similar home"
    assert TUAN_PROPERTY not in note.payload["property_ids"]


@pytest.mark.asyncio
async def test_new_listing_is_announced_to_buyers_it_fits(client, db):
    db.execute(
        update(BuyerProfile)
        .where(BuyerProfile.user_id == BINH_ID)
        .values(preferences={"project_codes": ["VHOP1"], "budget_max": 4_000_000_000, "preferred_bedrooms": 2})
    )
    db.execute(
        update(BuyerProfile)
        .where(BuyerProfile.user_id == AN_ID)
        .values(preferences={"project_codes": ["VHOP1"], "budget_max": 1_000_000_000})
    )
    db.commit()

    operator = await auth(client, OPERATOR)
    r = await client.post(f"/api/v1/operator/properties/{PENDING_LAN}/approve", headers=operator)
    assert r.status_code == 200, r.text

    (note,) = _notes(db, BINH_ID, "AGENT_NEW_MATCH")
    assert note.payload["property_id"] == PENDING_LAN
    # 3.5 tỷ is over An's 1 tỷ budget
    assert _notes(db, AN_ID, "AGENT_NEW_MATCH") == []

    binh = await auth(client, CUSTOMER_BINH)
    events = [n["event_type"] for n in (await client.get("/api/v1/notifications", headers=binh)).json()]
    assert "AGENT_NEW_MATCH" in events


# ---------- Wording and memory store safety nets ----------


class _FakeReply:
    def __init__(self, text):
        self.text = text


class _FakeLLM:
    def __init__(self, text):
        self.reply = text

    def invoke(self, _messages):
        return _FakeReply(self.reply)


def test_agent_wording_falls_back_when_a_fact_is_dropped(monkeypatch):
    monkeypatch.setattr(agent_writer, "enabled", lambda: True)
    monkeypatch.setattr(agent_writer, "get_llm", lambda: _FakeLLM("Chủ căn chưa trả lời, bạn xem căn khác nhé."))
    assert agent_writer.compose("x", {"deal": "VH-2026-00001"}, "TEMPLATE", ["VH-2026-00001"]) == "TEMPLATE"

    good = "Chủ căn chưa trả lời yêu cầu VH-2026-00001; bạn có thể chọn giờ khác."
    monkeypatch.setattr(agent_writer, "get_llm", lambda: _FakeLLM(good))
    assert agent_writer.compose("x", {"deal": "VH-2026-00001"}, "TEMPLATE", ["VH-2026-00001"]) == good


@pytest.mark.asyncio
async def test_agent_memory_falls_back_when_postgres_is_unreachable(monkeypatch):
    settings = agent_memory.get_settings()
    monkeypatch.setattr(settings, "agent_memory", "postgres")
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://nobody:x@127.0.0.1:1/none")
    monkeypatch.setattr(agent_memory, "_CONNECT_TIMEOUT_SECONDS", 1)
    assert await agent_memory.open_memory() is None
    assert agent_graph._checkpointer is None


@pytest.mark.asyncio
async def test_agent_cannot_book_outside_the_buyers_free_time(client, db):
    slot = await first_free_slot(client, TUAN_PROPERTY)
    start = datetime.fromisoformat(slot["start_at"])
    # The buyer said they are free on another day only
    other_day = [
        {
            "start_at": (start + timedelta(days=1)).isoformat(),
            "end_at": (start + timedelta(days=1, hours=4)).isoformat(),
        }
    ]
    from src.services import agent_api

    env = agent_api.create_viewing_request(AN_ID, TUAN_PROPERTY, start_at=slot["start_at"], buyer_windows=other_day)
    assert env["ok"] is False
    assert env["error"]["details"]["reason"] == "OUTSIDE_BUYER_WINDOWS"
    assert db.scalars(select(Booking)).all() == []

    inside = [{"start_at": start.isoformat(), "end_at": (start + timedelta(hours=2)).isoformat()}]
    env = agent_api.create_viewing_request(AN_ID, TUAN_PROPERTY, start_at=slot["start_at"], buyer_windows=inside)
    assert env["ok"] is True, env


class _OverloadedModel(ScriptedModel):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise RuntimeError("503 UNAVAILABLE: model is experiencing high demand")


@pytest.mark.asyncio
async def test_lighter_model_answers_when_the_main_one_is_overloaded(client, monkeypatch):
    backup = ScriptedModel(messages=iter([AIMessage(content="Em vẫn ở đây, anh cần tìm căn thế nào?")]))
    agent = agent_graph.build_graph(_OverloadedModel(messages=iter([])), InMemorySaver(), backup)
    monkeypatch.setattr(agent_graph, "get_agent", lambda: agent)

    body = await _chat(client, await auth(client, CUSTOMER_AN), "Chào em", conversation_id="overload")
    assert body["reply"] == "Em vẫn ở đây, anh cần tìm căn thế nào?"
