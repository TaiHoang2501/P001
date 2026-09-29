"""The AI tool contract: same rules as the web, structured errors, audited as AI_AGENT."""

from sqlalchemy import select

from src.db.models import ActorType, AuditLog
from src.services import agent_api

CUSTOMER_ID = 1
OWNER_ID = 4


def test_search_and_detail():
    result = agent_api.search_properties({"project_codes": ["VHOP1"], "bedrooms_min": 1, "limit": 3})
    assert result["ok"] is True
    recs = result["data"]["results"]
    assert 0 < len(recs) <= 3
    detail = agent_api.get_property_detail(recs[0]["property"]["id"])
    assert detail["ok"] is True


def test_invalid_criteria_returns_validation_error():
    result = agent_api.search_properties({"budget_min": 5, "budget_max": 1})
    assert result["ok"] is False
    assert result["error"]["code"] == "VALIDATION_ERROR"


def test_booking_via_agent_is_requested_and_audited_as_ai(db):
    avail = agent_api.check_availability(1)
    slot_id = avail["data"]["free_slots"][0]["id"]

    result = agent_api.create_booking_request(CUSTOMER_ID, 1, slot_id, note="Qua chatbot")
    assert result["ok"] is True
    booking = result["data"]
    # The agent can never produce a confirmed booking (AC-02)
    assert booking["status"] == "REQUESTED"
    assert booking["created_via"] == "AI_AGENT"

    log = db.scalar(select(AuditLog).where(AuditLog.target_type == "booking", AuditLog.target_id == booking["id"]))
    assert log.actor_type == ActorType.AI_AGENT
    assert log.actor_id == CUSTOMER_ID

    again = agent_api.create_booking_request(2, 1, slot_id)
    assert again["ok"] is False
    assert again["error"]["code"] == "SLOT_UNAVAILABLE"
    assert again["error"]["details"]["free_slots"]


def test_agent_cannot_book_as_owner_or_cancel_others():
    slot_id = agent_api.check_availability(1)["data"]["free_slots"][0]["id"]
    as_owner = agent_api.create_booking_request(OWNER_ID, 1, slot_id)
    assert as_owner["error"]["code"] == "FORBIDDEN"

    booking_id = agent_api.create_booking_request(CUSTOMER_ID, 1, slot_id)["data"]["id"]
    other = agent_api.cancel_booking(2, booking_id)
    assert other["error"]["code"] == "NOT_FOUND"
    mine = agent_api.cancel_booking(CUSTOMER_ID, booking_id)
    assert mine["data"]["status"] == "CANCELLED"


def test_booking_status_lists_only_own_bookings():
    slot_id = agent_api.check_availability(1)["data"]["free_slots"][0]["id"]
    agent_api.create_booking_request(CUSTOMER_ID, 1, slot_id)
    assert len(agent_api.get_booking_status(CUSTOMER_ID)["data"]) == 1
    assert agent_api.get_booking_status(2)["data"] == []
