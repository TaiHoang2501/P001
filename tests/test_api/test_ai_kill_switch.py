"""AI kill switch: an operator turns the assistant off; chat answers AI_DISABLED without calling the model."""

import pytest
from langchain_core.messages import AIMessage

from src.db.models import AuditLog
from tests.helpers import CUSTOMER_AN, OPERATOR, auth
from tests.test_agents.test_graph import script  # noqa: F401  (fixture)

BODY = {"message": "Tìm căn 2PN dưới 4 tỷ", "conversation_id": "ks-1"}


@pytest.mark.asyncio
async def test_operator_turns_ai_off_and_on(client, db, script):  # noqa: F811
    op = await auth(client, OPERATOR)
    an = await auth(client, CUSTOMER_AN)

    status = (await client.get("/api/v1/chat/assistant-status")).json()
    assert status["enabled"] is True and status["message"] is None

    r = await client.put("/api/v1/operator/ai-assistant", json={"enabled": False}, headers=op)
    assert r.status_code == 200, r.text
    assert r.json()["enabled"] is False

    status = (await client.get("/api/v1/chat/assistant-status")).json()
    assert status["enabled"] is False
    assert "đang bảo trì" in status["message"] and status["hotline"] in status["message"]

    # No model reply is scripted: every chat endpoint must stop before the model
    script()
    for path, headers in (
        ("/api/v1/chat", an),
        ("/api/v1/chat/stream", an),
        ("/api/v1/chat/guest", {}),
        ("/api/v1/chat/guest/stream", {}),
    ):
        r = await client.post(path, json=BODY, headers=headers)
        assert r.status_code == 503, (path, r.text)
        assert r.json()["error"]["code"] == "AI_DISABLED"

    r = await client.put("/api/v1/operator/ai-assistant", json={"enabled": True}, headers=op)
    assert r.json()["enabled"] is True
    script(AIMessage(content="Dạ em đây ạ."))
    r = await client.post("/api/v1/chat", json=BODY, headers=an)
    assert r.status_code == 200, r.text

    actions = [a.action for a in db.query(AuditLog).filter(AuditLog.target_type == "system_setting")]
    assert actions == ["AI_ASSISTANT_DISABLED", "AI_ASSISTANT_ENABLED"]


@pytest.mark.asyncio
async def test_only_operators_flip_the_switch(client):
    an = await auth(client, CUSTOMER_AN)
    r = await client.put("/api/v1/operator/ai-assistant", json={"enabled": False}, headers=an)
    assert r.status_code == 403
    assert (await client.get("/api/v1/chat/assistant-status")).json()["enabled"] is True
