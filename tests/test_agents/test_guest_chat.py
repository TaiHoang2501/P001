"""New buyers chat as guests; booking needs an account, then the guest conversation moves to that account."""

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import func, select

from src.db.models import Booking
from tests.helpers import first_free_slot, otp_auth
from tests.test_agents.test_graph import _call, script  # noqa: F401  (fixture)

PROPERTY = 1  # AVAILABLE seed listing with free slots


async def _guest(client, message: str, conversation_id: str = "guest-conv"):
    return await client.post("/api/v1/chat/guest", json={"message": message, "conversation_id": conversation_id})


@pytest.mark.asyncio
async def test_guest_can_search_without_account(client, script):  # noqa: F811
    script(
        _call("search_properties", {"budget_max_vnd": 5_000_000_000, "bedrooms": 2}),
        AIMessage(content="Có vài căn phù hợp."),
    )
    r = await _guest(client, "Căn 2PN dưới 5 tỷ")
    assert r.status_code == 200, r.text
    assert r.json()["recommendations"]
    assert r.json()["needs_account"] is False
    assert r.json()["pending_viewing"] is None


@pytest.mark.asyncio
async def test_guest_booking_asks_for_account_then_completes(client, db, script):  # noqa: F811
    slot = await first_free_slot(client, PROPERTY)
    script(
        _call("create_viewing_request", {"property_id": PROPERTY, "start_at": slot["start_at"]}),
        AIMessage(content="Bạn đăng ký nhanh bằng số điện thoại để gửi yêu cầu nhé."),
    )
    r = await _guest(client, "Tôi chọn giờ đó")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["needs_account"] is True
    assert body["bookings"] == []
    assert body["pending_viewing"]["property_id"] == PROPERTY
    # Nothing was booked for the guest
    assert db.scalar(select(func.count()).select_from(Booking)) == 0

    # Sign up with phone + OTP, move the conversation, then send the pending request
    buyer = await otp_auth(client, "0977000123", full_name="Khách Mới", role="CUSTOMER")
    r = await client.post("/api/v1/chat/guest/guest-conv/claim", headers=buyer)
    assert r.json() == {"claimed": True}
    pending = body["pending_viewing"]
    r = await client.post(
        "/api/v1/bookings",
        json={"property_id": pending["property_id"], "start_at": pending["start_at"], "buyer_windows": []},
        headers=buyer,
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "REQUESTED"

    # The agent keeps the guest context under the new account; the guest thread is gone
    me = (await client.get("/api/v1/auth/me", headers=buyer)).json()["id"]
    state = await script.agent.aget_state({"configurable": {"thread_id": f"{me}:guest-conv"}})
    assert any(isinstance(m, AIMessage) and m.tool_calls for m in state.values["messages"])
    guest_state = await script.agent.aget_state({"configurable": {"thread_id": "guest:guest-conv"}})
    assert not guest_state.values.get("messages")

    # Claiming again does nothing
    r = await client.post("/api/v1/chat/guest/guest-conv/claim", headers=buyer)
    assert r.json() == {"claimed": False}


@pytest.mark.asyncio
async def test_claim_needs_a_buyer_account(client, script):  # noqa: F811
    assert (await client.post("/api/v1/chat/guest/whatever/claim")).status_code == 401
