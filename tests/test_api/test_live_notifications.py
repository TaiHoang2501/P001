"""Live notifications (SSE): a notification sent while the stream is open is pushed at once; older ones are not."""

import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest

from src.config import get_settings
from src.services import notification_live, notification_service
from tests.helpers import CUSTOMER_AN, OWNER_TUAN, auth

TUAN_ID = 4


@pytest.fixture
def fast_stream(monkeypatch):
    monkeypatch.setattr(get_settings(), "notification_stream_poll_seconds", 0.05)
    monkeypatch.setattr(get_settings(), "notification_stream_max_seconds", 1.5)


def _events(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines() if not line.startswith(":"))
        if "event" in lines:
            out.append((lines["event"], json.loads(lines["data"])))
    return out


async def _next_notification(events) -> dict:
    async for chunk in events:
        for name, data in _events(chunk):
            if name == "notification":
                return data
    raise AssertionError("stream ended without a notification")


@pytest.mark.asyncio
async def test_new_notification_is_pushed_old_ones_are_not(db, fast_stream):
    notification_service.notify(db, TUAN_ID, "OLD", "Cũ", "đã có trước")
    db.commit()
    await asyncio.sleep(0.01)
    events = notification_live.stream(TUAN_ID)
    first = _events(await anext(events))
    assert first[0][0] == "ready"

    notification_service.notify(db, TUAN_ID, "VIEWING_REQUESTED", "Yêu cầu xem nhà mới", "An muốn xem căn")
    db.commit()
    note = await asyncio.wait_for(_next_notification(events), timeout=3)
    assert note["title"] == "Yêu cầu xem nhà mới"
    await events.aclose()


@pytest.mark.asyncio
async def test_only_your_own_notifications(db, fast_stream):
    events = notification_live.stream(TUAN_ID)
    await anext(events)
    notification_service.notify(db, 1, "OTHER", "Của người khác", "")
    notification_service.notify(db, TUAN_ID, "MINE", "Của Tuấn", "")
    db.commit()
    note = await asyncio.wait_for(_next_notification(events), timeout=3)
    assert note["title"] == "Của Tuấn"
    await events.aclose()


@pytest.mark.asyncio
async def test_endpoint_needs_sign_in_and_resumes_after(client, db, fast_stream):
    assert (await client.get("/api/v1/notifications/stream")).status_code == 401
    tuan = await auth(client, OWNER_TUAN)
    before = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    notification_service.notify(db, TUAN_ID, "VIEWING_REQUESTED", "Trong lúc mất kết nối", "")
    db.commit()
    # Reconnecting with ?after= delivers what was sent while the client was away; the stream then says bye
    r = await client.get("/api/v1/notifications/stream", params={"after": before}, headers=tuan)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = _events(r.text)
    assert [n for n, _ in events][0] == "ready" and events[-1][0] == "bye"
    assert [d["title"] for n, d in events if n == "notification"] == ["Trong lúc mất kết nối"]


@pytest.mark.asyncio
async def test_a_booking_request_pops_up_for_the_seller(client, db, fast_stream):
    """The real flow: a buyer asks to view a home; the owner's stream gets the request."""
    from tests.helpers import first_free_slot

    an = await auth(client, CUSTOMER_AN)
    slot = await first_free_slot(client, 1)  # property 1 belongs to Tuấn
    events = notification_live.stream(TUAN_ID)
    await anext(events)
    r = await client.post("/api/v1/bookings", json={"property_id": 1, "start_at": slot["start_at"]}, headers=an)
    assert r.status_code in (200, 201), r.text
    note = await asyncio.wait_for(_next_notification(events), timeout=3)
    assert note["booking_id"] == r.json()["id"]
    await events.aclose()
