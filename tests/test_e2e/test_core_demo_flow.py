"""End-to-end Core Demo Flow (spec §12, §6.1 Happy Path) through the public API.

Seller signs up with OTP -> verified by the investor -> lists a unit with its ownership document ->
listing approved -> opens viewing availability. Buyer signs up with OTP -> chats with the AI agent
(scripted model: no LLM call) -> gets the unit recommended -> viewing times matched -> viewing
request with a Deal ID -> seller confirms -> viewing hold -> reminders -> viewing done.
Every acceptance criterion touched on the way is asserted where it happens.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import select

from src.agents import graph as agent_graph
from src.db.models import (
    ActorType,
    AuditLog,
    HoldStatus,
    Notification,
    NotificationStatus,
    PropertyHold,
    Recommendation,
)
from src.services import booking_service, hold_service, notification_service
from tests.helpers import OPERATOR, UNCLAIMED_RED_BOOK, auth

VN = ZoneInfo("Asia/Ho_Chi_Minh")
SAT = datetime(2030, 1, 5, tzinfo=VN)
PRICE = 3_912_000_000  # unique among seeded listings, so the search result is unambiguous


def at(hour: float) -> datetime:
    return SAT + timedelta(hours=hour)


class ScriptedModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self


def _call(name: str, args: dict) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call-{name}"}])


async def _otp_signup(client, phone: str, name: str, role: str) -> dict:
    code = (await client.post("/api/v1/auth/otp/request", json={"target": phone})).json()["debug_code"]
    r = await client.post(
        "/api/v1/auth/otp/verify", json={"target": phone, "code": code, "full_name": name, "role": role}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _events(client, headers) -> list[str]:
    return [n["event_type"] for n in (await client.get("/api/v1/notifications", headers=headers)).json()]


@pytest.mark.asyncio
async def test_core_demo_flow(client, db, monkeypatch):
    model = ScriptedModel(messages=iter([]))
    agent = agent_graph.build_graph(model, InMemorySaver())
    monkeypatch.setattr(agent_graph, "get_agent", lambda: agent)
    operator = await auth(client, OPERATOR)

    # ---- Seller onboarding (spec §4.5): phone OTP login, then red book + OTP to the phone on record ----
    seller = await _otp_signup(client, "0966000001", "Chủ Căn Demo", "OWNER")
    assert (await client.get("/api/v1/owner/verification", headers=seller)).json()[
        "verification_status"
    ] == "UNVERIFIED"
    claim = {k: v for k, v in UNCLAIMED_RED_BOOK.items() if k != "id"}
    challenge = (await client.post("/api/v1/owner/ownership/claim", json=claim, headers=seller)).json()
    r = await client.post(
        f"/api/v1/owner/ownership/{challenge['verification_id']}/confirm",
        json={"code": challenge["debug_code"]},
        headers=seller,
    )
    assert r.json()["status"] == "VERIFIED"
    # The red book puts the seller in the operator's queue; the operator verifies them
    assert (await client.get("/api/v1/owner/verification", headers=seller)).json()["verification_status"] == "PENDING"
    seller_id = (await client.get("/api/v1/auth/me", headers=seller)).json()["id"]
    r = await client.post(f"/api/v1/operator/sellers/{seller_id}/verify", headers=operator)
    assert r.json()["verification_status"] == "VERIFIED"

    listing = {
        "building_id": 1,
        "unit_code": "DEMO-1508",
        "property_type": "APARTMENT",
        "bedrooms": 2,
        "bathrooms": 2,
        "area_m2": "71.5",
        "floor": 15,
        "price_vnd": PRICE,
        "direction": "SE",
        "view": "LAKE",
        "furnishing": "FULL",
        "legal_status": "PINK_BOOK",
        "description": "Căn demo 2PN view hồ",
        "verification_id": challenge["verification_id"],
    }
    prop = (await client.post("/api/v1/owner/properties", json=listing, headers=seller)).json()
    pid = prop["id"]
    assert (await client.post(f"/api/v1/owner/properties/{pid}/submit", headers=seller)).json()[
        "status"
    ] == "PENDING_REVIEW"
    assert (await client.post(f"/api/v1/operator/properties/{pid}/approve", headers=operator)).json()[
        "status"
    ] == "AVAILABLE"
    assert "LISTING_APPROVED" in await _events(client, seller)

    slot = {"start_at": at(14.5).isoformat(), "end_at": at(16).isoformat()}
    assert (await client.post(f"/api/v1/owner/properties/{pid}/slots", json=slot, headers=seller)).status_code == 201

    # ---- Buyer discovers the unit through the AI agent (spec §4.4) ----
    buyer = await _otp_signup(client, "0966000002", "Người Mua Demo", "CUSTOMER")
    buyer_id = (await client.get("/api/v1/auth/me", headers=buyer)).json()["id"]

    async def chat(message: str, *replies: AIMessage) -> dict:
        model.messages = iter(replies)
        r = await client.post("/api/v1/chat", json={"message": message, "conversation_id": "demo"}, headers=buyer)
        assert r.status_code == 200, r.text
        return r.json()

    criteria = {"project_codes": [prop["project_code"]], "budget_min": PRICE, "budget_max": PRICE, "bedrooms_min": 2}
    body = await chat(
        "Tôi cần căn 2PN khoảng 3,9 tỷ",
        _call("search_properties", criteria),
        AIMessage(content="Có căn DEMO-1508 phù hợp."),
    )
    # AC-01: the card comes from the database, not from the model's text
    assert [r["property"]["id"] for r in body["recommendations"]] == [pid]

    windows = [{"start_at": at(14).isoformat(), "end_at": at(17).isoformat()}]
    body = await chat(
        "Thứ 7 tôi rảnh 14h-17h",
        _call("check_property_availability", {"property_id": pid, "buyer_windows": windows}),
        AIMessage(content="Chủ căn trống 14h30, 15h, 15h30."),
    )
    # AC-06: buyer 14-17 ∩ seller 14:30-16 -> 14:30 / 15:00 / 15:30
    assert [datetime.fromisoformat(p["start_at"]) for p in body["viewing_times"]["proposals"]] == [
        at(14.5),
        at(15),
        at(15.5),
    ]

    body = await chat(
        "Đặt 15h",
        _call("create_viewing_request", {"property_id": pid, "start_at": at(15).isoformat(), "buyer_windows": windows}),
        AIMessage(content="Đã gửi yêu cầu tới chủ căn, chờ chủ căn xác nhận."),
    )
    [booking] = body["bookings"]
    # AC-02 / AC-09: a Deal ID, request goes to the seller; AC-05: not confirmed yet
    assert booking["deal_code"].startswith("VH-")
    assert (booking["status"], booking["created_via"], booking["hold_status"]) == ("REQUESTED", "AI_AGENT", None)
    deal = (await client.get(f"/api/v1/deals/{booking['deal_id']}", headers=buyer)).json()
    assert deal["status"] == "VIEWING_REQUESTED"
    rec = db.scalar(
        select(Recommendation).where(Recommendation.buyer_id == buyer_id, Recommendation.property_id == pid)
    )
    assert rec is not None  # the deal is attributed to the AI recommendation

    # ---- Seller confirms (HITL) ----
    [seen] = (await client.get("/api/v1/owner/bookings", headers=seller)).json()
    assert "VIEWING_REQUESTED" in await _events(client, seller)
    # AC-03: privacy level 1, the buyer's name but never their phone
    assert seen["buyer_ref"] == f"Buyer #{buyer_id}"
    assert seen["customer_name"] and seen["customer_phone"] is None

    r = await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=seller)
    assert (r.json()["status"], r.json()["hold_status"]) == ("CONFIRMED", "ACTIVE")
    assert "VIEWING_CONFIRMED" in await _events(client, buyer)
    assert (await client.get(f"/api/v1/deals/{booking['deal_id']}", headers=buyer)).json()[
        "status"
    ] == "VIEWING_CONFIRMED"

    # AC-08: nobody else can take that window
    other = await _otp_signup(client, "0966000003", "Người Mua Khác", "CUSTOMER")
    r = await client.post("/api/v1/bookings", json={"property_id": pid, "start_at": at(15).isoformat()}, headers=other)
    assert r.json()["error"]["code"] == "SLOT_UNAVAILABLE"

    # ---- Reminders and the viewing itself ----
    assert notification_service.deliver_due(db, now=at(15) - timedelta(hours=2) + timedelta(minutes=1)) == 4
    reminders = db.scalars(
        select(Notification).where(Notification.booking_id == booking["id"], Notification.event_type.like("REMINDER_%"))
    ).all()
    assert {n.status for n in reminders} == {NotificationStatus.SENT}

    monkeypatch.setattr(booking_service, "_now", lambda: at(15.6))
    r = await client.post(f"/api/v1/owner/bookings/{booking['id']}/complete", headers=seller)
    assert r.json()["status"] == "COMPLETED"
    assert (await client.get(f"/api/v1/deals/{booking['deal_id']}", headers=buyer)).json()["status"] == "VIEWED"
    hold = db.scalar(select(PropertyHold).where(PropertyHold.booking_id == booking["id"]))
    db.refresh(hold)
    assert hold.status == HoldStatus.RELEASED
    assert hold_service.expire_finished(db, now=at(16)) == 0

    # The AI's action is audited as the AI acting for the buyer
    log = db.scalar(select(AuditLog).where(AuditLog.action == "booking.request", AuditLog.target_id == booking["id"]))
    assert (log.actor_type, log.actor_id) == (ActorType.AI_AGENT, buyer_id)
