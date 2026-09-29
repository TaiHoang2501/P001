"""Notifications and viewing reminders (spec §4.19)."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.db.models import Notification, NotificationStatus
from src.services import notification_service
from tests.helpers import CUSTOMER_AN, CUSTOMER_BINH, OPERATOR, OWNER_TUAN, auth

VN = ZoneInfo("Asia/Ho_Chi_Minh")
PROPERTY_ID = 1  # Tuấn's
BUYER_ID, OWNER_ID = 1, 4
SAT = datetime(2030, 1, 5, tzinfo=VN)


def at(hour: float) -> str:
    return (SAT + timedelta(hours=hour)).isoformat()


async def _events(client, headers) -> list[str]:
    return [n["event_type"] for n in (await client.get("/api/v1/notifications", headers=headers)).json()]


async def _booked(client) -> tuple[dict, dict, dict]:
    tuan = await auth(client, OWNER_TUAN)
    await client.post(
        f"/api/v1/owner/properties/{PROPERTY_ID}/slots", json={"start_at": at(14), "end_at": at(17)}, headers=tuan
    )
    an = await auth(client, CUSTOMER_AN)
    r = await client.post("/api/v1/bookings", json={"property_id": PROPERTY_ID, "start_at": at(15)}, headers=an)
    assert r.status_code == 201, r.text
    return tuan, an, r.json()


def _reminders(db, booking_id: int) -> list[Notification]:
    db.expire_all()
    return (
        db.query(Notification)
        .filter(Notification.booking_id == booking_id, Notification.event_type.like("REMINDER_%"))
        .order_by(Notification.scheduled_at, Notification.user_id)
        .all()
    )


@pytest.mark.asyncio
async def test_seller_is_notified_of_new_request_without_buyer_pii(client):
    tuan, _, booking = await _booked(client)
    [n] = (await client.get("/api/v1/notifications", headers=tuan)).json()
    assert n["event_type"] == "VIEWING_REQUESTED"
    assert n["booking_id"] == booking["id"]
    assert booking["deal_code"] in n["body"]
    assert f"Buyer #{BUYER_ID}" in n["body"]
    assert "Nguyễn Văn An" not in n["body"] and "0901111222" not in n["body"]


@pytest.mark.asyncio
async def test_confirm_notifies_buyer_and_seller_and_schedules_reminders(client, db):
    tuan, an, booking = await _booked(client)
    await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=tuan)

    assert await _events(client, an) == ["VIEWING_CONFIRMED"]
    assert set(await _events(client, tuan)) == {"VIEWING_REQUESTED", "HOLD_CREATED"}

    reminders = _reminders(db, booking["id"])
    start = SAT + timedelta(hours=15)
    assert [(r.event_type, r.scheduled_at, r.user_id) for r in reminders] == [
        ("REMINDER_T24h", start - timedelta(hours=24), BUYER_ID),
        ("REMINDER_T24h", start - timedelta(hours=24), OWNER_ID),
        ("REMINDER_T2h", start - timedelta(hours=2), BUYER_ID),
        ("REMINDER_T2h", start - timedelta(hours=2), OWNER_ID),
    ]
    assert all(r.status == NotificationStatus.PENDING for r in reminders)


@pytest.mark.asyncio
async def test_reminders_are_delivered_when_due(client, db):
    tuan, an, booking = await _booked(client)
    await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=tuan)
    # Not yet due: nothing delivered, buyer still sees one notification
    assert notification_service.deliver_due(db) == 0

    t24 = SAT + timedelta(hours=15) - timedelta(hours=24)
    assert notification_service.deliver_due(db, now=t24 + timedelta(minutes=1)) == 2
    assert (await _events(client, an))[0] == "REMINDER_T24h"
    assert notification_service.deliver_due(db, now=t24 + timedelta(minutes=2)) == 0


@pytest.mark.asyncio
async def test_cancel_cancels_reminders_and_tells_the_seller(client, db):
    tuan, an, booking = await _booked(client)
    await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=tuan)
    await client.post(f"/api/v1/bookings/{booking['id']}/cancel", headers=an)

    assert all(r.status == NotificationStatus.CANCELLED for r in _reminders(db, booking["id"]))
    events = await _events(client, tuan)
    assert "VIEWING_CANCELLED" in events and "HOLD_RELEASED" in events
    # The buyer cancelled themselves, so they get no cancellation notice
    assert "VIEWING_CANCELLED" not in await _events(client, an)


@pytest.mark.asyncio
async def test_accepted_reschedule_moves_reminders(client, db):
    tuan, an, booking = await _booked(client)
    await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=tuan)
    await client.post(f"/api/v1/bookings/{booking['id']}/reschedule", json={"start_at": at(16)}, headers=an)
    assert "RESCHEDULE_REQUESTED" in await _events(client, tuan)
    await client.post(f"/api/v1/owner/bookings/{booking['id']}/approve", headers=tuan)

    reminders = _reminders(db, booking["id"])
    pending = [r for r in reminders if r.status == NotificationStatus.PENDING]
    assert {r.scheduled_at for r in pending} == {
        SAT + timedelta(hours=16) - timedelta(hours=24),
        SAT + timedelta(hours=16) - timedelta(hours=2),
    }
    assert len([r for r in reminders if r.status == NotificationStatus.CANCELLED]) == 4
    assert "RESCHEDULE_CONFIRMED" in await _events(client, an)


@pytest.mark.asyncio
async def test_rejection_notifies_buyer(client):
    tuan, an, booking = await _booked(client)
    await client.post(f"/api/v1/owner/bookings/{booking['id']}/reject", json={"reason": "Bận việc"}, headers=tuan)
    [n] = (await client.get("/api/v1/notifications", headers=an)).json()
    assert n["event_type"] == "VIEWING_REJECTED"
    assert "Bận việc" in n["body"]


@pytest.mark.asyncio
async def test_listing_review_notifies_owner(client):
    op = await auth(client, OPERATOR)
    await client.post("/api/v1/operator/properties/33/reject", json={"reason": "Thiếu ảnh"}, headers=op)
    lan = await auth(client, "lan.hoang@gmail.com")
    assert await _events(client, lan) == ["LISTING_REJECTED"]


@pytest.mark.asyncio
async def test_read_and_unread_count_are_per_user(client):
    tuan, _, _ = await _booked(client)
    assert (await client.get("/api/v1/notifications/unread-count", headers=tuan)).json() == {"unread": 1}
    [n] = (await client.get("/api/v1/notifications", headers=tuan)).json()

    binh = await auth(client, CUSTOMER_BINH)
    assert (await client.post(f"/api/v1/notifications/{n['id']}/read", headers=binh)).status_code == 404

    r = await client.post(f"/api/v1/notifications/{n['id']}/read", headers=tuan)
    assert r.json()["read_at"] is not None
    assert (await client.get("/api/v1/notifications/unread-count", headers=tuan)).json() == {"unread": 0}


@pytest.mark.asyncio
async def test_reminder_times_already_passed_are_skipped(client, db):
    # Viewing in 3 hours: the T-24h moment is in the past, only T-2h is scheduled
    start = (datetime.now(UTC) + timedelta(hours=3)).replace(second=0, microsecond=0)
    tuan = await auth(client, OWNER_TUAN)
    await client.post(
        f"/api/v1/owner/properties/{PROPERTY_ID}/slots",
        json={
            "start_at": (start - timedelta(minutes=30)).isoformat(),
            "end_at": (start + timedelta(hours=1)).isoformat(),
        },
        headers=tuan,
    )
    an = await auth(client, CUSTOMER_AN)
    r = await client.post(
        "/api/v1/bookings", json={"property_id": PROPERTY_ID, "start_at": start.isoformat()}, headers=an
    )
    assert r.status_code == 201, r.text
    await client.post(f"/api/v1/owner/bookings/{r.json()['id']}/approve", headers=tuan)

    assert {n.event_type for n in _reminders(db, r.json()["id"])} == {"REMINDER_T2h"}
