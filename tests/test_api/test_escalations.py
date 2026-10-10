"""Human escalation / operator exception queue (spec §4.3, §4.8 HITL, §6.4, AC-07)."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.db.models import (
    ActorType,
    AvailabilitySlot,
    Booking,
    Escalation,
    EscalationStatus,
    EscalationType,
    Notification,
)
from src.services import agent_api, escalation_service, property_service
from tests.helpers import CUSTOMER_AN, CUSTOMER_BINH, OPERATOR, OWNER_TUAN, auth

VN = ZoneInfo("Asia/Ho_Chi_Minh")
SAT = datetime(2030, 1, 5, tzinfo=VN)
BUYER_ID, OTHER_BUYER_ID, OWNER_ID = 1, 2, 4
PROPERTY_ID = 1


def at(hour: float) -> str:
    return (SAT + timedelta(hours=hour)).isoformat()


def _request(db) -> int:
    db.add(
        AvailabilitySlot(property_id=PROPERTY_ID, start_at=SAT + timedelta(hours=14), end_at=SAT + timedelta(hours=17))
    )
    db.commit()
    result = agent_api.create_viewing_request(BUYER_ID, PROPERTY_ID, start_at=at(15))
    assert result["ok"], result
    return result["data"]["id"]


def test_ac07_agent_escalates_no_common_slot(db):
    booking_id = _request(db)
    result = agent_api.create_human_escalation(
        BUYER_ID, "NO_COMMON_SLOT", "Khách chỉ rảnh tối thứ 6", booking_id=booking_id, thread_id="1:c1"
    )
    assert result["ok"], result
    esc = db.get(Escalation, result["data"]["id"])
    assert esc.type == EscalationType.NO_COMMON_SLOT
    assert esc.raised_by == ActorType.AI_AGENT
    assert esc.requester_id == BUYER_ID
    assert esc.property_id == PROPERTY_ID and esc.deal_id is not None
    assert esc.context == {"thread_id": "1:c1"}
    # Operators are told
    assert db.query(Notification).filter_by(event_type="ESCALATION_OPENED", user_id=7).count() == 1


def test_agent_cannot_escalate_about_someone_elses_booking_or_open_system_types(db):
    booking_id = _request(db)
    other = agent_api.create_human_escalation(OTHER_BUYER_ID, "OTHER", "Giúp tôi", booking_id=booking_id)
    assert other["error"]["code"] == "NOT_FOUND"
    system = agent_api.create_human_escalation(BUYER_ID, "SYSTEM_FAILURE", "Giả làm hệ thống")
    assert system["error"]["code"] == "BUSINESS_RULE_VIOLATION"


def test_tool_crash_opens_system_failure_escalation(db, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("database went away")

    monkeypatch.setattr(property_service, "search", boom)
    result = agent_api.search_properties({"limit": 3})
    assert result["error"]["code"] == "INTERNAL_ERROR"
    assert result["error"]["details"] == {"escalated": True}
    esc = db.query(Escalation).one()
    assert (esc.type, esc.raised_by, esc.context) == (
        EscalationType.SYSTEM_FAILURE,
        ActorType.SYSTEM,
        {"tool": "search_properties"},
    )


def test_unanswered_request_is_escalated_once(db):
    booking_id = _request(db)
    booking = db.get(Booking, booking_id)
    booking.created_at = datetime.now(UTC) - timedelta(hours=25)
    db.commit()

    assert escalation_service.escalate_unanswered_requests(db) == 1
    assert escalation_service.escalate_unanswered_requests(db) == 0
    esc = db.query(Escalation).one()
    assert (esc.type, esc.booking_id, esc.requester_id) == (EscalationType.SELLER_NO_RESPONSE, booking_id, BUYER_ID)
    # The buyer hears that support is on it
    assert db.query(Notification).filter_by(user_id=BUYER_ID, event_type="ESCALATION_OPENED").count() == 1


def test_request_for_a_close_viewing_is_due_an_hour_before_it(db):
    """Sent at 10:27 for a viewing at 14:00 next day: the seller cannot have 24 hours, only until 13:00."""
    from src.services import booking_service

    booking_id = _request(db)
    booking = db.get(Booking, booking_id)
    now = datetime.now(UTC)
    booking.created_at = now - timedelta(hours=1)
    booking.start_at, booking.end_at = now + timedelta(minutes=50), now + timedelta(minutes=80)
    db.commit()
    assert booking_service.respond_by(booking) == booking.start_at - timedelta(hours=1)

    # Less than an hour before the viewing and still unanswered: the investor's staff step in now
    assert escalation_service.escalate_unanswered_requests(db) == 1


def test_recent_or_answered_requests_are_not_escalated(db):
    _request(db)  # created just now
    assert escalation_service.escalate_unanswered_requests(db) == 0


@pytest.mark.asyncio
async def test_operator_takes_and_resolves_and_buyer_sees_outcome(client, db):
    booking_id = _request(db)
    esc_id = agent_api.create_human_escalation(BUYER_ID, "NO_COMMON_SLOT", "Cần giờ tối", booking_id=booking_id)[
        "data"
    ]["id"]
    op = await auth(client, OPERATOR)

    queue = (await client.get("/api/v1/operator/escalations", headers=op)).json()
    assert [e["id"] for e in queue] == [esc_id]

    r = await client.post(f"/api/v1/operator/escalations/{esc_id}/assign", headers=op)
    assert r.json()["status"] == "IN_PROGRESS"
    r = await client.post(
        f"/api/v1/operator/escalations/{esc_id}/resolve",
        json={"resolution": "Đã hẹn chủ căn 19h thứ 6"},
        headers=op,
    )
    assert r.json()["status"] == "RESOLVED"
    assert (await client.get("/api/v1/operator/escalations", headers=op)).json() == []
    resolved = (await client.get("/api/v1/operator/escalations", params={"status": "RESOLVED"}, headers=op)).json()
    assert [e["id"] for e in resolved] == [esc_id]

    an = await auth(client, CUSTOMER_AN)
    mine = (await client.get("/api/v1/escalations", headers=an)).json()
    assert mine[0]["resolution"] == "Đã hẹn chủ căn 19h thứ 6"
    events = [n["event_type"] for n in (await client.get("/api/v1/notifications", headers=an)).json()]
    assert "ESCALATION_RESOLVED" in events

    # Closed cases cannot be closed again
    r = await client.post(f"/api/v1/operator/escalations/{esc_id}/dismiss", json={"resolution": "x" * 5}, headers=op)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_queue_is_operator_only_and_escalations_are_private(client, db):
    agent_api.create_human_escalation(BUYER_ID, "OTHER", "Muốn nói chuyện với nhân viên")
    for who in (CUSTOMER_AN, OWNER_TUAN):
        headers = await auth(client, who)
        assert (await client.get("/api/v1/operator/escalations", headers=headers)).status_code == 403
    binh = await auth(client, CUSTOMER_BINH)
    assert (await client.get("/api/v1/escalations", headers=binh)).json() == []
    assert db.query(Escalation).filter_by(status=EscalationStatus.OPEN).count() == 1


@pytest.mark.asyncio
async def test_owner_can_still_answer_late_and_the_case_closes(client, db):
    """Past the deadline the investor's staff are told, but the request stays the owner's to answer."""
    booking_id = _request(db)
    booking = db.get(Booking, booking_id)
    booking.created_at = datetime.now(UTC) - timedelta(hours=25)
    db.commit()
    assert escalation_service.escalate_unanswered_requests(db) == 1

    tuan = await auth(client, OWNER_TUAN)
    r = await client.post(f"/api/v1/owner/bookings/{booking_id}/approve", headers=tuan)
    assert r.status_code == 200, r.text
    db.expire_all()
    esc = db.query(Escalation).filter_by(booking_id=booking_id).one()
    assert esc.status.value == "RESOLVED" and "xác nhận" in esc.resolution


@pytest.mark.asyncio
async def test_operator_name_on_a_taken_case_and_both_sides_told_the_outcome(client, db):
    """A request the seller left unanswered is about both: when closed, the buyer and the seller hear the outcome
    (unless the operator unticks one); the case shows who took it."""
    booking_id = _request(db)
    booking = db.get(Booking, booking_id)
    booking.created_at = datetime.now(UTC) - timedelta(hours=25)
    db.commit()
    escalation_service.escalate_unanswered_requests(db)
    esc = db.query(Escalation).one()

    op = await auth(client, OPERATOR)
    r = await client.post(f"/api/v1/operator/escalations/{esc.id}/assign", headers=op)
    assert (r.json()["status"], r.json()["assigned_to_name"]) == ("IN_PROGRESS", "Nguyễn Quang Dũng")
    ctx = (await client.get(f"/api/v1/operator/escalations/{esc.id}/context", headers=op)).json()
    assert (ctx["notify_buyer_default"], ctx["notify_seller_default"]) == (True, True)

    r = await client.post(
        f"/api/v1/operator/escalations/{esc.id}/resolve",
        json={"resolution": "Đã gọi chủ căn, chủ căn sẽ trả lời trong hôm nay"},
        headers=op,
    )
    assert r.status_code == 200, r.text
    told = {
        n.user_id
        for n in db.query(Notification).filter_by(event_type="ESCALATION_RESOLVED")
        if n.payload.get("escalation_id") == esc.id
    }
    assert told == {BUYER_ID, OWNER_ID}


@pytest.mark.asyncio
async def test_operator_can_tell_only_one_side(client, db):
    booking_id = _request(db)
    db.get(Booking, booking_id).created_at = datetime.now(UTC) - timedelta(hours=25)
    db.commit()
    escalation_service.escalate_unanswered_requests(db)
    esc = db.query(Escalation).one()
    op = await auth(client, OPERATOR)
    r = await client.post(
        f"/api/v1/operator/escalations/{esc.id}/resolve",
        json={"resolution": "Nhắc chủ căn trả lời sớm", "notify_buyer": False, "notify_seller": True},
        headers=op,
    )
    assert r.status_code == 200, r.text
    told = {n.user_id for n in db.query(Notification).filter_by(event_type="ESCALATION_RESOLVED")}
    assert told == {OWNER_ID}


def test_request_left_unanswered_past_its_time_expires(db):
    """The viewing time came and the owner never answered: the request closes by itself, the buyer is told."""
    from src.db.models import BookingStatus, Deal, DealStatus
    from src.services import booking_service

    booking_id = _request(db)
    booking = db.get(Booking, booking_id)
    booking.created_at = datetime.now(UTC) - timedelta(days=2)
    db.commit()
    escalation_service.escalate_unanswered_requests(db)
    booking.start_at = datetime.now(UTC) - timedelta(minutes=5)
    booking.end_at = booking.start_at + timedelta(minutes=30)
    db.commit()

    assert booking_service.expire_unanswered(db) == 1
    db.expire_all()
    booking = db.get(Booking, booking_id)
    assert booking.status == BookingStatus.EXPIRED
    assert db.get(Deal, booking.deal_id).status == DealStatus.MATCHED
    assert db.query(Notification).filter_by(user_id=BUYER_ID, event_type="VIEWING_EXPIRED").count() == 1
    assert db.query(Escalation).one().status.value == "RESOLVED"
    assert booking_service.expire_unanswered(db) == 0  # once
