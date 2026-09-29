"""Buyer ∩ seller availability over the API (spec §4.8, AC-06, AC-07)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.db.models import (
    Booking,
    BookingStatus,
    Deal,
    HoldStatus,
    Property,
    PropertyHold,
    SellerProfile,
    SellerVerificationStatus,
)
from tests.helpers import OWNER_TUAN, auth

VN = ZoneInfo("Asia/Ho_Chi_Minh")
PROPERTY_ID = 1  # owned by Tuấn, AVAILABLE
SAT = datetime(2030, 1, 5, tzinfo=VN)


def at(hour: float) -> datetime:
    return SAT + timedelta(hours=hour)


def iso(hour: float) -> str:
    return at(hour).isoformat()


async def _seller_free(client, start: float, end: float) -> None:
    owner = await auth(client, OWNER_TUAN)
    r = await client.post(
        f"/api/v1/owner/properties/{PROPERTY_ID}/slots",
        json={"start_at": iso(start), "end_at": iso(end)},
        headers=owner,
    )
    assert r.status_code == 201, r.text


async def _propose(client, *windows: tuple[float, float]):
    body = {"windows": [{"start_at": iso(s), "end_at": iso(e)} for s, e in windows]}
    return await client.post(f"/api/v1/properties/{PROPERTY_ID}/viewing-times", json=body)


def _starts(items: list[dict]) -> list[datetime]:
    return [datetime.fromisoformat(i["start_at"]) for i in items]


@pytest.mark.asyncio
async def test_ac06_buyer_14_17_seller_1430_16(client):
    await _seller_free(client, 14.5, 16)
    r = await _propose(client, (14, 17))
    assert r.status_code == 200, r.text
    body = r.json()

    assert [
        (datetime.fromisoformat(w["start_at"]), datetime.fromisoformat(w["end_at"])) for w in body["common_windows"]
    ] == [(at(14.5), at(16))]
    assert _starts(body["proposals"]) == [at(14.5), at(15), at(15.5)]
    assert body["alternatives"] == []
    assert body["viewing_duration_minutes"] == 30


@pytest.mark.asyncio
async def test_booked_and_held_times_are_not_proposed(client, db):
    await _seller_free(client, 14.5, 16)
    prop = db.get(Property, PROPERTY_ID)
    booking = Booking(
        property_id=prop.id,
        customer_id=1,
        start_at=at(15),
        end_at=at(15.5),
        status=BookingStatus.CONFIRMED,
    )
    db.add(booking)
    db.commit()

    r = await _propose(client, (14, 17))
    assert _starts(r.json()["proposals"]) == [at(14.5), at(15.5)]

    # A hold alone (e.g. booking already moved on) also blocks its window
    booking.status = BookingStatus.COMPLETED
    db.add(
        PropertyHold(
            booking_id=booking.id,
            deal_id=_deal_id(db, prop),
            property_id=prop.id,
            buyer_id=1,
            start_at=at(14.5),
            end_at=at(15),
            status=HoldStatus.ACTIVE,
        )
    )
    db.commit()
    r = await _propose(client, (14, 17))
    assert _starts(r.json()["proposals"]) == [at(15), at(15.5)]


def _deal_id(db, prop: Property) -> int:
    deal = Deal(buyer_id=1, seller_id=prop.owner_id, property_id=prop.id)
    db.add(deal)
    db.flush()
    return deal.id


@pytest.mark.asyncio
async def test_ac07_no_common_slot_returns_alternatives(client):
    await _seller_free(client, 14.5, 16)
    r = await _propose(client, (8, 9))
    body = r.json()
    assert body["common_windows"] == []
    assert body["proposals"] == []
    # Seller's upcoming free times (seeded daily slots) are offered instead
    assert len(body["alternatives"]) == 3
    assert _starts(body["alternatives"]) == sorted(_starts(body["alternatives"]))


@pytest.mark.asyncio
async def test_rejects_naive_datetimes(client):
    body = {"windows": [{"start_at": "2030-01-05T14:00:00", "end_at": "2030-01-05T17:00:00"}]}
    r = await client.post(f"/api/v1/properties/{PROPERTY_ID}/viewing-times", json=body)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_unverified_seller_property_has_no_viewing_times(client, db):
    db.get(SellerProfile, 4).verification_status = SellerVerificationStatus.UNVERIFIED
    db.commit()
    r = await _propose(client, (14, 17))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "SELLER_UNVERIFIED"
