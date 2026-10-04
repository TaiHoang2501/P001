"""Streaming chat (SSE): the reply arrives piece by piece; cards still come only from tool results."""

import json

import pytest
from langchain_core.messages import AIMessage

from src.db.models import AiMessage
from tests.helpers import CUSTOMER_AN, OWNER_TUAN, auth
from tests.test_agents.test_graph import _call, script  # noqa: F401  (fixture)

BODY = {"message": "Căn 2PN dưới 5 tỷ", "conversation_id": "stream-1"}


def _events(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


@pytest.mark.asyncio
async def test_buyer_reply_streams_then_done_has_tool_results(client, db, script):  # noqa: F811
    script(
        _call("search_properties", {"budget_max_vnd": 5_000_000_000, "bedrooms": 2}),
        AIMessage(content="Có vài căn phù hợp với anh chị."),
    )
    an = await auth(client, CUSTOMER_AN)
    r = await client.post("/api/v1/chat/stream", json=BODY, headers=an)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/event-stream")
    events = _events(r.text)
    names = [n for n, _ in events]

    # Tool status first, then the reply word by word, then the final result
    assert events[0] == ("tools", {"names": ["search_properties"]})
    tokens = [d["text"] for n, d in events if n == "token"]
    assert len(tokens) > 1
    assert "".join(tokens) == "Có vài căn phù hợp với anh chị."
    assert names[-1] == "done"
    done = events[-1][1]
    assert done["reply"] == "Có vài căn phù hợp với anh chị."
    assert done["recommendations"]
    # The turn is recorded like a non-streaming one
    assert db.query(AiMessage).count() > 0


@pytest.mark.asyncio
async def test_guest_stream_asks_for_account_on_booking(client, script):  # noqa: F811
    script(
        _call("create_viewing_request", {"property_id": 1, "start_at": "2030-01-05T15:00:00+07:00"}),
        AIMessage(content="Bạn đăng ký nhanh để gửi yêu cầu nhé."),
    )
    r = await client.post("/api/v1/chat/guest/stream", json={**BODY, "conversation_id": "guest-stream"})
    assert r.status_code == 200, r.text
    done = _events(r.text)[-1]
    assert done[0] == "done"
    assert done[1]["needs_account"] is True
    assert done[1]["pending_viewing"]["property_id"] == 1
    assert done[1]["bookings"] == []


@pytest.mark.asyncio
async def test_stream_needs_a_buyer(client, script):  # noqa: F811
    assert (await client.post("/api/v1/chat/stream", json=BODY)).status_code == 401
    owner = await auth(client, OWNER_TUAN)
    assert (await client.post("/api/v1/chat/stream", json=BODY, headers=owner)).status_code == 403


@pytest.mark.asyncio
async def test_model_failure_becomes_an_error_event(client, script):  # noqa: F811
    script()  # no scripted reply: the model fails
    r = await client.post("/api/v1/chat/guest/stream", json={**BODY, "conversation_id": "guest-fail"})
    assert r.status_code == 200
    assert _events(r.text) == [
        ("error", {"code": "AGENT_UNAVAILABLE", "message": "AI assistant is temporarily unavailable, please try again"})
    ]
