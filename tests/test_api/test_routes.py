import pytest

from tests.helpers import CUSTOMER_AN, auth


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0"
    assert "environment" in data


@pytest.mark.asyncio
async def test_chat_empty_message(client):
    an = await auth(client, CUSTOMER_AN)
    response = await client.post("/api/v1/chat", json={"message": "", "conversation_id": "c1"}, headers=an)
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_agent_status(client):
    response = await client.get("/api/v1/status")
    assert response.status_code == 200
