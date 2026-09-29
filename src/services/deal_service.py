"""Deals: one per Buyer + Seller + Property (spec §4.9, AC-02, AC-09).

A deal's early status mirrors its bookings; later statuses (INTERESTED onwards) are
set by humans after the viewing and are never overwritten here.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.core.actor import Actor
from src.core.errors import NotFoundError, StateConflictError
from src.db.models import (
    CLOSED_DEAL_STATUSES,
    Booking,
    BookingStatus,
    Building,
    Deal,
    DealStatus,
    Property,
    UserRole,
)
from src.models.deal import DealOut
from src.services import audit

# Statuses this module derives from bookings; anything else is owned by people
_BOOKING_DRIVEN = {
    DealStatus.MATCHED,
    DealStatus.VIEWING_REQUESTED,
    DealStatus.VIEWING_CONFIRMED,
    DealStatus.VIEWED,
}


def get_or_create_open(db: Session, actor: Actor, prop: Property) -> Deal:
    """The buyer's open deal for this property, created (MATCHED) if there is none. Row-locked."""
    deal = db.scalar(
        select(Deal)
        .where(
            Deal.buyer_id == actor.id,
            Deal.property_id == prop.id,
            Deal.status.not_in(CLOSED_DEAL_STATUSES),
        )
        .with_for_update()
    )
    if deal is not None:
        return deal
    deal = Deal(buyer_id=actor.id, seller_id=prop.owner_id, property_id=prop.id, status=DealStatus.MATCHED)
    db.add(deal)
    db.flush()
    db.refresh(deal, ["code"])
    audit.record(db, actor, "deal.create", "deal", deal.id, after={"code": deal.code, "property_id": prop.id})
    return deal


def sync_status(db: Session, actor: Actor, deal: Deal) -> None:
    """Move the deal to match its bookings (called in the same transaction as the booking change)."""
    if deal.status not in _BOOKING_DRIVEN:
        return
    statuses = set(db.scalars(select(Booking.status).where(Booking.deal_id == deal.id)))
    if BookingStatus.COMPLETED in statuses:
        target = DealStatus.VIEWED
    elif BookingStatus.CONFIRMED in statuses:
        target = DealStatus.VIEWING_CONFIRMED
    elif statuses & {BookingStatus.REQUESTED, BookingStatus.RESCHEDULE_REQUESTED}:
        target = DealStatus.VIEWING_REQUESTED
    else:
        target = DealStatus.MATCHED
    if target != deal.status:
        before = deal.status
        deal.status = target
        audit.record(db, actor, "deal.status", "deal", deal.id, before={"status": before}, after={"status": target})


def require_open(deal: Deal) -> None:
    if deal.status in CLOSED_DEAL_STATUSES:
        raise StateConflictError(f"Deal {deal.code} is already {deal.status.value}")


# ---------- Reads ----------


def _query():
    return select(Deal).options(
        joinedload(Deal.property, innerjoin=True)
        .joinedload(Property.building, innerjoin=True)
        .joinedload(Building.project, innerjoin=True)
    )


def _visible_to(actor: Actor):
    if actor.role == UserRole.CUSTOMER:
        return Deal.buyer_id == actor.id
    if actor.role == UserRole.OWNER:
        return Deal.seller_id == actor.id
    return None


def to_out(deal: Deal) -> DealOut:
    prop = deal.property
    return DealOut(
        id=deal.id,
        code=deal.code,
        status=deal.status,
        property_id=prop.id,
        property_label=f"{prop.building.project.name} · {prop.building.name} · {prop.unit_code}",
        buyer_id=deal.buyer_id,
        seller_id=deal.seller_id,
        disclosure_level=deal.disclosure_level,
        created_at=deal.created_at,
        updated_at=deal.updated_at,
    )


def get(db: Session, actor: Actor, deal_id: int) -> DealOut:
    stmt = _query().where(Deal.id == deal_id)
    if (cond := _visible_to(actor)) is not None:
        stmt = stmt.where(cond)
    deal = db.scalar(stmt)
    if deal is None:
        raise NotFoundError(f"Deal {deal_id} not found")
    return to_out(deal)


def list_for(db: Session, actor: Actor, status: DealStatus | None = None) -> list[DealOut]:
    """Buyers see their deals, sellers the deals on their properties, operators all."""
    stmt = _query()
    if (cond := _visible_to(actor)) is not None:
        stmt = stmt.where(cond)
    if status is not None:
        stmt = stmt.where(Deal.status == status)
    return [to_out(d) for d in db.scalars(stmt.order_by(Deal.updated_at.desc()))]
