"""The AI tool contract (spec §4.18): same rules as the web, structured errors, audited as AI_AGENT."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from src.db.models import ActorType, AuditLog, AvailabilitySlot, SellerProfile, SellerVerificationStatus
from src.services import agent_api

BUYER_ID = 1
OTHER_BUYER_ID = 2
OWNER_ID = 4
PROPERTY_ID = 1  # owned by OWNER_ID
VN = ZoneInfo("Asia/Ho_Chi_Minh")
SAT = datetime(2030, 1, 5, tzinfo=VN)


def at(hour: float) -> str:
    return (SAT + timedelta(hours=hour)).isoformat()


def _seller_free(db, start: float, end: float) -> None:
    db.add(
        AvailabilitySlot(
            property_id=PROPERTY_ID, start_at=SAT + timedelta(hours=start), end_at=SAT + timedelta(hours=end)
        )
    )
    db.commit()


def test_search_and_detail():
    result = agent_api.search_properties({"project_codes": ["VHOP1"], "bedrooms_min": 1, "limit": 3})
    assert result["ok"] is True
    recs = result["data"]["results"]
    assert 0 < len(recs) <= 3
    assert agent_api.get_property_detail(recs[0]["property"]["id"])["ok"] is True


def test_invalid_criteria_returns_validation_error():
    result = agent_api.search_properties({"budget_min": 5, "budget_max": 1})
    assert result["ok"] is False
    assert result["error"]["code"] == "VALIDATION_ERROR"


def test_seller_status_has_no_pii(db):
    result = agent_api.get_seller_status(PROPERTY_ID)
    assert result["data"] == {"property_id": PROPERTY_ID, "seller_verified": True}

    db.get(SellerProfile, OWNER_ID).verification_status = SellerVerificationStatus.UNVERIFIED
    db.commit()
    assert agent_api.get_seller_status(PROPERTY_ID)["data"]["seller_verified"] is False


def test_check_seller_availability_lists_free_windows(db):
    _seller_free(db, 14.5, 16)
    windows = agent_api.check_seller_availability(PROPERTY_ID)["data"]
    assert windows
    assert all(datetime.fromisoformat(w["end_at"]) > datetime.fromisoformat(w["start_at"]) for w in windows)


def test_ac06_check_property_availability(db):
    _seller_free(db, 14.5, 16)
    result = agent_api.check_property_availability(PROPERTY_ID, [{"start_at": at(14), "end_at": at(17)}])
    assert result["ok"] is True
    starts = [datetime.fromisoformat(p["start_at"]) for p in result["data"]["proposals"]]
    assert starts == [SAT + timedelta(hours=h) for h in (14.5, 15, 15.5)]


def test_viewing_request_via_agent_is_requested_opens_deal_and_is_audited_as_ai(db):
    _seller_free(db, 14.5, 16)
    result = agent_api.create_viewing_request(
        BUYER_ID, PROPERTY_ID, start_at=at(15), buyer_windows=[{"start_at": at(14), "end_at": at(17)}]
    )
    assert result["ok"] is True, result
    booking = result["data"]
    # The agent can never produce a confirmed booking (AC-05)
    assert booking["status"] == "REQUESTED"
    assert booking["created_via"] == "AI_AGENT"
    assert booking["deal_code"].startswith("VH-")

    log = db.scalar(select(AuditLog).where(AuditLog.target_type == "booking", AuditLog.target_id == booking["id"]))
    assert log.actor_type == ActorType.AI_AGENT
    assert log.actor_id == BUYER_ID

    deals = agent_api.get_deal_status(BUYER_ID)["data"]
    assert [d["id"] for d in deals] == [booking["deal_id"]]

    again = agent_api.create_viewing_request(OTHER_BUYER_ID, PROPERTY_ID, start_at=at(15))
    assert again["ok"] is False
    assert again["error"]["code"] == "SLOT_UNAVAILABLE"


def test_agent_cannot_book_as_owner_or_cancel_others(db):
    _seller_free(db, 14.5, 16)
    as_owner = agent_api.create_viewing_request(OWNER_ID, PROPERTY_ID, start_at=at(15))
    assert as_owner["error"]["code"] == "FORBIDDEN"

    booking_id = agent_api.create_viewing_request(BUYER_ID, PROPERTY_ID, start_at=at(15))["data"]["id"]
    assert agent_api.cancel_viewing(OTHER_BUYER_ID, booking_id)["error"]["code"] == "NOT_FOUND"
    assert agent_api.cancel_viewing(BUYER_ID, booking_id)["data"]["status"] == "CANCELLED"


def test_reschedule_requires_confirmed_viewing(db):
    _seller_free(db, 14.5, 16)
    booking_id = agent_api.create_viewing_request(BUYER_ID, PROPERTY_ID, start_at=at(15))["data"]["id"]
    result = agent_api.reschedule_viewing(BUYER_ID, booking_id, at(15.5))
    assert result["error"]["code"] == "STATE_CONFLICT"


def test_status_lists_only_own_bookings(db):
    _seller_free(db, 14.5, 16)
    agent_api.create_viewing_request(BUYER_ID, PROPERTY_ID, start_at=at(15))
    assert len(agent_api.get_booking_status(BUYER_ID)["data"]) == 1
    assert agent_api.get_booking_status(OTHER_BUYER_ID)["data"] == []
    assert agent_api.get_deal_status(OTHER_BUYER_ID)["data"] == []


def test_no_confirm_or_hold_functions_exposed():
    # AC-05 / §4.13: only the owner confirms; holds are created by the booking service
    for name in ("confirm_viewing", "create_property_hold", "release_property_hold"):
        assert not hasattr(agent_api, name)
