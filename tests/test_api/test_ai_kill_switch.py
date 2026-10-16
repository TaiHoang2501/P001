"""AI kill switch: a developer (X-Admin-Token) turns the assistant off; chat answers AI_DISABLED without calling the
model. No user role (operators included) can see or flip it."""

import pytest
from langchain_core.messages import AIMessage

from src.config import get_settings
from src.db.models import AuditLog
from tests.helpers import CUSTOMER_AN, OPERATOR, auth
from tests.test_agents.test_graph import script  # noqa: F401  (fixture)

BODY = {"message": "Tìm căn 2PN dưới 4 tỷ", "conversation_id": "ks-1"}
TOKEN = "dev-secret-token-for-tests"
DEV = {"X-Admin-Token": TOKEN}


@pytest.fixture
def admin_token(monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_api_token", TOKEN)


@pytest.mark.asyncio
async def test_developer_turns_ai_off_and_on(client, db, script, admin_token):  # noqa: F811
    an = await auth(client, CUSTOMER_AN)

    status = (await client.get("/api/v1/chat/assistant-status")).json()
    assert status["enabled"] is True and status["message"] is None

    # Turning it off needs a reason
    r = await client.put("/api/v1/admin/ai-assistant", json={"enabled": False}, headers=DEV)
    assert r.status_code == 422
    r = await client.put("/api/v1/admin/ai-assistant", json={"enabled": False, "reason": "provider down"}, headers=DEV)
    assert r.status_code == 200, r.text
    assert (await client.get("/api/v1/status")).json()["status"] == "maintenance"
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

    r = await client.put("/api/v1/admin/ai-assistant", json={"enabled": True}, headers=DEV)
    assert r.json()["enabled"] is True
    script(AIMessage(content="Dạ em đây ạ."))
    r = await client.post("/api/v1/chat", json=BODY, headers=an)
    assert r.status_code == 200, r.text

    audits = db.query(AuditLog).filter(AuditLog.target_type == "system_setting").order_by(AuditLog.id).all()
    assert [a.action for a in audits] == ["AI_ASSISTANT_DISABLED", "AI_ASSISTANT_ENABLED"]
    assert audits[0].extra["reason"] == "provider down" and audits[0].extra["via"] == "admin_api"


@pytest.mark.asyncio
async def test_no_user_role_can_flip_the_switch(client, admin_token):
    op = await auth(client, OPERATOR)
    an = await auth(client, CUSTOMER_AN)
    # Operators have no kill switch endpoint at all
    assert (await client.put("/api/v1/operator/ai-assistant", json={"enabled": False}, headers=op)).status_code == 404
    # A user's bearer token is not the admin token
    for headers in (op, an, {}, {"X-Admin-Token": "wrong"}):
        r = await client.put(
            "/api/v1/admin/ai-assistant", json={"enabled": False, "reason": "thử quyền"}, headers=headers
        )
        assert r.status_code == 401, r.text
    assert (await client.get("/api/v1/chat/assistant-status")).json()["enabled"] is True


@pytest.mark.asyncio
async def test_admin_api_is_off_without_a_token(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_api_token", "")
    r = await client.put(
        "/api/v1/admin/ai-assistant", json={"enabled": False, "reason": "thử quyền"}, headers={"X-Admin-Token": ""}
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_client_ip_diagnostics(client, admin_token):
    r = await client.get(
        "/api/v1/admin/diagnostics/client-ip", headers={**DEV, "x-forwarded-for": "1.1.1.1, 203.0.113.5"}
    )
    assert r.status_code == 200
    assert r.json()["client_ip"] == "203.0.113.5"
